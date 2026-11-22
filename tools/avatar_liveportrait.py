"""Motor V2 — LivePortrait lip re-rendering for the dynamic avatar director.

Why this exists
---------------
Wav2Lip generates the mouth inside a 96x96 crop and pastes it back, so every
lip-synced block loses all skin/lip/beard detail (the face turns into plastic)
while the un-synced tail of the video stays sharp. LivePortrait instead keeps the
appearance of the *sharp* source frame and only re-renders the animated region
with its own generator (512 px face crop + paste-back), so the face detail is
preserved.

Pipeline per block (one fresh process per block, VRAM released in between):

    source  = the sharp slice of the plan clip  (assets/avatar/<clip>_<mode>.mp4)
    driving = the Wav2Lip result for that block (assets/avatar/lipsync/<seg>.mp4)
    run     = LivePortrait inference.py -s source -d driving
              --animation_region lip --flag_relative_motion --flag_stitching

`animation_region=lip` transfers only the lip motion from the driving video, so
head pose, blinks and body motion stay exactly as in the sharp source clip. The
resulting clip is muted, conformed to the layout size and gets written back to
`avatar_plan.json` as `media_override` (with `--apply`).

Deterministic fallback: when LivePortrait, CUDA or the driving clip is missing,
the block keeps the Wav2Lip clip already mounted by `avatar_lipsync.py`, and the
pipeline never breaks.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.avatar_lipsync import (  # noqa: E402  (shared helpers)
    MODE_DIMS,
    _find_ffmpeg,
    _find_python,
    _overlaps,
    _probe_duration,
    _run,
    conform_clip,
    vram_info,
)

DEFAULT_LIVEPORTRAIT_DIR = Path(os.getenv("LIVEPORTRAIT_DIR", r"D:\Utilitarios\LivePortrait"))
DEFAULT_SPEECH_BLOCKS = [[0.0, 6.0], [9.5, 12.0], [14.5, 17.36]]


def _lp_python(args: argparse.Namespace) -> Path:
    """Python that can import LivePortrait (torch + onnxruntime + tyro)."""
    candidates = [
        Path(args.lp_python) if args.lp_python else None,
        Path(r"D:\Comfy\ComfyUI\venv\Scripts\python.exe"),
        Path(r"C:\Users\Pires\AppData\Local\Programs\Python\Python312\python.exe"),
    ]
    for candidate in candidates:
        if not candidate or not candidate.is_file():
            continue
        probe = subprocess.run(
            [str(candidate), "-c", "import tyro, onnxruntime, torch; print('ok')"],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode == 0 and "ok" in probe.stdout:
            return candidate
    raise FileNotFoundError(
        "No Python with LivePortrait dependencies (tyro/onnxruntime/torch) found; pass --lp-python"
    )


def run_liveportrait(
    python: Path,
    lp_dir: Path,
    source: Path,
    driving: Path,
    out_dir: Path,
    animation_region: str,
    driving_multiplier: float,
    source_max_dim: int,
    min_free_mb: int,
    vram_python: Path,
    timeout_s: int,
) -> dict[str, Any]:
    info = vram_info(vram_python)
    if not info.get("cuda"):
        raise RuntimeError(f"CUDA unavailable: {info.get('error') or info}")
    if info.get("free_mb") is not None and info["free_mb"] < min_free_mb:
        raise RuntimeError(
            f"Not enough free VRAM for LivePortrait: {info['free_mb']} MB free, "
            f"{min_free_mb} MB required"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(python), "inference.py",
        "-s", str(source.resolve()),
        "-d", str(driving.resolve()),
        "-o", str(out_dir.resolve()),
        "--animation_region", animation_region,
        "--flag_relative_motion",
        "--flag_stitching",
        "--source_max_dim", str(source_max_dim),
        "--driving_multiplier", f"{driving_multiplier:.3f}",
    ]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        env["PATH"] = str(Path(ffmpeg_bin).parent) + os.pathsep + env.get("PATH", "")

    started = time.time()
    log_path = out_dir / f"{source.stem}--{driving.stem}.liveportrait.log"
    proc = subprocess.run(
        cmd,
        cwd=str(lp_dir),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout_s,
    )
    log_path.write_text((proc.stdout or "") + "\n" + (proc.stderr or ""), encoding="utf-8")

    produced = out_dir / f"{source.stem}--{driving.stem}.mp4"
    if proc.returncode != 0 or not produced.is_file():
        tail = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()[-1500:]
        raise RuntimeError(
            f"LivePortrait failed (exit {proc.returncode}, file={produced.is_file()}) "
            f"log={log_path}\n{tail}"
        )
    return {
        "engine": "liveportrait",
        "animation_region": animation_region,
        "driving_multiplier": driving_multiplier,
        "elapsed_seconds": round(time.time() - started, 1),
        "vram_free_mb_before": info.get("free_mb"),
        "vram_total_mb": info.get("total_mb"),
        "gpu": info.get("name"),
        "raw_output": str(produced),
    }



# ---------------------------------------------------------------------------
# Mouth-only composite: keep the sharp source pixels, take only the lips from
# LivePortrait. LivePortrait re-renders the whole face crop through its SPADE
# generator, which softens skin/beard by ~2x even where nothing moves; blending
# only a feathered mouth ellipse restores the original detail everywhere else.
# ---------------------------------------------------------------------------

def composite_mouth(
    ffmpeg: str,
    source_clip: Path,
    lp_clip: Path,
    dest: Path,
    fps: int,
    sharpen: float,
    feather: float,
) -> bool:
    try:
        import cv2  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415
    except Exception:
        return False

    src_cap = cv2.VideoCapture(str(source_clip))
    lp_cap = cv2.VideoCapture(str(lp_clip))
    ok, first = lp_cap.read()
    if not ok:
        src_cap.release()
        lp_cap.release()
        return False
    h, w = first.shape[:2]
    lp_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(cv2.cvtColor(first, cv2.COLOR_BGR2GRAY), 1.08, 5, minSize=(60, 60))
    if len(faces) == 0:
        src_cap.release()
        lp_cap.release()
        return False
    x, y, fw, fh = sorted(faces, key=lambda b: b[2] * b[3])[-1]

    mask = np.zeros((h, w), dtype=np.float32)
    center = (int(x + 0.5 * fw), int(y + 0.72 * fh))
    axes = (max(8, int(0.34 * fw)), max(6, int(0.26 * fh)))
    cv2.ellipse(mask, center, axes, 0, 0, 360, 1.0, -1)
    sigma = max(3.0, feather * fw)
    k = int(sigma * 4) | 1
    mask = cv2.GaussianBlur(mask, (k, k), sigma)
    mask3 = mask[:, :, None]

    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
        "-an", "-c:v", "libx264", "-crf", "15", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dest),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    written = 0
    try:
        while True:
            ok_s, src = src_cap.read()
            ok_l, lp = lp_cap.read()
            if not ok_s or not ok_l:
                break
            if lp.shape[:2] != (h, w):
                lp = cv2.resize(lp, (w, h), interpolation=cv2.INTER_LANCZOS4)
            mouth = lp.astype(np.float32)
            if sharpen > 0:
                blurred = cv2.GaussianBlur(mouth, (0, 0), 1.1)
                mouth = np.clip(mouth * (1.0 + sharpen) - blurred * sharpen, 0, 255)
            out = src.astype(np.float32) * (1.0 - mask3) + mouth * mask3
            proc.stdin.write(np.clip(out, 0, 255).astype(np.uint8).tobytes())
            written += 1
    finally:
        src_cap.release()
        lp_cap.release()
        if proc.stdin:
            proc.stdin.close()
        proc.wait()
    return written > 0 and dest.is_file()


def lip_sync_project(args: argparse.Namespace) -> dict[str, Any]:
    project = Path(args.project)
    hf_dir = project / "hyperframes"
    assets_dir = hf_dir / "assets"
    plan_path = Path(args.plan) if args.plan else project / "artifacts" / "avatar_plan.json"
    lipsync_dir = Path(args.lipsync_dir) if args.lipsync_dir else assets_dir / "avatar" / "lipsync"
    out_dir = Path(args.out_dir) if args.out_dir else assets_dir / "avatar" / "liveportrait"
    work_root = out_dir / "_work"
    report_path = project / "artifacts" / "liveportrait_report.json"
    lp_dir = Path(args.liveportrait_dir)

    if not plan_path.is_file():
        raise FileNotFoundError(f"avatar_plan.json not found: {plan_path}")
    if not (lp_dir / "inference.py").is_file():
        raise FileNotFoundError(f"LivePortrait not found at {lp_dir}")

    ffmpeg = _find_ffmpeg(args.ffmpeg)
    vram_python = _find_python(args.vram_python)
    lp_python = _lp_python(args)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    blocks = plan.get("speech_blocks") or DEFAULT_SPEECH_BLOCKS
    fps = int(plan.get("fps") or args.fps)
    segments = plan.get("segments", [])
    wanted = set(args.only.split(",")) if args.only else None

    results: list[dict[str, Any]] = []
    for seg in segments:
        seg_id = str(seg.get("id"))
        mode = str(seg.get("mode"))
        start = float(seg["start"])
        end = float(seg["end"])
        duration = round(end - start, 3)
        clip = seg.get("clip")

        if wanted and seg_id not in wanted:
            continue
        if mode not in MODE_DIMS or not clip:
            results.append({"id": seg_id, "status": "skipped", "reason": "no avatar media"})
            continue
        if seg.get("lip_sync") is False:
            results.append({"id": seg_id, "status": "skipped", "reason": "lip_sync disabled (neutral hold)"})
            continue
        if not _overlaps(start, end, blocks):
            results.append({"id": seg_id, "status": "skipped", "reason": "outside speech windows"})
            continue

        suffix = "split" if mode == "split" else "full"
        source = assets_dir / "avatar" / f"{clip}_{suffix}.mp4"
        driving = lipsync_dir / f"{seg_id}.mp4"
        if not source.is_file():
            results.append({"id": seg_id, "status": "failed", "reason": f"missing source {source}"})
            continue
        if not driving.is_file():
            results.append(
                {
                    "id": seg_id,
                    "status": "failed",
                    "reason": f"missing Wav2Lip driving clip {driving} (run tools/avatar_lipsync.py first)",
                    "fallback": "original clip kept",
                }
            )
            continue

        width, height = MODE_DIMS[mode]
        dest = out_dir / f"{seg_id}.mp4"
        if dest.is_file() and not args.force:
            results.append({"id": seg_id, "status": "cached", "output": str(dest)})
            continue
        if args.dry_run:
            results.append(
                {"id": seg_id, "status": "planned", "source": str(source), "driving": str(driving)}
            )
            continue

        work = work_root / seg_id
        work.mkdir(parents=True, exist_ok=True)
        src_slice = work / f"{seg_id}.source.mp4"
        drv_slice = work / f"{seg_id}.driving.mp4"
        try:
            media_start = float(seg.get("media_start") or 0.0)
            _run(
                [
                    ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", f"{media_start:.3f}", "-t", f"{duration:.3f}", "-i", str(source),
                    "-an", "-r", str(fps), "-pix_fmt", "yuv420p",
                    "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", str(src_slice),
                ]
            )
            shift = max(0, int(args.drive_shift_frames))
            shift_s = shift / float(fps)
            _run(
                [
                    ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", f"{shift_s:.3f}", "-i", str(driving),
                    "-an", "-r", str(fps), "-pix_fmt", "yuv420p",
                    "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", str(drv_slice),
                ]
            )
            if shift:
                padded = work / f"{seg_id}.driving_pad.mp4"
                _run(
                    [
                        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                        "-i", str(drv_slice),
                        "-vf", f"tpad=stop_mode=clone:stop_duration={shift_s + 0.2:.3f},trim=duration={duration:.3f},setpts=PTS-STARTPTS",
                        "-an", "-r", str(fps), "-c:v", "libx264", "-crf", "16", "-preset", "veryfast",
                        str(padded),
                    ]
                )
                drv_slice = padded
            meta = run_liveportrait(
                python=lp_python,
                lp_dir=lp_dir,
                source=src_slice,
                driving=drv_slice,
                out_dir=work,
                animation_region=args.animation_region,
                driving_multiplier=args.driving_multiplier,
                source_max_dim=args.source_max_dim,
                min_free_mb=args.min_free_mb,
                vram_python=vram_python,
                timeout_s=args.timeout_s,
            )
            raw = Path(meta["raw_output"])
            if not raw.is_file():
                # LivePortrait writes "<src>--<drv>.mp4"; fall back to the concat variant.
                alt = raw.with_name(raw.stem + "_concat.mp4")
                if alt.is_file():
                    raw = alt
                    meta["raw_output"] = str(alt)
                else:
                    raise RuntimeError(f"LivePortrait produced no usable file next to {raw}")
            probed = _probe_duration(ffmpeg, raw)
            if probed + 0.25 < duration:
                raise RuntimeError(
                    f"LivePortrait output too short: {probed:.2f}s < block {duration:.2f}s"
                )
            composited = False
            if not args.no_mouth_composite:
                composited = composite_mouth(
                    ffmpeg=ffmpeg,
                    source_clip=src_slice,
                    lp_clip=raw,
                    dest=dest,
                    fps=fps,
                    sharpen=args.mouth_sharpen,
                    feather=args.mouth_feather,
                )
            if not composited:
                conform_clip(ffmpeg, raw, dest, width, height, duration, fps)
            results.append(
                {
                    "id": seg_id,
                    "mode": mode,
                    "status": "done",
                    "start": start,
                    "end": end,
                    "duration": duration,
                    "source": str(source),
                    "driving": str(driving),
                    "output": str(dest),
                    "dimensions": f"{width}x{height}",
                    "mouth_composite": composited,
                    **meta,
                }
            )
        except Exception as exc:  # noqa: BLE001 — deterministic fallback
            results.append(
                {
                    "id": seg_id,
                    "status": "failed",
                    "reason": f"{type(exc).__name__}: {exc}"[:1200],
                    "fallback": "Wav2Lip clip kept",
                }
            )

    done = [r for r in results if r["status"] == "done"]
    cached = [r for r in results if r["status"] == "cached"]
    failed = [r for r in results if r["status"] == "failed"]

    report = {
        "version": "1.0",
        "engine": "liveportrait",
        "liveportrait_dir": str(lp_dir),
        "python": str(lp_python),
        "animation_region": args.animation_region,
        "driving_multiplier": args.driving_multiplier,
        "drive_shift_frames": args.drive_shift_frames,
        "mouth_composite": not args.no_mouth_composite,
        "speech_blocks": blocks,
        "min_free_vram_mb": args.min_free_mb,
        "blocks": results,
        "summary": {
            "done": len(done),
            "cached": len(cached),
            "failed": len(failed),
            "skipped": len([r for r in results if r["status"] in ("skipped", "planned")]),
        },
    }

    if args.apply and (done or cached):
        by_id = {r["id"]: r for r in done + cached}
        for seg in segments:
            entry = by_id.get(str(seg.get("id")))
            if not entry:
                continue
            dest = Path(entry.get("output") or out_dir / f"{seg['id']}.mp4")
            if not dest.is_file():
                continue
            try:
                rel = dest.relative_to(hf_dir).as_posix()
            except ValueError:
                rel = str(dest)
            seg["media_override"] = rel
            seg["media_start"] = 0.0
            seg["lip_engine"] = "liveportrait"
        plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        report["applied_to_plan"] = True

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if not args.keep_work and not args.dry_run:
        shutil.rmtree(work_root, ignore_errors=True)

    return report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="LivePortrait lip re-rendering for the Motor V2 avatar plan")
    p.add_argument("--project", default="projects/teste-jornal-ia")
    p.add_argument("--plan", default=None)
    p.add_argument("--lipsync-dir", default=None, help="Wav2Lip driving clips (default: assets/avatar/lipsync)")
    p.add_argument("--out-dir", default=None, help="Default: assets/avatar/liveportrait")
    p.add_argument("--liveportrait-dir", default=str(DEFAULT_LIVEPORTRAIT_DIR))
    p.add_argument("--lp-python", default=None, help="Python with tyro/onnxruntime/torch (LivePortrait)")
    p.add_argument("--vram-python", default=None, help="Python with CUDA torch (VRAM guard)")
    p.add_argument("--ffmpeg", default=None)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--animation-region", default="lip", choices=["lip", "exp", "pose", "eyes", "all"])
    p.add_argument("--driving-multiplier", type=float, default=0.7,
                   help="Ganho do movimento labial vindo do driving (1.0 amplifica demais)")
    p.add_argument("--drive-shift-frames", type=int, default=0,
                   help="Avanca o driving N frames para compensar atraso do Wav2Lip")
    p.add_argument("--no-mouth-composite", action="store_true",
                   help="Desliga o blend so-da-boca (mantem o frame inteiro do LivePortrait)")
    p.add_argument("--mouth-sharpen", type=float, default=0.35,
                   help="Unsharp na boca do LivePortrait antes do blend")
    p.add_argument("--mouth-feather", type=float, default=0.05,
                   help="Raio do feather da mascara, como fracao da largura do rosto")
    p.add_argument("--source-max-dim", type=int, default=1920)
    p.add_argument("--min-free-mb", type=int, default=700)
    p.add_argument("--timeout-s", type=int, default=1800)
    p.add_argument("--only", default=None, help="Comma-separated segment ids")
    p.add_argument("--apply", action="store_true", help="Write media_override back into avatar_plan.json")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--keep-work", action="store_true")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = lip_sync_project(args)
    except Exception as exc:  # noqa: BLE001
        print(f"[avatar_liveportrait] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not report["summary"]["failed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
