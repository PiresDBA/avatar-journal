"""Per-block calibration for the two-stage lip-sync (Wav2Lip driving -> LivePortrait).

Why this exists
---------------
The mouth you see is the motion LivePortrait copies from the Wav2Lip driving clip. Two
constants decide whether that looks right, and both vary a little per block:

* **shift** — LivePortrait's temporal filter adds ~4 frames of delay, and Wav2Lip itself
  reacts ~1-2 frames after the audio. A fixed `--drive-shift-frames 5` over- or under-shoots
  on some blocks.
* **multiplier** — LivePortrait's lip retargeting amplifies or flattens the driving's opening.
  With one global value some blocks open too much and others barely move.

This tool measures both instead of guessing:

1. Landmark lip signal of the *driving* clip (`audit_lip_signal` machinery) vs the word mask
   from `captions_words.json` -> onset lag in frames.
2. `shift = lag + LivePortrait delay` (default 4), clamped.
3. Runs `avatar_liveportrait.py` with that shift and a base multiplier.
4. Measures the produced clip's lip opening against the driving's, computes the corrected
   multiplier (`base / ratio`) and re-runs once when the ratio is off by more than `--tolerance`.

Usage (needs a Python with onnxruntime, e.g. the ComfyUI venv, because of the landmark model):

    python tools/calibrate_lipsync.py --project ./project --apply
    python tools/calibrate_lipsync.py --project ./project --only seg_4_data_split_point --force

Output: `<project>/artifacts/lipsync_calibration.json` with the chosen shift/multiplier per
block, plus the measurements that justify them. The plan keeps pointing at the produced clips.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

try:
    from tools.audit_lip_signal import (
        _landmark_session,
        _FaceDetector,
        _audio_envelope,
        _lip_series,
        _word_mask,
        _lag,
    )
except ModuleNotFoundError:  # running as a script from the repo root
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from tools.audit_lip_signal import (
        _landmark_session,
        _FaceDetector,
        _audio_envelope,
        _lip_series,
        _word_mask,
        _lag,
    )


def _series_ratio(lp_series, drv_series) -> Optional[float]:
    import numpy as np

    def p95(values) -> Optional[float]:
        arr = np.asarray(values, dtype=float)
        arr = arr[~np.isnan(arr)]
        return float(np.percentile(arr, 95)) if arr.size else None

    a = p95(lp_series)
    b = p95(drv_series)
    if not a or not b:
        return None
    return a / b



def _word_onsets(project: Path, start: float, end: float) -> list[float]:
    path = project / "artifacts" / "captions_words.json"
    if not path.is_file():
        return []
    words = json.loads(path.read_text(encoding="utf-8"))
    return [float(w["start"]) for w in words if start <= float(w["start"]) < end]


def _onset_offset_ms(onsets: list[float], series, start: float) -> Optional[float]:
    """Median delay (ms) between a word onset and the nearest lip-opening event.

    A word onset marks the start of a syllable; the mouth opens a few frames later, so an
    offset near 0 means the mouth is in time, positive means it is late (video behind audio),
    negative means it leads. This is far more stable than correlating a step-shaped word mask
    with a smooth opening curve (which peaks mid-vowel by construction).
    """
    import numpy as np

    arr = np.asarray(series, dtype=float)
    if arr.size < 10 or not onsets:
        return None
    filled = np.nan_to_num(arr, nan=0.0)
    smooth = np.convolve(filled, np.ones(3) / 3.0, mode="same")
    velocity = np.gradient(smooth)
    offsets: list[float] = []
    for onset in onsets:
        c = (onset - start) * 30.0
        lo, hi = max(0, int(c - 6)), min(arr.size - 1, int(c + 10))
        if hi <= lo + 2:
            continue
        idx = lo + int(np.argmax(velocity[lo:hi]))
        offsets.append((idx - c) / 30.0)
    if not offsets:
        return None
    return float(np.median(offsets)) * 1000.0


def calibrate(args: argparse.Namespace) -> dict[str, Any]:
    project = Path(args.project)
    hf = project / "hyperframes"
    assets = hf / "assets" / "avatar"
    plan_path = project / "artifacts" / "avatar_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    voice = Path(args.voice_wav) if args.voice_wav else project / "assets" / "audio" / "voice_only_clean.wav"
    ckpt = Path(args.liveportrait_dir) / "pretrained_weights" / "liveportrait" / "landmark.onnx"
    if not ckpt.is_file():
        raise FileNotFoundError(f"landmark model not found: {ckpt}")

    out_path = project / "artifacts" / "lipsync_calibration.json"
    previous: dict[str, Any] = {}
    if out_path.is_file() and not args.force:
        try:
            previous = json.loads(out_path.read_text(encoding="utf-8")).get("blocks", {})
        except Exception:
            previous = {}

    session = _landmark_session(ckpt, args.device)
    detector = _FaceDetector(Path(args.liveportrait_dir))
    wanted = set(args.only.split(",")) if args.only else None
    driver_python = args.driver_python

    blocks: dict[str, Any] = {}
    for seg in plan.get("segments", []):
        seg_id = str(seg.get("id"))
        if wanted and seg_id not in wanted:
            continue
        if seg.get("lip_sync", True) is False or seg.get("mode") not in ("split", "full_avatar"):
            continue
        driving = assets / "lipsync" / f"{seg_id}.mp4"
        if not driving.is_file():
            blocks[seg_id] = {"status": "skipped", "reason": "missing driving clip"}
            continue
        if seg_id in previous and not args.force and previous[seg_id].get("status") == "ok":
            blocks[seg_id] = previous[seg_id]
            blocks[seg_id]["cached"] = True
            continue

        start, end = float(seg["start"]), float(seg["end"])
        duration = end - start
        mask = _word_mask(project, start, end)
        env = _audio_envelope(args.ffmpeg or "ffmpeg", voice, start, duration)

        source_clip = assets / f"{seg.get('clip')}_{'split' if seg.get('mode') == 'split' else 'full'}.mp4"
        drv = _lip_series(session, detector, driving)
        onsets = _word_onsets(project, start, end)
        drv_offset = _onset_offset_ms(onsets, drv["series"], start)
        lag_frames = int(round((drv_offset or 0.0) / 1000.0 * 30.0))
        shift = max(0, min(int(args.max_shift), lag_frames + int(args.lp_delay)))
        src_p95 = None
        if source_clip.is_file():
            src = _lip_series(session, detector, source_clip)
            src_p95 = float(src["stats"].get("p95") or 0.0) or None

        entry: dict[str, Any] = {
            "status": "ok",
            "driving_onset_offset_ms": round(drv_offset, 0) if drv_offset is not None else None,
            "lp_delay_frames": int(args.lp_delay),
            "shift_frames": shift,
            "driving_p95": round(float(drv["stats"].get("p95") or 0.0), 4),
            "source_p95": round(src_p95, 4) if src_p95 else None,
            "attempts": [],
        }
        if args.dry_run:
            entry["status"] = "planned"
            blocks[seg_id] = entry
            continue

        multiplier = float(args.base_multiplier)
        for attempt in range(int(args.max_attempts)):
            cmd = [
                str(driver_python), str(Path(args.driver_script)),
                "--project", str(project),
                "--only", seg_id,
                "--force",
                "--driving-multiplier", f"{multiplier:.2f}",
                "--drive-shift-frames", str(shift),
            ]
            if args.apply:
                cmd.append("--apply")
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
            produced = assets / "liveportrait" / f"{seg_id}.mp4"
            if proc.returncode != 0 or not produced.is_file():
                entry.update({"status": "failed", "reason": (proc.stderr or proc.stdout)[-600:]})
                break
            lp = _lip_series(session, detector, produced)
            lp_p95 = float(lp["stats"].get("p95") or 0.0)
            offset_after = _onset_offset_ms(onsets, lp["series"], start)
            reference = src_p95 or float(drv["stats"].get("p95") or 0.0)
            ratio = (lp_p95 / reference) if reference else None
            entry["attempts"].append({
                "multiplier": round(multiplier, 3),
                "output_p95": round(lp_p95, 4),
                "openness_vs_reference": round(ratio, 3) if ratio else None,
                "onset_offset_ms_after": round(offset_after, 0) if offset_after is not None else None,
            })
            offset_ok = offset_after is None or abs(offset_after) <= float(args.offset_tolerance_ms)
            ratio_ok = ratio is None or abs(ratio - 1.0) <= float(args.tolerance)
            if ratio_ok and offset_ok:
                break
            if not offset_ok:
                # advance/retard the driving by the residual the eye sees, one step only
                shift = max(0, min(int(args.max_shift), shift + int(round(offset_after / 1000.0 * 30.0))))
                entry["shift_frames"] = shift
            if not ratio_ok and ratio:
                # LP opens MORE than the natural reference -> divide; less -> also divide (ratio<1)
                multiplier = max(float(args.min_multiplier), min(float(args.max_multiplier), multiplier / ratio))
        entry["multiplier"] = round(multiplier, 3)
        blocks[seg_id] = entry
        print(f"[calibrate] {seg_id}: shift={shift}f multiplier={multiplier:.2f} "
              f"lag_after={entry['attempts'][-1].get('lag_ms_after')}ms", flush=True)

    report = {
        "version": "1.0",
        "base_multiplier": float(args.base_multiplier),
        "lp_delay_frames": int(args.lp_delay),
        "tolerance": float(args.tolerance),
        "blocks": blocks,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report["report_path"] = str(out_path)
    return report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Per-block shift/multiplier calibration for Wav2Lip+LivePortrait")
    p.add_argument("--project", default="projects/teste-jornal-ia")
    p.add_argument("--voice-wav", default=None)
    p.add_argument("--ffmpeg", default=None)
    p.add_argument("--liveportrait-dir", default="D:/Utilitarios/LivePortrait")
    p.add_argument("--device", default="cpu", choices=["cpu", "cuda"],
                   help="onnxruntime device for the landmark model (cpu is reliable on 6 GB)")
    p.add_argument("--driver-script", default="tools/avatar_liveportrait.py")
    p.add_argument("--driver-python", default=r"C:\Users\Pires\AppData\Local\Programs\Python\Python312\python.exe")
    p.add_argument("--base-multiplier", type=float, default=0.7)
    p.add_argument("--lp-delay", type=int, default=4, help="LivePortrait retarget delay in frames")
    p.add_argument("--max-shift", type=int, default=8)
    p.add_argument("--tolerance", type=float, default=0.2)
    p.add_argument("--offset-tolerance-ms", type=float, default=45.0)
    p.add_argument("--max-attempts", type=int, default=2)
    p.add_argument("--min-multiplier", type=float, default=0.55)
    p.add_argument("--max-multiplier", type=float, default=0.95)
    p.add_argument("--lag-tolerance", type=int, default=1, help="Accept |lag| <= N frames after calibration")
    p.add_argument("--only", default=None)
    p.add_argument("--apply", action="store_true", help="Let avatar_liveportrait write media_override")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = calibrate(args)
    except Exception as exc:  # noqa: BLE001
        print(f"[calibrate_lipsync] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    for sid, entry in report["blocks"].items():
        print(f"{sid}: {json.dumps({k: v for k, v in entry.items() if k != 'attempts'}, ensure_ascii=False)}")
    print(f"report: {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
