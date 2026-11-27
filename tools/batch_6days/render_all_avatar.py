"""Batched V17C Avatar renderer for all 6 Shorts (single model load across all pending Shorts)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw

REPO_ROOT = Path(r"D:\Utilitarios\avatar-journal")
OUT_ROOT = REPO_ROOT / "output" / "2026-11-26"
AVATAR_PY = Path(r"D:\Utilitarios\gerador-avatar\generate_avatar.py")
COMFY_PY = r"D:\Comfy\ComfyUI\venv\Scripts\python.exe"
FFMPEG = r"D:\Utilitarios\ffmpeg\bin\ffmpeg.exe"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.batch_6days.specs import SHORTS_6DAYS  # noqa: E402
from tools.voicestudio_tts import flush_memory  # noqa: E402


def build_combined_avatar_qa(specs: list[dict]) -> None:
    rows_img = []
    for spec in specs:
        p = OUT_ROOT / spec["slug"] / "avatar_out" / "avatar_v17c_audit.png"
        if not p.is_file():
            continue
        im = Image.open(p).convert("RGB")
        im = im.resize((1200, int(im.height * (1200 / im.width))), Image.Resampling.LANCZOS)
        dr = ImageDraw.Draw(im)
        dr.rectangle([0, 0, 340, 32], fill=(8, 12, 22))
        dr.text((10, 8), f"{spec['day_short']} · {spec['slug']}", fill=(248, 250, 252))
        rows_img.append(im)
    if not rows_img:
        return
    total_h = sum(im.height for im in rows_img)
    sheet = Image.new("RGB", (1200, total_h), (6, 8, 14))
    y = 0
    for im in rows_img:
        sheet.paste(im, (0, y))
        y += im.height
    out = OUT_ROOT / "all6_avatar_qa.png"
    sheet.save(out)
    print(f"[OK] Saved consolidated avatar QA -> {out}", flush=True)


def make_per_short_audit_grid(seg1_mp4: Path, seg2_mp4: Path, out_png: Path, tmp_dir: Path) -> None:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tiles = []
    for label, mp4 in [("seg_01", seg1_mp4), ("seg_02", seg2_mp4)]:
        for idx, frac in enumerate([0.08, 0.25, 0.45, 0.65, 0.82, 0.94]):
            out_f = tmp_dir / f"{label}_{idx}.png"
            ts_cmd = subprocess.check_output(
                [r"D:\Utilitarios\ffmpeg\bin\ffprobe.exe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(mp4)],
                text=True,
            ).strip()
            dur = max(0.2, float(ts_cmd))
            t = round(dur * frac, 3)
            subprocess.run(
                [FFMPEG, "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(mp4), "-frames:v", "1", str(out_f)],
                check=True,
            )
            im = Image.open(out_f).convert("RGB").resize((360, 192), Image.Resampling.LANCZOS)
            dr = ImageDraw.Draw(im)
            dr.text((10, 8), f"{label} t={t:.2f}s", fill=(34, 197, 94))
            tiles.append(im)
    grid = Image.new("RGB", (360 * 6, 192 * 2), (6, 8, 14))
    for i, im in enumerate(tiles):
        grid.paste(im, ((i % 6) * 360, (i // 6) * 192))
    grid.save(out_png)


def main() -> int:
    os.environ["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PATH"] = r"D:\Utilitarios\ffmpeg\bin;" + os.environ.get("PATH", "")

    flush_res = flush_memory()
    print("[Avatar Batch] VoiceStudio VRAM flush:", flush_res, flush=True)

    only = {a.strip() for a in sys.argv[1:] if a.strip()}
    pending: list[dict] = []
    for spec in SHORTS_6DAYS:
        slug = spec["slug"]
        if only and slug not in only and spec["day_key"] not in only:
            continue
        sdir = OUT_ROOT / slug
        av_dir = sdir / "avatar_out"
        needed = [av_dir / "avatar_seg_01.mp4", av_dir / "avatar_seg_02.mp4", av_dir / "avatar_hold_bar.mp4"]
        audit_png = av_dir / "avatar_v17c_audit.png"
        if all(p.is_file() and p.stat().st_size > 20000 for p in needed) and audit_png.is_file():
            print(f"[{slug}] REUSE avatar_out", flush=True)
            continue
        pending.append(spec)

    if len(pending) == 1:
        spec = pending[0]
        slug = spec["slug"]
        sdir = OUT_ROOT / slug
        timings = json.loads((sdir / "audio" / "timings.json").read_text(encoding="utf-8"))
        segs = timings["segments"]
        seg_arg = f"0.0:{float(segs[1]['start']):.3f},{float(segs[3]['start']):.3f}:{float(segs[3]['end']):.3f}"
        av_dir = sdir / "avatar_out"
        av_dir.mkdir(parents=True, exist_ok=True)
        print(f"[{slug}] Single V17C Avatar ({seg_arg})...", flush=True)
        subprocess.run(
            [
                COMFY_PY, str(AVATAR_PY),
                "--audio", timings["final_mix_wav"],
                "--segments", seg_arg,
                "--bottom-bar-height", "576",
                "--out-dir", str(av_dir),
                "--audit-png", str(av_dir / "avatar_v17c_audit.png"),
            ],
            check=True,
        )
    elif len(pending) > 1:
        # Single-load batched execution across all pending Shorts (avoids ~12m startup x N!)
        batch_dir = OUT_ROOT / "_avatar_batch"
        batch_dir.mkdir(parents=True, exist_ok=True)
        concat_txt = batch_dir / "concat.txt"
        combined_wav = batch_dir / "combined_mix.wav"

        lines = []
        seg_windows = []
        mapping = []
        cursor = 0.0
        for spec in pending:
            slug = spec["slug"]
            sdir = OUT_ROOT / slug
            timings = json.loads((sdir / "audio" / "timings.json").read_text(encoding="utf-8"))
            wav_p = Path(timings["final_mix_wav"])
            with wave.open(str(wav_p), "rb") as w:
                wav_dur = w.getnframes() / float(w.getframerate())
            segs = timings["segments"]
            s0_end = float(segs[1]["start"])
            s3_start = float(segs[3]["start"])
            s3_end = float(segs[3]["end"])
            seg_windows.append(f"{cursor:.3f}:{cursor + s0_end:.3f}")
            seg_windows.append(f"{cursor + s3_start:.3f}:{cursor + s3_end:.3f}")
            mapping.append(spec)
            lines.append(f"file '{wav_p.as_posix()}'")
            cursor += wav_dur

        concat_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
        subprocess.run(
            [FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(combined_wav)],
            check=True,
        )

        seg_arg = ",".join(seg_windows)
        print(f"[Avatar Batch] Single-pass V17C for {len(pending)} Shorts ({len(seg_windows)} segments): {seg_arg}", flush=True)
        subprocess.run(
            [
                COMFY_PY, str(AVATAR_PY),
                "--audio", str(combined_wav),
                "--segments", seg_arg,
                "--bottom-bar-height", "576",
                "--out-dir", str(batch_dir),
                "--audit-png", str(batch_dir / "batch_audit.png"),
            ],
            check=True,
        )

        hold_src = batch_dir / "avatar_hold_bar.mp4"
        for idx, spec in enumerate(mapping):
            av_dir = OUT_ROOT / spec["slug"] / "avatar_out"
            av_dir.mkdir(parents=True, exist_ok=True)
            s1_src = batch_dir / f"avatar_seg_{idx * 2 + 1:02d}.mp4"
            s2_src = batch_dir / f"avatar_seg_{idx * 2 + 2:02d}.mp4"
            s1_dst = av_dir / "avatar_seg_01.mp4"
            s2_dst = av_dir / "avatar_seg_02.mp4"
            shutil.copy2(s1_src, s1_dst)
            shutil.copy2(s2_src, s2_dst)
            shutil.copy2(hold_src, av_dir / "avatar_hold_bar.mp4")
            make_per_short_audit_grid(s1_dst, s2_dst, av_dir / "avatar_v17c_audit.png", av_dir / "_qa_tmp")
            print(f"[{spec['slug']}] Unpacked avatar_out + audit PNG", flush=True)

    build_combined_avatar_qa(SHORTS_6DAYS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
