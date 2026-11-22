"""Ground-truth lip signal for the Motor V2 avatar (LivePortrait landmark model).

The earlier audit (`audit_lipsync.py`) correlated audio with *pixel difference* in the mouth
box, which mixes lip motion with head/hand motion and is noisy. This tool uses the actual
203-point landmark model shipped with LivePortrait
(`pretrained_weights/liveportrait/landmark.onnx`) and the same lip-closure ratio LivePortrait
uses internally:

    lip_ratio = || lmk[90] - lmk[102] || / || lmk[48] - lmk[66] ||

(inner-lip gap normalised by the mouth width, see
`LivePortrait/src/utils/retargeting_utils.py::calc_lip_close_ratio`).

With that signal per frame we can answer, with numbers:

- **sync**  — lag (in frames) between the narration envelope and the mouth. A positive lag means
  the mouth reacts *after* the audio (i.e. the video is late).
- **over-opening** — max/mean lip ratio compared with the source performance: how much the
  engine amplifies the mouth.
- **flattening** — dynamic range (p95 - p5) of the lip ratio: if the engine compresses it, the
  mouth looks "stuck half open" instead of articulating.

Usage (needs a Python with `onnxruntime` + `torch`, e.g. the ComfyUI venv):

    python tools/audit_lip_signal.py --project ./project \
        --liveportrait-dir "D:/Utilitarios/LivePortrait"

Outputs `<project>/artifacts/lip_signal.json` and a console table.
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

# Landmark indices used by LivePortrait's lip-retargeting (203-point model, crop space).
LIP_TOP, LIP_BOTTOM, MOUTH_LEFT, MOUTH_RIGHT = 90, 102, 48, 66


def _landmark_session(ckpt: Path, device: str):
    import onnxruntime

    providers = (
        ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if device == "cuda"
        else ["CPUExecutionProvider"]
    )
    return onnxruntime.InferenceSession(str(ckpt), providers=providers)


class _FaceDetector:
    """Face box detector: insightface (shipped with LivePortrait) with a cv2 fallback."""

    def __init__(self, liveportrait_dir: Path):
        self.app = None
        try:
            import sys as _sys

            if str(liveportrait_dir) not in _sys.path:
                _sys.path.insert(0, str(liveportrait_dir))
            from src.utils.face_analysis_diy import FaceAnalysisDIY  # type: ignore

            self.app = FaceAnalysisDIY(
                name="buffalo_l",
                root=str(liveportrait_dir / "pretrained_weights" / "insightface"),
                providers=["CPUExecutionProvider"],
            )
            self.app.prepare(ctx_id=-1, det_size=(512, 512), det_thresh=0.3)
        except Exception:
            self.app = None
        self.cascade = None
        try:
            self.cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
        except Exception:
            self.cascade = None

    def detect(self, frame_bgr: np.ndarray) -> Optional[tuple[int, int, int, int]]:
        if self.app is not None:
            try:
                faces = self.app.get(frame_bgr)
                if faces:
                    box = max(faces, key=lambda f: (f["bbox"][2] - f["bbox"][0]) * (f["bbox"][3] - f["bbox"][1]))["bbox"]
                    x0, y0, x1, y1 = (int(v) for v in box[:4])
                    return (x0, y0, x1 - x0, y1 - y0)
            except Exception:
                pass
        if self.cascade is not None:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            faces = self.cascade.detectMultiScale(gray, 1.08, 5, minSize=(80, 80))
            if len(faces):
                return tuple(int(v) for v in sorted(faces, key=lambda b: b[2] * b[3])[-1])
        return None


def _landmarks(session, img_bgr: np.ndarray, box: tuple[int, int, int, int], dsize: int = 224) -> Optional[np.ndarray]:
    x, y, w, h = box
    pad_x, pad_y = int(0.35 * w), int(0.35 * h)
    x0, y0 = max(0, x - pad_x), max(0, y - pad_y)
    x1, y1 = min(img_bgr.shape[1], x + w + pad_x), min(img_bgr.shape[0], y + h + pad_y)
    crop = img_bgr[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    crop = cv2.resize(crop, (dsize, dsize))
    inp = (crop.astype(np.float32) / 255.0).transpose(2, 0, 1)[None, ...]
    try:
        out = session.run(None, {"input": inp})
    except Exception:
        return None
    pts = np.asarray(out[2][0]).reshape(-1, 2)
    return pts * dsize


def _lip_series(session, detector: "_FaceDetector", path: Path, max_frames: Optional[int] = None) -> dict[str, Any]:
    cap = cv2.VideoCapture(str(path))
    ratios: list[float] = []
    widths: list[float] = []
    box = None
    frames = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames += 1
        if max_frames and frames > max_frames:
            break
        if box is None:
            box = detector.detect(frame)
            if box is None:
                ratios.append(np.nan)
                continue
        pts = _landmarks(session, frame, box)
        if pts is None or len(pts) <= LIP_BOTTOM:
            ratios.append(np.nan)
            continue
        gap = float(np.linalg.norm(pts[LIP_TOP] - pts[LIP_BOTTOM]))
        width = float(np.linalg.norm(pts[MOUTH_LEFT] - pts[MOUTH_RIGHT])) + 1e-6
        ratios.append(gap / width)
        widths.append(width)
    cap.release()
    arr = np.asarray(ratios, dtype=np.float32)
    valid = arr[~np.isnan(arr)]
    stats = {}
    if valid.size:
        stats = {
            "frames": int(frames),
            "valid_frames": int(valid.size),
            "min": round(float(np.min(valid)), 4),
            "max": round(float(np.max(valid)), 4),
            "mean": round(float(np.mean(valid)), 4),
            "p05": round(float(np.percentile(valid, 5)), 4),
            "p95": round(float(np.percentile(valid, 95)), 4),
            "range": round(float(np.percentile(valid, 95) - np.percentile(valid, 5)), 4),
        }
    return {"series": arr, "stats": stats, "face_box": box}


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


def _word_mask(project: Path, start: float, end: float, fps: int = 30) -> Optional[np.ndarray]:
    """Binary speech mask from word timestamps (onset-accurate; better than RMS for lag)."""
    path = project / "artifacts" / "captions_words.json"
    if not path.is_file():
        return None
    words = json.loads(path.read_text(encoding="utf-8"))
    n = int(round((end - start) * fps))
    mask = np.zeros(n, dtype=np.float32)
    for w in words:
        a = max(0, int(round((float(w["start"]) - start) * fps)))
        b = min(n, int(round((float(w["end"]) - start) * fps)))
        if b > a:
            mask[a:b] = 1.0
    return mask if mask.any() else None


def _lag(env: np.ndarray, series: np.ndarray, max_frames: int = 12) -> dict[str, Any]:
    n = min(len(env), len(series))
    env, series = env[:n], series[:n]
    mask = ~np.isnan(series)
    if mask.sum() < 15:
        return {}
    env = env[mask]
    series = series[mask]
    if env.std() == 0 or series.std() == 0:
        return {}
    env = (env - env.mean()) / env.std()
    series = (series - series.mean()) / series.std()
    scores = []
    for lag in range(-max_frames, max_frames + 1):
        if lag >= 0:
            a, b = env[lag:], series[: len(series) - lag]
        else:
            a, b = env[:lag], series[-lag:]
        m = min(len(a), len(b))
        if m < 12:
            continue
        scores.append((lag, float(np.dot(a[:m], b[:m]) / m)))
    if not scores:
        return {}
    best = max(scores, key=lambda s: s[1])
    zero = next((s[1] for s in scores if s[0] == 0), None)
    return {
        "lag_frames": best[0],
        "lag_ms": int(round(best[0] / 30.0 * 1000)),
        "corr_at_best": round(best[1], 3),
        "corr_at_zero": round(zero, 3) if zero is not None else None,
    }


def audit(args: argparse.Namespace) -> dict[str, Any]:
    project = Path(args.project)
    hf = project / "hyperframes"
    assets = hf / "assets" / "avatar"
    plan = json.loads((project / "artifacts" / "avatar_plan.json").read_text(encoding="utf-8"))
    voice = Path(args.voice_wav) if args.voice_wav else project / "assets" / "audio" / "voice_only_clean.wav"
    lp_dir = Path(args.liveportrait_dir)
    ckpt = lp_dir / "pretrained_weights" / "liveportrait" / "landmark.onnx"
    if not ckpt.is_file():
        raise FileNotFoundError(f"landmark model not found: {ckpt}")
    session = _landmark_session(ckpt, args.device)
    detector = _FaceDetector(lp_dir)
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
        candidates = {
            "source": assets / f"{seg.get('clip')}_{suffix}.mp4",
            "wav2lip": assets / "lipsync" / f"{seg_id}.mp4",
            "liveportrait": assets / "liveportrait" / f"{seg_id}.mp4",
        }
        env = _audio_envelope(ffmpeg, voice, float(seg["start"]), float(seg["end"]) - float(seg["start"]))
        mask = _word_mask(project, float(seg["start"]), float(seg["end"]))
        entry: dict[str, Any] = {"id": seg_id, "start": seg["start"], "end": seg["end"], "engines": {}}
        for engine, path in candidates.items():
            if not path.is_file():
                continue
            result = _lip_series(session, detector, path)
            data = {"file": str(path), "stats": result["stats"]}
            if engine != "source":
                data["sync"] = _lag(env, result["series"])
                if mask is not None:
                    data["sync_words"] = _lag(mask, result["series"])
                data["series"] = [None if np.isnan(v) else round(float(v), 4) for v in result["series"]]
            entry["engines"][engine] = data
        # normalise openness against the source performance
        base = entry["engines"].get("source", {}).get("stats", {})
        for engine, data in entry["engines"].items():
            if engine == "source" or not data.get("stats") or not base:
                continue
            data["openness_vs_source"] = round(data["stats"]["max"] / base["max"], 2) if base.get("max") else None
            data["range_vs_source"] = round(data["stats"]["range"] / base["range"], 2) if base.get("range") else None
        clips[seg_id] = entry

    report = {
        "version": "1.0",
        "method": {
            "lip_signal": "LivePortrait landmark.onnx (203 pts): inner-lip gap / mouth width",
            "sync": "normalized cross-correlation with the audio RMS envelope (30 Hz); "
                    "positive lag = mouth after audio = video late",
            "openness_vs_source": "max lip ratio / source max lip ratio",
            "range_vs_source": "(p95-p5) lip ratio / source (p95-p5) = articulation dynamics",
        },
        "voice_track": str(voice),
        "clips": clips,
    }
    out = project / "artifacts" / "lip_signal.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report["report_path"] = str(out)
    return report


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Landmark-based lip signal audit (sync + openness)")
    p.add_argument("--project", default="projects/teste-jornal-ia")
    p.add_argument("--voice-wav", default=None)
    p.add_argument("--ffmpeg", default=None)
    p.add_argument("--liveportrait-dir", default="D:/Utilitarios/LivePortrait")
    p.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    p.add_argument("--only", default=None)
    args = p.parse_args(argv)
    try:
        report = audit(args)
    except Exception as exc:  # noqa: BLE001
        print(f"[audit_lip_signal] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    for cid, c in report["clips"].items():
        print(f"\n{cid} ({c['start']}-{c['end']}s)")
        for engine, d in c["engines"].items():
            st = d.get("stats", {})
            line = (
                f"  {engine:12s} lip max={st.get('max')} mean={st.get('mean')} "
                f"range={st.get('range')}"
            )
            if d.get("openness_vs_source") is not None:
                line += f" | openness x{d['openness_vs_source']} range x{d['range_vs_source']}"
            if d.get("sync"):
                line += (
                    f" | lag {d['sync'].get('lag_frames')}f ({d['sync'].get('lag_ms')}ms) "
                    f"corr {d['sync'].get('corr_at_best')}"
                )
            if d.get("sync_words"):
                line += (
                    f" | words lag {d['sync_words'].get('lag_frames')}f "
                    f"({d['sync_words'].get('lag_ms')}ms) corr {d['sync_words'].get('corr_at_best')}"
                )
            print(line)
    print(f"\nreport: {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
