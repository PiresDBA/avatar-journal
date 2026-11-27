"""End-to-end orchestrator: jornalismo-ia-shorts-pro `pauta.json` -> `avatar-journal` MP4.

Runs the full local pipeline for a selected short from `pauta.json`:
  1. plan          -> `tools/pauta_to_plan.py` (pauta.json -> avatar_plan.json + voiceover.txt + tag lint)
  2. tts           -> `tools/voice_craft_tts.py` (VoiceStudio :3900 / Piper fallback -> voice_only_clean.wav)
  3. slot          -> `tools/avatar_slot.py` (mounts catalog clips into HyperFrames)
  4. lipsync       -> `tools/avatar_lipsync.py --apply` (Wav2Lip driving, 1 process per block)
  5. liveportrait  -> `tools/avatar_liveportrait.py --apply` (pixels + mouth-only composite, shift 5, mult 0.7)
  6. render        -> HyperFrames gates (`lint`, `validate`, `inspect`, `render --strict`)
  7. audit         -> optional (`--audit`): `tools/audit_lipsync.py` + `tools/audit_lip_signal.py`

Use `--dry-run` to preview the exact step-by-step commands and validate `pauta.json`
without writing files or touching the GPU.
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

REPO_ROOT = Path(__file__).resolve().parent.parent
STEPS = ["plan", "tts", "slot", "lipsync", "liveportrait", "render", "audit"]


def _resolve_npx() -> str:
    if os.name == "nt":
        found = shutil.which("npx.cmd") or shutil.which("npx")
        return found or "npx.cmd"
    return shutil.which("npx") or "npx"


def _step_slice(from_step: str, to_step: str, include_audit: bool) -> list[str]:
    start_i = STEPS.index(from_step)
    end_i = STEPS.index(to_step)
    if end_i < start_i:
        raise ValueError(f"--to-step ({to_step}) cannot precede --from-step ({from_step})")
    selected = STEPS[start_i : end_i + 1]
    if not include_audit and "audit" in selected and to_step != "audit":
        selected = [s for s in selected if s != "audit"]
    return selected


def _build_commands(args: argparse.Namespace, selected_steps: list[str]) -> list[dict[str, Any]]:
    py = sys.executable
    tools_dir = REPO_ROOT / "tools"
    project_dir = Path(args.project).expanduser().resolve()
    artifacts_dir = project_dir / "artifacts"
    plan_path = artifacts_dir / "avatar_plan.json"
    voiceover_path = artifacts_dir / "voiceover.txt"
    voice_wav = project_dir / "assets" / "audio" / "voice_only_clean.wav"
    avatar_v17b_mp4 = project_dir / "assets" / "video" / "avatar_v17b.mp4"
    gerador_dir = Path(args.gerador_avatar_dir).expanduser().resolve()
    gerador_py = Path(r"D:\Comfy\ComfyUI\venv\Scripts\python.exe")
    hf_dir = project_dir / "hyperframes"
    npx = _resolve_npx()

    jobs: list[dict[str, Any]] = []

    if "plan" in selected_steps:
        cmd = [
            py,
            str(tools_dir / "pauta_to_plan.py"),
            "--pauta",
            str(Path(args.pauta).expanduser().resolve()),
            "--project",
            str(project_dir),
            "--fps",
            str(args.fps),
            "--max-block-sec",
            str(args.max_block_sec),
            "--hold-sec",
            str(args.hold_sec),
            "--tts-provider",
            args.tts_provider,
        ]
        if args.short:
            cmd.extend(["--short", args.short])
        if args.duration is not None:
            cmd.extend(["--duration", str(args.duration)])
        if args.engine:
            cmd.extend(["--engine", args.engine])
        if args.compositor:
            cmd.extend(["--compositor", args.compositor])
        if args.strict_tags:
            cmd.append("--strict-tags")
        if args.dry_run:
            cmd.append("--dry-run")
        jobs.append({"step": "plan", "cwd": str(REPO_ROOT), "cmd": cmd, "run_in_dry_run": True})

    if "tts" in selected_steps and not args.skip_tts:
        cmd = [
            py,
            str(tools_dir / "voicestudio_tts.py"),
            "--text-file",
            str(voiceover_path),
            "--out",
            str(voice_wav),
            "--voice",
            args.voice,
            "--engine",
            args.tts_engine,
        ]
        if args.tts_instruct:
            cmd.extend(["--instruct", args.tts_instruct])
        if args.seed is not None:
            cmd.extend(["--seed", str(args.seed)])
        if args.style and not args.tts_instruct:
            cmd.extend(["--instruct", args.style])
        jobs.append({"step": "tts", "cwd": str(REPO_ROOT), "cmd": cmd})

    if "slot" in selected_steps:
        cmd = [
            py,
            str(tools_dir / "avatar_slot.py"),
            "--project",
            str(project_dir),
            "--avatar-dir",
            str(Path(args.avatar_dir).expanduser()),
            "--plan",
            str(plan_path),
            "--fps",
            str(args.fps),
        ]
        if args.force:
            cmd.append("--force")
        jobs.append({"step": "slot", "cwd": str(REPO_ROOT), "cmd": cmd})

    if "lipsync" in selected_steps:
        if args.avatar_engine == "gerador-avatar":
            v17b_py = str(gerador_py) if gerador_py.exists() else py
            cmd = [
                v17b_py,
                str(gerador_dir / "generate_avatar.py"),
                "--video",
                str(Path(args.avatar_video).expanduser()),
                "--audio",
                str(voice_wav),
                "--fps",
                str(args.fps),
                "--out",
                str(avatar_v17b_mp4),
            ]
            jobs.append({"step": "lipsync:gerador-avatar-v17b", "cwd": str(gerador_dir), "cmd": cmd})
        else:
            cmd = [
                py,
                str(tools_dir / "avatar_lipsync.py"),
                "--project",
                str(project_dir),
                "--plan",
                str(plan_path),
                "--voice-wav",
                str(voice_wav),
                "--fps",
                str(args.fps),
                "--apply",
            ]
            if args.force:
                cmd.append("--force")
            jobs.append({"step": "lipsync", "cwd": str(REPO_ROOT), "cmd": cmd})

    if "liveportrait" in selected_steps and args.avatar_engine != "gerador-avatar":
        cmd = [
            py,
            str(tools_dir / "avatar_liveportrait.py"),
            "--project",
            str(project_dir),
            "--plan",
            str(plan_path),
            "--fps",
            str(args.fps),
            "--animation-region",
            args.animation_region,
            "--driving-multiplier",
            str(args.driving_multiplier),
            "--drive-shift-frames",
            str(args.drive_shift_frames),
            "--apply",
        ]
        if args.force:
            cmd.append("--force")
        jobs.append({"step": "liveportrait", "cwd": str(REPO_ROOT), "cmd": cmd})

    if "render" in selected_steps and not args.skip_render:
        for gate in (
            ["hyperframes", "lint", "--json"],
            ["hyperframes", "validate", "--json"],
            ["hyperframes", "inspect", "--json"],
            ["hyperframes", "render", "--strict"],
        ):
            jobs.append({"step": f"render:{gate[1]}", "cwd": str(hf_dir), "cmd": [npx, *gate]})

    if "audit" in selected_steps:
        jobs.append(
            {
                "step": "audit:pixels",
                "cwd": str(REPO_ROOT),
                "cmd": [py, str(tools_dir / "audit_lipsync.py"), "--project", str(project_dir)],
            }
        )
        jobs.append(
            {
                "step": "audit:landmarks",
                "cwd": str(REPO_ROOT),
                "cmd": [py, str(tools_dir / "audit_lip_signal.py"), "--project", str(project_dir)],
            }
        )

    return jobs


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run the full avatar-journal pipeline starting from a jornalismo-ia-shorts-pro pauta.json."
    )
    p.add_argument("--pauta", required=True, help="Path to pauta.json")
    p.add_argument("--short", default=None, help="Short ID inside pauta.json (default: first short)")
    p.add_argument("--project", default="./project", help="Project directory (default: ./project)")
    p.add_argument("--avatar-dir", default=r"D:\PROJETOS-IA\AVATAR", help="Directory with catalog avatar clips")
    p.add_argument(
        "--avatar-engine",
        default="gerador-avatar",
        choices=["gerador-avatar", "wav2lip-liveportrait"],
        help="Local avatar engine (default: gerador-avatar V17B)",
    )
    p.add_argument(
        "--avatar-video",
        default=r"D:\Utilitarios\gerador-avatar\assets\avatar_base_9x16_30fps.mp4",
        help="Base calm 9:16 30fps video for gerador-avatar V17C",
    )
    p.add_argument(
        "--gerador-avatar-dir",
        default=r"D:\Utilitarios\gerador-avatar",
        help="Path to standalone gerador-avatar package",
    )
    p.add_argument("--voice", default="Ale-empolgado", help="VoiceStudio voice profile (default: Ale-empolgado)")
    p.add_argument("--tts-provider", default="voicestudio", help="TTS provider (default: voicestudio)")
    p.add_argument("--tts-engine", default="omnivoice", help="VoiceStudio engine: omnivoice, voxcpm2, etc.")
    p.add_argument("--tts-instruct", default=None, help="Optional VoiceStudio --instruct emotion/delivery prompt")
    p.add_argument("--style", default=None, help="Optional TTS style alias (e.g., whisper)")
    p.add_argument("--seed", type=int, default=None, help="Optional TTS seed for reproducible takes")
    p.add_argument("--paragraph-gap-ms", type=int, default=None, help="Optional pause between paragraphs in ms")
    p.add_argument("--keep-silences", action="store_true", help="Keep breath-length silences in TTS output")
    p.add_argument("--strict-tags", action="store_true", help="Abort if unsupported TTS tags are present")
    p.add_argument("--duration", type=float, default=None, help="Optional duration override in seconds")
    p.add_argument("--fps", type=int, default=30, help="Target FPS (default: 30)")
    p.add_argument("--max-block-sec", type=float, default=5.5, help="Max speaking block seconds (default: 5.5)")
    p.add_argument("--hold-sec", type=float, default=0.64, help="Final closed-mouth hold seconds (default: 0.64)")
    p.add_argument("--engine", default=None, choices=["avatar-journal", "blender-hybrid", "reallusion"])
    p.add_argument("--compositor", default=None, choices=["hyperframes", "openmontage", "remotion"])
    p.add_argument("--animation-region", default="lip", choices=["lip", "exp", "pose", "eyes", "all"])
    p.add_argument("--driving-multiplier", type=float, default=0.7, help="LivePortrait lip multiplier (default: 0.7)")
    p.add_argument("--drive-shift-frames", type=int, default=5, help="LivePortrait driving shift frames (default: 5)")
    p.add_argument("--from-step", default="plan", choices=STEPS, help="Start pipeline at this step")
    p.add_argument("--to-step", default="render", choices=STEPS, help="Stop pipeline after this step")
    p.add_argument("--skip-tts", action="store_true", help="Skip TTS step (reuse existing voice_only_clean.wav)")
    p.add_argument("--skip-render", action="store_true", help="Skip HyperFrames gates & render")
    p.add_argument("--audit", action="store_true", help="Run audit_lipsync.py and audit_lip_signal.py at the end")
    p.add_argument("--force", action="store_true", help="Force re-encoding/re-inference of cached clips")
    p.add_argument("--dry-run", action="store_true", help="Validate pauta.json and print commands without executing GPU/render")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    include_audit = args.audit or args.to_step == "audit"
    to_step = "audit" if args.audit and args.to_step == "render" else args.to_step
    selected = _step_slice(args.from_step, to_step, include_audit=include_audit)
    jobs = _build_commands(args, selected)

    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
    ffmpeg_bin = r"D:\Utilitarios\ffmpeg\bin"
    if ffmpeg_bin not in env.get("PATH", ""):
        env["PATH"] = f"{ffmpeg_bin};{env.get('PATH', '')}"

    results: list[dict[str, Any]] = []
    for job in jobs:
        step = job["step"]
        cmd = job["cmd"]
        cwd = job["cwd"]

        if args.dry_run and not job.get("run_in_dry_run"):
            results.append({"step": step, "status": "planned", "cwd": cwd, "cmd": cmd})
            continue

        t0 = time.monotonic()
        proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, check=False)
        elapsed = round(time.monotonic() - t0, 2)
        entry: dict[str, Any] = {
            "step": step,
            "status": "ok" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "elapsed_s": elapsed,
            "cwd": cwd,
            "cmd": cmd,
        }
        if proc.stdout.strip():
            try:
                entry["output"] = json.loads(proc.stdout)
            except json.JSONDecodeError:
                entry["stdout_tail"] = proc.stdout.strip()[-600:]
        if proc.stderr.strip():
            entry["stderr_tail"] = proc.stderr.strip()[-600:]
        results.append(entry)

        if proc.returncode != 0:
            print(json.dumps({"dry_run": args.dry_run, "steps": results}, indent=2, ensure_ascii=False))
            return proc.returncode

    print(json.dumps({"dry_run": args.dry_run, "steps": results}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
