"""Synthesize 6 PT-BR Shorts audio tracks via native VoiceStudio CLI/HTTP + flush VRAM + measure with earshot."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import wave
from pathlib import Path

REPO_ROOT = Path(r"D:\Utilitarios\avatar-journal")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.batch_6days.specs import SHORTS_6DAYS  # noqa: E402
from tools.voicestudio_tts import VoiceStudioTTS, flush_memory  # noqa: E402

OUT_ROOT = REPO_ROOT / "output" / "2026-11-26"
FFMPEG = r"D:\Utilitarios\ffmpeg\bin\ffmpeg.exe"
VOICE = "Ale-empolgado-15s"
ENGINE = "omnivoice"


def trim_and_resample(src: Path, dst: Path) -> float:
    subprocess.run(
        [
            FFMPEG, "-y", "-v", "error", "-i", str(src),
            "-af",
            "silenceremove=start_periods=1:start_silence=0.05:start_threshold=-45dB,"
            "areverse,silenceremove=start_periods=1:start_silence=0.05:start_threshold=-45dB,areverse,"
            "aresample=48000",
            "-ac", "2", "-c:a", "pcm_s16le", str(dst),
        ],
        check=True,
    )
    with wave.open(str(dst), "rb") as w:
        return round(w.getnframes() / float(w.getframerate()), 3)


def make_silence(dur: float, dst: Path) -> None:
    subprocess.run(
        [
            FFMPEG, "-y", "-v", "error",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-t", f"{dur:.3f}", "-c:a", "pcm_s16le", str(dst),
        ],
        check=True,
    )


def build_short_audio(spec: dict, tts: VoiceStudioTTS) -> dict:
    sdir = OUT_ROOT / spec["slug"]
    adir = sdir / "audio"
    adir.mkdir(parents=True, exist_ok=True)

    # Write verified YouTube metadata & links immediately
    (sdir / "youtube_metadata.json").write_text(
        json.dumps(
            {
                "slug": spec["slug"],
                "day_key": spec["day_key"],
                "db_id": spec["db_id"],
                "program": spec["program"],
                "style": spec["style"],
                "youtube": spec["youtube"],
                "official_links": spec["official_links"],
            },
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    gap = 0.18
    tail_hold = 0.65
    gap_wav = adir / "silence_gap.wav"
    tail_wav = adir / "silence_tail.wav"
    make_silence(gap, gap_wav)
    make_silence(tail_hold, tail_wav)

    concat_list: list[Path] = []
    segments: list[dict] = []
    cursor = 0.0

    for idx, (seg_id, text) in enumerate(spec["blocks"]):
        raw_wav = adir / f"{seg_id}_raw.wav"
        clean_wav = adir / f"{seg_id}.wav"
        if clean_wav.is_file() and clean_wav.stat().st_size > 16000:
            with wave.open(str(clean_wav), "rb") as w:
                dur = round(w.getnframes() / float(w.getframerate()), 3)
            print(f"[{spec['slug']}] REUSE {seg_id} ({dur}s)", flush=True)
        else:
            print(f"[{spec['slug']}] TTS {seg_id}...", flush=True)
            res = tts.execute({
                "text": text,
                "output_path": str(raw_wav),
                "voice": VOICE,
                "engine": ENGINE,
                "language": "pt",
                "fallback_to_piper": False,
                "request_timeout": 600.0,
            })
            if not res.success:
                raise RuntimeError(f"TTS failed on {spec['slug']}/{seg_id}: {res.error}")
            dur = trim_and_resample(raw_wav, clean_wav)
            print(f"  -> {dur}s ({res.data.get('transport_used')})", flush=True)

        start = round(cursor, 3)
        end = round(cursor + dur, 3)
        segments.append({"id": seg_id, "start": start, "end": end, "duration": dur, "text": text})
        concat_list.append(clean_wav)
        cursor = end
        if idx < len(spec["blocks"]) - 1:
            concat_list.append(gap_wav)
            cursor = round(cursor + gap, 3)

    concat_list.append(tail_wav)
    total_dur = round(cursor + tail_hold, 3)

    concat_txt = adir / "concat.txt"
    concat_txt.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in concat_list) + "\n",
        encoding="utf-8",
    )
    raw_full = adir / "voiceover_raw_concat.wav"
    voiceover_full = adir / "voiceover_full.wav"
    subprocess.run(
        [FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(raw_full)],
        check=True,
    )
    subprocess.run(
        [
            FFMPEG, "-y", "-v", "error", "-i", str(raw_full),
            "-af", "loudnorm=I=-14:TP=-1.5:LRA=7",
            "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(voiceover_full),
        ],
        check=True,
    )

    hz1 = float(spec["style"]["hz1"])
    hz2 = float(spec["style"]["hz2"])
    final_mix = adir / "final_mix.wav"
    subprocess.run(
        [
            FFMPEG, "-y", "-v", "error",
            "-i", str(voiceover_full),
            "-f", "lavfi",
            "-i", f"aevalsrc=0.025*sin(2*PI*{hz1}*t)+0.012*sin(2*PI*{hz2}*t):s=48000:c=stereo:d={total_dur:.3f}",
            "-filter_complex",
            f"[1:a]lowpass=f=240,afade=t=in:st=0:d=0.6,afade=t=out:st={max(0.0, total_dur - 1.0):.3f}:d=1.0[bed];"
            "[0:a][bed]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mix]",
            "-map", "[mix]", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(final_mix),
        ],
        check=True,
    )

    timings = {
        "slug": spec["slug"],
        "total_duration": total_dur,
        "voiceover_wav": str(voiceover_full),
        "final_mix_wav": str(final_mix),
        "segments": segments,
    }
    (adir / "timings.json").write_text(json.dumps(timings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return timings


def main() -> int:
    os.environ["PATH"] = r"D:\Utilitarios\ffmpeg\bin;" + os.environ.get("PATH", "")
    tts = VoiceStudioTTS()
    only = {a.strip() for a in sys.argv[1:] if a.strip()}
    summary = []
    try:
        for spec in SHORTS_6DAYS:
            if only and spec["slug"] not in only and spec["day_key"] not in only:
                continue
            t = build_short_audio(spec, tts)
            summary.append({"slug": spec["slug"], "duration": t["total_duration"]})
    finally:
        fl = flush_memory()
        print("VoiceStudio VRAM flush:", fl, flush=True)

    print("AUDIO BATCH SUMMARY:", json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
