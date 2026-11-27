"""Automated layout-fill QA gate for 1080x1920 HyperFrames Shorts.

Detects dead horizontal bands inside the editorial zone (y = 152..1484 px, x = 48..1032 px)
split into 4 equal bands of 333 px each. Fails (exit code 1) if any band has
< 4.0% active non-background pixels AND < 0.45% edge density.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

BANDS = [
    (152, 485),
    (485, 818),
    (818, 1151),
    (1151, 1484),
]
X0, X1 = 48, 1032


def check_video(mp4_path: Path, timestamps: list[float]) -> bool:
    cap = cv2.VideoCapture(str(mp4_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {mp4_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = total_frames / fps if fps > 0 else 0.0

    if not timestamps:
        t = 2.0
        while t < duration - 0.5:
            timestamps.append(round(t, 2))
            t += 4.0

    all_ok = True
    for ts in timestamps:
        frame_idx = min(max(0, int(round(ts * fps))), max(0, total_frames - 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, frame = cap.read()
        if not ok or frame is None:
            print(f"[FAIL] t={ts:.2f}s could not read frame {frame_idx}")
            all_ok = False
            continue

        h, w = frame.shape[:2]
        if (w, h) != (1080, 1920):
            frame = cv2.resize(frame, (1080, 1920), interpolation=cv2.INTER_AREA)

        zone = frame[152:1484, X0:X1]
        # Scene background color = median across the editorial zone
        bg_rgb = np.median(zone.reshape(-1, 3), axis=0)
        edges = cv2.Canny(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), 50, 150)

        dead_bands = []
        band_stats = []
        for idx, (y0, y1) in enumerate(BANDS, 1):
            patch = frame[y0:y1, X0:X1].astype(np.float32)
            diff = np.max(np.abs(patch - bg_rgb[None, None, :]), axis=2)
            active_pct = float(np.mean(diff > 18.0)) * 100.0
            edge_pct = float(np.mean(edges[y0:y1, X0:X1] > 0)) * 100.0
            band_stats.append(f"B{idx}({y0}-{y1}): act={active_pct:.1f}% edg={edge_pct:.2f}%")
            if active_pct < 4.0 and edge_pct < 0.45:
                dead_bands.append(f"B{idx}({y0}-{y1})")

        status = "PASS" if not dead_bands else f"FAIL [dead: {', '.join(dead_bands)}]"
        if dead_bands:
            all_ok = False
        print(f"t={ts:5.2f}s | {status:34s} | " + " | ".join(band_stats))

    cap.release()
    return all_ok


def main() -> int:
    p = argparse.ArgumentParser(description="Audit 1080x1920 Short frames for dead vertical bands.")
    p.add_argument("--mp4", type=Path, required=True, help="Path to rendered MP4")
    p.add_argument("--timestamps", type=str, default="", help="Comma-separated timestamps in seconds")
    args = p.parse_args()

    ts_list = [float(x.strip()) for x in args.timestamps.split(",") if x.strip()] if args.timestamps else []
    ok = check_video(args.mp4.expanduser().resolve(), ts_list)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
