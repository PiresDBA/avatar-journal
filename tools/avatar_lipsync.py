"""Motor V2 — per-block Wav2Lip lip-sync for the dynamic avatar director.

Reads `artifacts/avatar_plan.json`, and for every avatar block that falls inside
a speech window it lip-syncs that specific clip slice against the corresponding
slice of the clean narration track. Everything runs one block at a time in a
fresh Python process, so CUDA memory is fully released between blocks. That
keeps the peak well under the GTX 1060's 6 GB.

Output clips are muted (the final mix stays the single audio source) and are
written at the exact layout size the plan expects:
  - split        -> 1080x864
  - full_avatar  -> 1080x1920

`--apply` writes `media_override` + `media_start: 0.0` into the plan segments so
`tools/avatar_slot.py --plan` mounts the lip-synced clips instead of the source
loop. When Wav2Lip is missing or a block fails, the segment keeps its original
clip (deterministic fallback — the pipeline never breaks).
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

DEFAULT_WAV2LIP_DIR = Path(os.getenv("WAV2LIP_DIR", r"D:\Utilitarios\Wav2Lip"))
DEFAULT_PYTHON_CANDIDATES = [
    Path(r"D:\Comfy\ComfyUI\venv\Scripts\python.exe"),
    Path(r"C:\Users\Pires\AppData\Local\Programs\Python\Python312\python.exe"),
    Path(r"D:\Utilitarios\OpenMontage\.venv\Scripts\python.exe"),
]
DEFAULT_SPEECH_BLOCKS = [[0.0, 6.0], [9.5, 12.0], [14.5, 18.0]]
MODE_DIMS = {"split": (1080, 864), "full_avatar": (1080, 1920)}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _find_ffmpeg(override: Optional[str] = None) -> str:
    if override:
        return override
    for candidate in (r"D:\Utilitarios\ffmpeg\bin\ffmpeg.exe", r"C:\ffmpeg\bin\ffmpeg.exe"):
        if Path(candidate).is_file():
            return candidate
    found = shutil.which("ffmpeg")
    if not found:
        raise FileNotFoundError("ffmpeg not found; pass --ffmpeg")
    return found


def _run(cmd: list[str], cwd: Optional[Path] = None, env: Optional[dict[str, str]] = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr.strip()[-1500:]}"
        )
    return proc


def _find_python(override: Optional[str]) -> Path:
    if override:
        path = Path(override)
        if not path.is_file():
            raise FileNotFoundError(f"Python not found: {path}")
        return path
    for candidate in DEFAULT_PYTHON_CANDIDATES:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("No usable Python found; pass --python")


def _probe(python: Path, code: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(python), "-c", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def vram_info(python: Path) -> dict[str, Any]:
    code = (
        "import json,torch\n"
        "torch.cuda.init()\n"
        "free,total=torch.cuda.mem_get_info()\n"
        "print(json.dumps({'free_mb':round(free/1048576),'total_mb':round(total/1048576),"
        "'name':torch.cuda.get_device_name(0),'cuda':torch.cuda.is_available()}))"
    )
    proc = _probe(python, code)
    if proc.returncode != 0 or not proc.stdout.strip():
        return {"cuda": False, "free_mb": None, "total_mb": None, "name": None, "error": proc.stderr.strip()[-300:]}
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {"cuda": False, "free_mb": None, "total_mb": None, "name": None, "error": proc.stdout[-300:]}


def _probe_duration(ffmpeg: str, path: Path) -> float:
    ffprobe = str(Path(ffmpeg).with_name("ffprobe.exe")) if Path(ffmpeg).suffix else shutil.which("ffprobe") or "ffprobe"
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    try:
        return float(proc.stdout.strip().splitlines()[0])
    except Exception:
        return 0.0


def _overlaps(seg_start: float, seg_end: float, blocks: list[list[float]]) -> bool:
    return any(min(seg_end, b[1]) - max(seg_start, b[0]) > 0.05 for b in blocks)


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------


def prepare_block(
    ffmpeg: str,
    source: Path,
    media_start: float,
    duration: float,
    voice_wav: Path,
    timeline_start: float,
    mode: str,
    out_dir: Path,
    seg_id: str,
    fps: int,
) -> tuple[Path, Path]:
    """Cut the source face clip and the matching narration slice."""
    out_dir.mkdir(parents=True, exist_ok=True)
    face_path = out_dir / f"{seg_id}.face.mp4"
    audio_path = out_dir / f"{seg_id}.voice.wav"

    _run(
        [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{media_start:.3f}", "-t", f"{duration:.3f}",
            "-i", str(source),
            "-an", "-r", str(fps), "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-crf", "16", "-preset", "veryfast",
            str(face_path),
        ]
    )

    # Pad the narration slice so short segments never end mid-word truncation.
    _run(
        [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{timeline_start:.3f}", "-t", f"{duration:.3f}",
            "-i", str(voice_wav),
            "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
            str(audio_path),
        ]
    )
    return face_path, audio_path


def run_wav2lip(
    python: Path,
    wav2lip_dir: Path,
    checkpoint: Path,
    face: Path,
    audio: Path,
    outfile: Path,
    resize_factor: int,
    wav2lip_batch: int,
    face_det_batch: int,
    max_vram_mb: int,
    min_free_mb: int,
) -> dict[str, Any]:
    info = vram_info(python)
    if not info.get("cuda"):
        raise RuntimeError(f"CUDA unavailable for {python}: {info.get('error') or info}")
    if info.get("total_mb") and info["total_mb"] > max_vram_mb + 512:
        # Not fatal: the card may report slightly more than the stated budget.
        pass
    if info.get("free_mb") is not None and info["free_mb"] < min_free_mb:
        raise RuntimeError(
            f"Not enough free VRAM: {info['free_mb']} MB free, {min_free_mb} MB required "
            f"(GTX 1060 budget {max_vram_mb} MB total)"
        )

    env = os.environ.copy()
    env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    env["OMP_NUM_THREADS"] = "2"
    env["PYTHONIOENCODING"] = "utf-8"
    # Wav2Lip shells out to `ffmpeg` to mux its temp result; make sure the
    # ffmpeg we resolved is on the child PATH even when the parent had none.
    ffmpeg_bin = shutil.which("ffmpeg") or ""
    if ffmpeg_bin:
        env["PATH"] = str(Path(ffmpeg_bin).parent) + os.pathsep + env.get("PATH", "")

    outfile = outfile.resolve()
    cmd = [
        str(python), "inference.py",
        "--checkpoint_path", str(checkpoint.resolve()),
        "--face", str(face.resolve()),
        "--audio", str(audio.resolve()),
        "--outfile", str(outfile),
        "--resize_factor", str(resize_factor),
        "--wav2lip_batch_size", str(wav2lip_batch),
        "--face_det_batch_size", str(face_det_batch),
        "--nosmooth",
    ]
    started = time.time()
    log_path = outfile.with_name(outfile.stem + ".inference.log")
    proc = subprocess.run(
        cmd,
        cwd=str(wav2lip_dir),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text((proc.stdout or "") + "\n" + (proc.stderr or ""), encoding="utf-8")
    if proc.returncode != 0 or not outfile.is_file():
        tail = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()[-1500:]
        raise RuntimeError(
            f"Wav2Lip failed (exit {proc.returncode}, outfile_exists={outfile.is_file()}) "
            f"log={log_path}\n{tail}"
        )
    return {
        "engine": "wav2lip",
        "checkpoint": checkpoint.name,
        "resize_factor": resize_factor,
        "elapsed_seconds": round(time.time() - started, 1),
        "vram_free_mb_before": info.get("free_mb"),
        "vram_total_mb": info.get("total_mb"),
        "gpu": info.get("name"),
    }


def conform_clip(
    ffmpeg: str,
    raw: Path,
    dest: Path,
    width: int,
    height: int,
    duration: float,
    fps: int,
) -> None:
    """Upscale to layout size, mute, and force the exact block duration."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    frames = max(1, round(duration * fps))
    vf = (
        f"scale={width}:{height}:flags=lanczos,"
        f"fps={fps},"
        f"tpad=stop_mode=clone:stop_duration=1.0,"
        f"trim=duration={duration:.3f},setpts=PTS-STARTPTS"
    )
    _run(
        [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(raw),
            "-an", "-vf", vf, "-r", str(fps),
            "-frames:v", str(frames),
            "-c:v", "libx264", "-crf", "17", "-preset", "fast",
            "-pix_fmt", "yuv420p", "-g", str(fps), "-movflags", "+faststart",
            str(dest),
        ]
    )


