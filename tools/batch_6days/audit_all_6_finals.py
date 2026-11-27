"""Run layout-fill QA and build multi-cut + final-frame QA contact sheets for all 6 Shorts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

REPO_ROOT = Path(r"D:\Utilitarios\avatar-journal")
OUT_ROOT = REPO_ROOT / "output" / "2026-11-26"
ARTIFACT_DIR = Path(r"C:\Users\Pires\.gemini\antigravity\brain\0817253a-6bab-45c9-92c8-9fc43806cc95")
FFMPEG = r"D:\Utilitarios\ffmpeg\bin\ffmpeg.exe"
FFPROBE = r"D:\Utilitarios\ffmpeg\bin\ffprobe.exe"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.audit_layout_fill import check_video  # noqa: E402
from tools.batch_6days.specs import SHORTS_6DAYS  # noqa: E402


def probe_mp4(mp4_path: Path) -> dict:
    raw = subprocess.check_output(
        [
            FFPROBE, "-v", "error", "-show_entries",
            "format=duration,size:stream=codec_type,width,height,r_frame_rate",
            "-of", "json", str(mp4_path),
        ],
        text=True,
        encoding="utf-8",
    )
    return json.loads(raw)


def extract_frame(mp4_path: Path, ts: float, out_png: Path) -> None:
    subprocess.run(
        [FFMPEG, "-y", "-v", "error", "-ss", f"{ts:.3f}", "-i", str(mp4_path), "-frames:v", "1", str(out_png)],
        check=True,
    )


def build_qa_for_short(spec: dict) -> tuple[bool, Path, dict]:
    slug = spec["slug"]
    sdir = OUT_ROOT / slug
    mp4 = sdir / f"final_{slug}.mp4"
    if not mp4.is_file():
        raise FileNotFoundError(f"Missing final MP4: {mp4}")

    timings = json.loads((sdir / "audio" / "timings.json").read_text(encoding="utf-8"))
    segs = timings["segments"]
    total = float(timings["total_duration"])

    # Sample opening, cut transition, block A mid, block B mid, closing, and final resting frame
    sample_ts = [
        1.20,
        round(float(segs[1]["start"]) + 0.30, 2),
        round(float(segs[1]["start"]) + float(segs[1]["duration"]) * 0.55, 2),
        round(float(segs[2]["start"]) + float(segs[2]["duration"]) * 0.55, 2),
        round(float(segs[3]["start"]) + 1.00, 2),
        round(max(0.5, total - 0.10), 2),
    ]

    print(f"\n=== AUDIT LAYOUT FILL: {slug} ===", flush=True)
    ok_layout = check_video(mp4, sample_ts)

    qa_dir = sdir / "qa_frames"
    qa_dir.mkdir(parents=True, exist_ok=True)
    tw, th = 270, 480
    tiles = []
    for idx, ts in enumerate(sample_ts):
        fpng = qa_dir / f"cut_{idx:02d}.png"
        extract_frame(mp4, ts, fpng)
        im = Image.open(fpng).convert("RGB").resize((tw, th), Image.Resampling.LANCZOS)
        dr = ImageDraw.Draw(im)
        dr.rectangle([0, 0, tw, 28], fill=(8, 12, 22))
        dr.text((8, 6), f"{spec['day_short']} t={ts:.2f}s", fill=(248, 250, 252))
        tiles.append(im)

    strip = Image.new("RGB", (tw * len(tiles), th), (6, 8, 14))
    for i, im in enumerate(tiles):
        strip.paste(im, (i * tw, 0))
    strip_path = sdir / "all_cuts_qa.png"
    strip.save(strip_path)
    meta = probe_mp4(mp4)
    return ok_layout, strip_path, meta


def main() -> int:
    only = {a.strip() for a in sys.argv[1:] if a.strip()}
    strips: list[Path] = []
    results = []
    all_ok = True
    for spec in SHORTS_6DAYS:
        if only and spec["slug"] not in only and spec["day_key"] not in only:
            continue
        ok_layout, strip_path, meta = build_qa_for_short(spec)
        all_ok = all_ok and ok_layout
        strips.append(strip_path)
        results.append({
            "slug": spec["slug"],
            "layout_ok": ok_layout,
            "duration": meta["format"].get("duration"),
            "size_mb": round(int(meta["format"].get("size", 0)) / (1024 * 1024), 2),
            "strip": str(strip_path),
        })

    if strips:
        rows = [Image.open(p).convert("RGB") for p in strips]
        w = max(r.width for r in rows)
        h = sum(r.height for r in rows)
        combined = Image.new("RGB", (w, h), (6, 8, 14))
        y = 0
        for r in rows:
            combined.paste(r, (0, y))
            y += r.height
        out_root_qa = OUT_ROOT / "all6_shorts_final_qa.png"
        combined.save(out_root_qa)
        if ARTIFACT_DIR.is_dir():
            combined.save(ARTIFACT_DIR / "all6_shorts_final_qa.png")

    print("\nFINAL 6-SHORT AUDIT SUMMARY:", json.dumps(results, indent=2), flush=True)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
