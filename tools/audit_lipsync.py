"""Lip-sync / quality audit for the Motor V2 avatar blocks.

Answers two questions with numbers instead of opinions:

1. **Sync** — how many frames does the mouth motion lag the narration?
   Method: audio RMS envelope (30 Hz) x mouth-ROI frame difference (30 Hz), normalised
   cross-correlation over ±0.5 s. Reported as `lag_frames` (positive = mouth reacts
   *after* the audio) plus the correlation at that lag.

2. **Quality** — is the talking face as sharp as the silent/source one?
   Method: variance of the Laplacian inside the detected face box, averaged over frames
   ("sharpness"). A Wav2Lip block that is visibly plastic scores far below the source.

Usage:
    python tools/audit_lipsync.py --project projects/teste-jornal-ia
    python tools/audit_lipsync.py --project projects/teste-jornal-ia --only seg_2_headline_split

Output: `<project>/artifacts/quality_audit.json` (plus a console summary).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np


def _audio_envelope(ffmpeg: str, wav: Path, start: float, duration: float, fps: int = 30, sr: int = 16000) -> np.ndarray:
    proc = subprocess.run(
        [
            ffmpeg, "-v", "error", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
            "-i", str(wav), "-ac", "1", "-ar", str(sr), "-f", "s16le", "-",
        ],
        capture_output=True,
        check=False,
    )
    audio = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    hop = max(1, int(sr / fps))
    n = len(audio) // hop
    return np.array([float(np.sqrt((audio[i * hop:(i + 1) * hop] ** 2).mean())) for i in range(n)])


def _face_box(gray: np.ndarray) -> Optional[tuple[int, int, int, int]]:
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, 1.08, 5, minSize=(80, 80))
    if len(faces) == 0:
        return None
    return tuple(int(v) for v in sorted(faces, key=lambda b: b[2] * b[3])[-1])


def _clip_series(path: Path) -> dict[str, Any]:
    """Mouth-motion envelope + sharpness, mouth ROI locked on the first detected face."""
    cap = cv2.VideoCapture(str(path))
    motion: list[float] = []
    sharp: list[float] = []
    box: Optional[tuple[int, int, int, int]] = None
    prev = None
    frames = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if box is None:
            face = _face_box(gray)
            if face is not None:
                x, y, w, h = face
                # face box -> mouth region + face region for sharpness
                box = (x, y, w, h)
        if box is None:
            motion.append(0.0)
            sharp.append(0.0)
            continue
        x, y, w, h = box
        fx0, fy0, fx1, fy1 = x, y, x + w, y + h
        mx0, my0 = int(x + 0.25 * w), int(y + 0.60 * h)
        mx1, my1 = int(x + 0.75 * w), int(y + 0.95 * h)
        face_crop = gray[fy0:fy1, fx0:fx1]
        sharp.append(float(cv2.Laplacian(face_crop, cv2.CV_64F).var()) if face_crop.size else 0.0)
        mouth = cv2.resize(gray[my0:my1, mx0:mx1], (120, 80)).astype(np.float32)
        motion.append(0.0 if prev is None else float(np.abs(mouth - prev).mean()))
        prev = mouth
    cap.release()
    return {
        "frames": frames,
        "mouth_motion": motion,
        "sharpness": sharp,
        "face_box": box,
    }


def _best_lag(env: np.ndarray, motion: list[float], max_frames: int = 15) -> dict[str, Any]:
    motion = np.asarray(motion, dtype=np.float32)
    n = min(len(env), len(motion))
    env, motion = env[:n], motion[:n]
    if n == 0 or float(env.std()) == 0.0 or float(motion.std()) == 0.0:
        return {"lag_frames": None, "corr": None, "peak_at_zero": None}
    env = (env - env.mean()) / (env.std() + 1e-8)
    motion = (motion - motion.mean()) / (motion.std() + 1e-8)
    scores = []
    for lag in range(-max_frames, max_frames + 1):
        if lag >= 0:
            a, b = env[lag:], motion[: len(motion) - lag]
        else:
            a, b = env[:lag], motion[-lag:]
        m = min(len(a), len(b))
        if m < 10:
            continue
        scores.append((lag, float(np.dot(a[:m], b[:m]) / m)))
    if not scores:
        return {"lag_frames": None, "corr": None, "peak_at_zero": None}
    best = max(scores, key=lambda s: s[1])
    at_zero = next((s[1] for s in scores if s[0] == 0), None)
    return {
        "lag_frames": best[0],
        "lag_seconds": round(best[0] / 30.0, 3),
        "corr": round(best[1], 3),
        "peak_at_zero": round(at_zero, 3) if at_zero is not None else None,
    }


def audit(args: argparse.Namespace) -> dict[str, Any]:
    project = Path(args.project)
    hf = project / "hyperframes"
    assets = hf / "assets" / "avatar"
    plan = json.loads((project / "artifacts" / "avatar_plan.json").read_text(encoding="utf-8"))
    voice = Path(args.voice_wav) if args.voice_wav else project / "assets" / "audio" / "voice_only_clean.wav"
    ffmpeg = args.ffmpeg or "ffmpeg"
    wanted = set(args.only.split(",")) if args.only else None

    clips: dict[str, Any] = {}
    for seg in plan.get("segments", []):
        seg_id = str(seg.get("id"))
        if wanted and seg_id not in wanted:
            continue
        if not seg.get("lip_sync", True):
            continue
        suffix = "split" if seg.get("mode") == "split" else "full"
        source = assets / f"{seg.get('clip')}_{suffix}.mp4"
        candidates = {
            "wav2lip": assets / "lipsync" / f"{seg_id}.mp4",
            "liveportrait": assets / "liveportrait" / f"{seg_id}.mp4",
        }
        entry: dict[str, Any] = {
            "id": seg_id,
            "start": seg["start"],
            "end": seg["end"],
            "source": str(source),
            "engines": {},
        }
        env = _audio_envelope(ffmpeg, voice, float(seg["start"]), float(seg["end"]) - float(seg["start"]))
        for engine, path in candidates.items():
            if not path.is_file():
                continue
            series = _clip_series(path)
            lag = _best_lag(env, series["mouth_motion"])
            sharp = [s for s in series["sharpness"] if s > 0]
            entry["engines"][engine] = {
                "file": str(path),
                "frames": series["frames"],
                "sync": lag,
                "sharpness_mean": round(float(np.mean(sharp)), 1) if sharp else None,
            }
        if source.is_file():
            series = _clip_series(source)
            sharp = [s for s in series["sharpness"] if s > 0]
            entry["source_sharpness_mean"] = round(float(np.mean(sharp)), 1) if sharp else None
        # relative sharpness vs the sharp source slice
        base = entry.get("source_sharpness_mean")
        if base:
            for engine, data in entry["engines"].items():
                if data.get("sharpness_mean"):
                    data["sharpness_vs_source"] = round(data["sharpness_mean"] / base, 2)
        clips[seg_id] = entry

    report = {
        "version": "1.0",
        "method": {
            "sync": "normalized cross-correlation between audio RMS envelope (30 Hz) and "
                    "mouth-ROI frame difference (30 Hz); positive lag = mouth after audio",
            "sharpness": "mean variance of the Laplacian inside the detected face box",
            "caveat": "blocks that are mostly silence give a weak correlation and an unreliable lag",
        },
        "voice_track": str(voice),
        "clips": clips,
    }
    out = project / "artifacts" / "quality_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report["report_path"] = str(out)
    return report


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Audit lip-sync timing and face sharpness per avatar block")
    p.add_argument("--project", default="projects/teste-jornal-ia")
    p.add_argument("--voice-wav", default=None)
    p.add_argument("--ffmpeg", default=None)
    p.add_argument("--only", default=None)
    args = p.parse_args(argv)
    try:
        report = audit(args)
    except Exception as exc:  # noqa: BLE001
        print(f"[audit_lipsync] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    for cid, c in report["clips"].items():
        print(f"\n{cid}  ({c['start']}-{c['end']}s)  source sharpness={c.get('source_sharpness_mean')}")
        for engine, d in c["engines"].items():
            print(
                f"  {engine:12s} sharpness={d['sharpness_mean']} "
                f"({d.get('sharpness_vs_source')}x source)  "
                f"lag={d['sync'].get('lag_frames')} frames / {d['sync'].get('lag_seconds')}s  "
                f"corr={d['sync'].get('corr')}"
            )
    print(f"\nreport: {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