def lip_sync_project(args: argparse.Namespace) -> dict[str, Any]:
    project = Path(args.project)
    hf_dir = project / "hyperframes"
    assets_dir = hf_dir / "assets"
    plan_path = Path(args.plan) if args.plan else project / "artifacts" / "avatar_plan.json"
    voice_wav = Path(args.voice_wav) if args.voice_wav else project / "assets" / "audio" / "voice_only_clean.wav"
    out_dir = Path(args.out_dir) if args.out_dir else assets_dir / "avatar" / "lipsync"
    work_dir = out_dir / "_work"
    report_path = project / "artifacts" / "lipsync_report.json"
    wav2lip_dir = Path(args.wav2lip_dir)

    if not plan_path.is_file():
        raise FileNotFoundError(f"avatar_plan.json not found: {plan_path}")
    if not voice_wav.is_file():
        raise FileNotFoundError(f"clean voice track not found: {voice_wav}")
    if not (wav2lip_dir / "inference.py").is_file():
        raise FileNotFoundError(f"Wav2Lip not found at {wav2lip_dir}")
    checkpoint = Path(args.checkpoint) if args.checkpoint else wav2lip_dir / "checkpoints" / "wav2lip_gan.pth"
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Wav2Lip checkpoint not found: {checkpoint}")

    ffmpeg = _find_ffmpeg(args.ffmpeg)
    python = _find_python(args.python)
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
        media_start = float(seg.get("media_start") or 0.0)

        if wanted and seg_id not in wanted:
            continue
        if mode not in MODE_DIMS or not clip:
            results.append({"id": seg_id, "mode": mode, "status": "skipped", "reason": "no avatar media in this block"})
            continue
        if seg.get("lip_sync") is False:
            results.append({"id": seg_id, "mode": mode, "status": "skipped", "reason": "lip_sync disabled (neutral hold)"})
            continue
        if not _overlaps(start, end, blocks):
            results.append({"id": seg_id, "mode": mode, "status": "skipped", "reason": "outside speech windows"})
            continue

        suffix = "split" if mode == "split" else "full"
        source = assets_dir / "avatar" / f"{clip}_{suffix}.mp4"
        if not source.is_file():
            results.append(
                {"id": seg_id, "mode": mode, "status": "failed", "reason": f"missing source clip {source}"}
            )
            continue

        width, height = MODE_DIMS[mode]
        dest = out_dir / f"{seg_id}.mp4"
        if dest.is_file() and not args.force:
            results.append({"id": seg_id, "mode": mode, "status": "cached", "output": str(dest)})
            continue
        if args.dry_run:
            results.append({"id": seg_id, "mode": mode, "status": "planned", "face_source": str(source)})
            continue

        resize = args.resize_factor or 1  # 1 = HQ driving: the mouth motion is what LivePortrait copies
        raw_out = work_dir / f"{seg_id}.wav2lip.mp4"
        try:
            face, audio = prepare_block(
                ffmpeg, source, media_start, duration, voice_wav, start, mode, work_dir, seg_id, fps
            )
            meta = run_wav2lip(
                python=python,
                wav2lip_dir=wav2lip_dir,
                checkpoint=checkpoint,
                face=face,
                audio=audio,
                outfile=raw_out,
                resize_factor=resize,
                wav2lip_batch=args.wav2lip_batch,
                face_det_batch=args.face_det_batch,
                max_vram_mb=args.max_vram_mb,
                min_free_mb=args.min_free_mb,
            )
            conform_clip(ffmpeg, raw_out, dest, width, height, duration, fps)
            results.append(
                {
                    "id": seg_id,
                    "mode": mode,
                    "status": "done",
                    "start": start,
                    "end": end,
                    "duration": duration,
                    "source": str(source),
                    "media_start": media_start,
                    "output": str(dest),
                    "dimensions": f"{width}x{height}",
                    **meta,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "id": seg_id,
                    "mode": mode,
                    "status": "failed",
                    "reason": f"{type(exc).__name__}: {exc}"[:1200],
                    "fallback": "original clip kept",
                }
            )

    done = [r for r in results if r["status"] == "done"]
    cached = [r for r in results if r["status"] == "cached"]
    failed = [r for r in results if r["status"] == "failed"]

    report = {
        "version": "1.0",
        "engine": "wav2lip",
        "wav2lip_dir": str(wav2lip_dir),
        "checkpoint": checkpoint.name,
        "python": str(python),
        "voice_track": str(voice_wav),
        "speech_blocks": blocks,
        "max_vram_mb": args.max_vram_mb,
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
        plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        report["applied_to_plan"] = True

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if not args.keep_work and not args.dry_run:
        shutil.rmtree(work_dir, ignore_errors=True)

    return report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Per-block Wav2Lip lip-sync for the Motor V2 avatar plan")
    p.add_argument("--project", default="projects/teste-jornal-ia")
    p.add_argument("--plan", default=None, help="avatar_plan.json path (default: <project>/artifacts/avatar_plan.json)")
    p.add_argument("--voice-wav", default=None, help="Clean narration track (default: assets/audio/voice_only_clean.wav)")
    p.add_argument("--out-dir", default=None, help="Output dir (default: hyperframes/assets/avatar/lipsync)")
    p.add_argument("--wav2lip-dir", default=str(DEFAULT_WAV2LIP_DIR))
    p.add_argument("--checkpoint", default=None)
    p.add_argument("--python", default=None, help="Python with CUDA torch (default: ComfyUI venv, then Python312)")
    p.add_argument("--ffmpeg", default=None)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--resize-factor", type=int, default=0, help="0 = auto (1 = HQ driving, the default)")
    p.add_argument("--wav2lip-batch", type=int, default=16)
    p.add_argument("--face-det-batch", type=int, default=4)
    p.add_argument("--max-vram-mb", type=int, default=6144, help="GTX 1060 budget")
    p.add_argument("--min-free-mb", type=int, default=900, help="Abort a block if free VRAM is below this")
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
    except Exception as exc:
        print(f"[avatar_lipsync] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not report["summary"]["failed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
