"""Bridge from jornalismo-ia-shorts-pro `pauta.json` to `avatar-journal` production artifacts.

Converts a selected short from `pauta.json` into:
  1. `<project>/artifacts/avatar_plan.json` — canonical Dynamic Avatar Director plan
     compatible with `avatar_slot.py`, `avatar_lipsync.py`, and `avatar_liveportrait.py`.
  2. `<project>/artifacts/voiceover.txt` — narration text ready for `voicestudio_tts.py --text-file`.
  3. `<project>/artifacts/short_brief.json` — editorial metadata, fact-verification flags,
     visual assets, TTS tag lint report, and optional Blender/Reallusion/Remotion hooks.

Core guarantees:
  - Dynamic Avatar Director: alternates `full_avatar`, `split`, and `full_graphics`/`broll`
    so the avatar never stays static for the entire video nor disappears completely.
  - GTX 1060 6 GB budget: automatically chunks speaking segments to `<= max_block_sec`
    (default 5.5 s) so each Wav2Lip/LivePortrait block runs safely in an isolated process.
  - Neutral closed-mouth hold: always ends with `closed_hold` (`lip_sync: false`, 0.64 s)
    because Wav2Lip does not close the mouth over silence.
  - Additive ("somar, nunca subtrair"): preserves optional Blender 4.x (`blender_top.mov`),
    Reallusion (`reallusion_avatar`), and Remotion/OpenMontage hooks alongside the default
    100% local `avatar-journal` pipeline.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from tools.voicestudio_tts import analyze_expression
except Exception:  # noqa: BLE001
    analyze_expression = None  # type: ignore[assignment]

VALID_MODES = {"full_avatar", "split", "full_graphics", "broll"}
DEFAULT_LAYOUT = {
    "width": 1080,
    "height": 1920,
    "split_y": 1056,
    "split_height": 864,
    "captions_y_split": 950,
    "captions_y_full": 1390,
    "bottom_safe_margin_px": 300,
}
SPLIT_CLIP_CYCLE = ["speaking", "pointing", "idle"]


def _parse_timestamp(raw: str) -> float:
    """Parse 'MM:SS', 'MM:SS.ms', 'HH:MM:SS', or plain seconds '12.5' into float seconds."""
    token = raw.strip()
    if ":" not in token:
        return float(token)
    parts = [float(p) for p in token.split(":")]
    if len(parts) == 2:
        return parts[0] * 60.0 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600.0 + parts[1] * 60.0 + parts[2]
    raise ValueError(f"Unsupported timestamp format: '{raw}'")


def parse_time_range(raw: str) -> tuple[float, float]:
    """Parse '00:00-00:05' or '00:02.5-00:06' into (start_sec, end_sec)."""
    parts = re.split(r"\s*[-–—]\s*", raw.strip())
    if len(parts) != 2:
        raise ValueError(f"Invalid time range '{raw}'; expected 'START-END'")
    start = _parse_timestamp(parts[0])
    end = _parse_timestamp(parts[1])
    if end <= start:
        raise ValueError(f"Time range end ({end}) must be greater than start ({start}) in '{raw}'")
    return round(start, 3), round(end, 3)


def _snap_to_fps(seconds: float, fps: int) -> float:
    """Snap a timestamp to the nearest frame boundary so segments align cleanly on the fps grid."""
    if fps <= 0:
        return round(seconds, 3)
    return round(round(seconds * fps) / fps, 3)


def _infer_block_mode(role: str, visual_cue: str, explicit_mode: Optional[str]) -> str:
    if explicit_mode and explicit_mode in VALID_MODES:
        return explicit_mode
    r = (role or "").lower()
    cue = (visual_cue or "").lower()
    if "broll" in r or "b-roll" in cue or "broll" in cue:
        return "broll"
    if any(k in r for k in ("respiro", "grafico", "terminal", "full_gfx", "full_graphics")):
        return "full_graphics"
    if any(k in r for k in ("gancho", "hook", "abertura", "fechamento", "outro", "encerramento")):
        return "full_avatar"
    return "split"


def _expand_dynamic_block(
    start: float,
    end: float,
    role: str,
    mode: str,
    visual_cue: str,
    explicit_mode: bool,
    max_block_sec: float,
    fps: int,
    has_blender_top: bool,
) -> list[dict[str, Any]]:
    """Split a block into dynamic sub-segments respecting the GTX 1060 <= max_block_sec rule.

    If a long data block (> 10 s) came without an explicit mode (classic 60s pauta.json),
    automatically interleave a `full_graphics` breathing beat so the avatar appears and
    disappears dynamically rather than staying locked in split-screen for 20+ seconds.
    """
    dur = round(end - start, 3)
    if dur <= 0.05:
        return []

    r = (role or "").lower()
    raw_slices: list[tuple[float, float, str, str]] = []

    if not explicit_mode and mode == "split" and dur >= 10.0:
        # Dynamic rhythm for long data blocks: split -> full_graphics breather -> split -> ...
        cursor = start
        slot_idx = 0
        while cursor < end - 0.05:
            remaining = end - cursor
            # Every 3rd slice (index 1, 4, ...) give a full_graphics breather (~3.5-4.5s)
            if slot_idx % 3 == 1 and remaining >= 6.5:
                step = min(4.0, remaining - 2.5)
                nxt = _snap_to_fps(cursor + step, fps)
                raw_slices.append((cursor, nxt, "full_graphics", f"{visual_cue} [respiro tela cheia]"))
            else:
                step = min(max_block_sec, remaining)
                # Avoid leaving a tiny sliver < 1.5s at the end
                if 0 < remaining - step < 1.5:
                    step = remaining / 2.0
                nxt = end if remaining <= max_block_sec + 0.05 else _snap_to_fps(cursor + step, fps)
                raw_slices.append((cursor, nxt, "split", visual_cue))
            cursor = nxt
            slot_idx += 1
    elif not explicit_mode and mode == "full_avatar" and any(k in r for k in ("fechamento", "outro")) and dur > max_block_sec:
        # Long closing block: start in split for summary card, finish in full_avatar for sign-off
        final_full = min(4.0, max(2.0, dur * 0.35))
        split_end = _snap_to_fps(end - final_full, fps)
        cursor = start
        while cursor < split_end - 0.05:
            remaining = split_end - cursor
            step = min(max_block_sec, remaining)
            if 0 < remaining - step < 1.5:
                step = remaining / 2.0
            nxt = split_end if remaining <= max_block_sec + 0.05 else _snap_to_fps(cursor + step, fps)
            raw_slices.append((cursor, nxt, "split", visual_cue))
            cursor = nxt
        raw_slices.append((split_end, end, "full_avatar", visual_cue))
    elif mode in ("full_avatar", "split") and dur > max_block_sec:
        # Chunk long avatar speaking block into <= max_block_sec pieces for GTX 1060 VRAM/time
        n_chunks = max(2, math.ceil(dur / max_block_sec))
        chunk_len = dur / n_chunks
        cursor = start
        for idx in range(n_chunks):
            nxt = end if idx == n_chunks - 1 else _snap_to_fps(start + chunk_len * (idx + 1), fps)
            raw_slices.append((cursor, nxt, mode, visual_cue))
            cursor = nxt
    else:
        raw_slices.append((start, end, mode, visual_cue))

    out: list[dict[str, Any]] = []
    for s, e, m, cue in raw_slices:
        if e - s <= 0.05:
            continue
        item: dict[str, Any] = {
            "start": round(s, 3),
            "end": round(e, 3),
            "mode": m,
            "role": role,
            "visual_cue": cue,
        }
        if has_blender_top and m in ("split", "full_graphics"):
            item["blender_top_layer"] = True
        out.append(item)
    return out


def _merge_intervals(intervals: list[tuple[float, float]], eps: float = 0.05) -> list[list[float]]:
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda x: x[0])
    merged: list[list[float]] = [[ordered[0][0], ordered[0][1]]]
    for s, e in ordered[1:]:
        if s <= merged[-1][1] + eps:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [[round(s, 3), round(e, 3)] for s, e in merged]


def _select_short(pauta: dict[str, Any], short_id: Optional[str]) -> dict[str, Any]:
    shorts = pauta.get("shorts") or []
    if not shorts:
        raise ValueError("pauta.json has no entries in 'shorts'")
    if not short_id:
        return shorts[0]
    for item in shorts:
        if str(item.get("id")) == str(short_id):
            return item
    available = ", ".join(str(s.get("id")) for s in shorts)
    raise ValueError(f"Short '{short_id}' not found in pauta.json. Available: {available}")


def _audit_facts(facts: list[dict[str, Any]]) -> dict[str, Any]:
    missing_metrics = []
    missing_urls = []
    for idx, fact in enumerate(facts, start=1):
        if fact.get("metrics") is None:
            missing_metrics.append(idx)
        if not fact.get("source_url"):
            missing_urls.append(idx)
    return {
        "total_facts": len(facts),
        "missing_metrics_indices": missing_metrics,
        "missing_source_url_indices": missing_urls,
    }


def build_plan_from_pauta(
    pauta: dict[str, Any],
    short_id: Optional[str] = None,
    duration_override: Optional[float] = None,
    fps: int = 30,
    max_block_sec: float = 5.5,
    hold_sec: float = 0.64,
    engine_override: Optional[str] = None,
    compositor_override: Optional[str] = None,
    tts_provider: str = "voicestudio",
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    """Convert a pauta.json short into (avatar_plan, voiceover_text, short_brief)."""
    short = _select_short(pauta, short_id)
    voiceover = short.get("voiceover") or {}
    text = str(voiceover.get("text") or "").strip()
    blocks = voiceover.get("blocks") or []

    optional_engines = short.get("optional_engines") or {}
    blender_top = optional_engines.get("blender_top")
    reallusion_avatar = optional_engines.get("reallusion_avatar")
    remotion_props = optional_engines.get("remotion_props")

    engine = engine_override or pauta.get("avatar_engine_default") or "avatar-journal"
    compositor = compositor_override or pauta.get("compositor_default") or "hyperframes"
    has_blender_top = bool(blender_top) or engine == "blender-hybrid"

    # Determine target duration
    parsed_blocks: list[dict[str, Any]] = []
    max_block_end = 0.0
    for blk in blocks:
        s, e = parse_time_range(str(blk["time"]))
        max_block_end = max(max_block_end, e)
        explicit_mode = "mode" in blk and blk["mode"] in VALID_MODES
        mode = _infer_block_mode(
            str(blk.get("role") or ""),
            str(blk.get("visual_cue") or ""),
            blk.get("mode"),
        )
        parsed_blocks.append(
            {
                "start": s,
                "end": e,
                "role": str(blk.get("role") or "segment"),
                "mode": mode,
                "explicit_mode": explicit_mode,
                "visual_cue": str(blk.get("visual_cue") or ""),
            }
        )

    duration = float(
        duration_override
        if duration_override is not None
        else short.get("duration_seconds") or max_block_end or 18.0
    )
    if duration < 3.0:
        raise ValueError(f"Short duration ({duration}s) is too short; expected >= 3.0s")

    # Fallback if pauta.json had no voiceover.blocks
    if not parsed_blocks:
        hook_end = _snap_to_fps(min(3.0, duration * 0.18), fps)
        mid_end = _snap_to_fps(duration * 0.55, fps)
        gfx_end = _snap_to_fps(min(mid_end + 3.5, duration - 3.0), fps)
        outro_start = _snap_to_fps(max(gfx_end, duration - 2.5), fps)
        parsed_blocks = [
            {"start": 0.0, "end": hook_end, "role": "gancho", "mode": "full_avatar", "explicit_mode": False, "visual_cue": "abertura"},
            {"start": hook_end, "end": mid_end, "role": "dado_1", "mode": "split", "explicit_mode": False, "visual_cue": "img_01"},
            {"start": mid_end, "end": gfx_end, "role": "respiro_visual", "mode": "full_graphics", "explicit_mode": False, "visual_cue": "grafico"},
            {"start": gfx_end, "end": outro_start, "role": "dado_2", "mode": "split", "explicit_mode": False, "visual_cue": "img_02"},
            {"start": outro_start, "end": duration, "role": "fechamento", "mode": "full_avatar", "explicit_mode": False, "visual_cue": "fechamento"},
        ]
    elif duration_override is not None and max_block_end > 0 and abs(duration - max_block_end) > 0.05:
        scale = duration / max_block_end
        for blk in parsed_blocks:
            blk["start"] = _snap_to_fps(blk["start"] * scale, fps)
            blk["end"] = _snap_to_fps(blk["end"] * scale, fps)
        parsed_blocks[-1]["end"] = round(duration, 3)

    # Reserve the final hold_sec for the mandatory closed-mouth neutral hold
    effective_hold = min(hold_sec, max(0.32, duration * 0.08))
    speech_cutoff = _snap_to_fps(duration - effective_hold, fps)

    expanded: list[dict[str, Any]] = []
    for blk in parsed_blocks:
        s = min(blk["start"], speech_cutoff)
        e = min(blk["end"], speech_cutoff)
        if e - s <= 0.05:
            continue
        expanded.extend(
            _expand_dynamic_block(
                start=s,
                end=e,
                role=blk["role"],
                mode=blk["mode"],
                visual_cue=blk["visual_cue"],
                explicit_mode=blk["explicit_mode"],
                max_block_sec=min(max_block_sec, 6.0),
                fps=fps,
                has_blender_top=has_blender_top,
            )
        )

    # Build canonical avatar_plan segments
    segments: list[dict[str, Any]] = []
    speech_intervals: list[tuple[float, float]] = []
    split_counter = 0

    for idx, item in enumerate(expanded, start=1):
        mode = item["mode"]
        role_slug = re.sub(r"[^a-z0-9]+", "_", item["role"].lower()).strip("_") or "seg"
        seg_id = f"seg_{idx}_{role_slug}_{mode}"
        scene_id = f"scene_{min(3, 1 + int((item['start'] / max(duration, 1.0)) * 3))}"

        seg: dict[str, Any] = {
            "id": seg_id,
            "scene_id": scene_id,
            "start": item["start"],
            "end": item["end"],
            "mode": mode,
        }

        if mode == "full_avatar":
            seg["clip"] = "speaking"
            seg["media_start"] = 0.0
            seg["lip_sync"] = True
            if idx == 1:
                seg["zoom"] = {"from": 1.0, "to": 1.05}
            if reallusion_avatar and engine == "reallusion":
                seg["media_override"] = str(reallusion_avatar)
                seg["lip_engine"] = "reallusion"
            speech_intervals.append((item["start"], item["end"]))
        elif mode == "split":
            seg["clip"] = SPLIT_CLIP_CYCLE[split_counter % len(SPLIT_CLIP_CYCLE)]
            split_counter += 1
            seg["media_start"] = 0.0
            seg["lip_sync"] = True
            if reallusion_avatar and engine == "reallusion":
                seg["media_override"] = str(reallusion_avatar)
                seg["lip_engine"] = "reallusion"
            if item.get("blender_top_layer") and blender_top:
                seg["graphics"] = {"type": "blender_top", "source": str(blender_top), "cue": item["visual_cue"]}
            elif item["visual_cue"]:
                seg["graphics"] = {"type": "editorial_card", "cue": item["visual_cue"]}
            speech_intervals.append((item["start"], item["end"]))
        elif mode == "full_graphics":
            seg["clip"] = None
            seg["lip_sync"] = False
            gfx: dict[str, Any] = {"type": "full_graphics", "cue": item["visual_cue"]}
            if item.get("blender_top_layer") and blender_top:
                gfx["type"] = "blender_full"
                gfx["source"] = str(blender_top)
            seg["graphics"] = gfx
        elif mode == "broll":
            seg["clip"] = "broll_laptop"
            seg["media_start"] = 0.0
            seg["lip_sync"] = False
            seg["zoom"] = {"from": 1.0, "to": 1.04}
            if item["visual_cue"]:
                seg["note"] = item["visual_cue"]

        segments.append(seg)

    # Append mandatory neutral closed-mouth hold
    hold_seg_idx = len(segments) + 1
    segments.append(
        {
            "id": f"seg_{hold_seg_idx}_closed_hold",
            "scene_id": "scene_3",
            "start": speech_cutoff,
            "end": round(duration, 3),
            "mode": "full_avatar",
            "clip": "idle",
            "media_start": 0.0,
            "media_override": "assets/avatar/neutral_hold_full.mp4",
            "lip_sync": False,
            "fade_in": 0.08,
            "zoom": {"from": 1.0, "to": 1.02},
            "note": "Hold neutro de boca fechada (Wav2Lip nao fecha a boca em silencio).",
        }
    )

    avatar_plan: dict[str, Any] = {
        "version": "1.0",
        "source_short_id": short.get("id"),
        "source_date": pauta.get("date"),
        "avatar_engine": engine,
        "compositor": compositor,
        "duration_seconds": round(duration, 3),
        "fps": fps,
        "layout": dict(DEFAULT_LAYOUT),
        "speech_blocks": _merge_intervals(speech_intervals),
        "segments": segments,
    }

    # Lint TTS tags if voice_craft_tts is available
    tag_lint: dict[str, Any]
    if analyze_expression is not None:
        tag_lint = analyze_expression(text, tts_provider)
    else:
        tag_lint = {"provider": tts_provider, "tags": [], "unsupported": [], "warnings": ["analyze_expression unavailable"]}

    modes_used = sorted({s["mode"] for s in segments})
    lip_segments = [s for s in segments if s.get("lip_sync")]
    max_lip_dur = max(((s["end"] - s["start"]) for s in lip_segments), default=0.0)

    short_brief: dict[str, Any] = {
        "date": pauta.get("date"),
        "mode": pauta.get("mode"),
        "short_id": short.get("id"),
        "category": short.get("category"),
        "headline": short.get("headline"),
        "visual_concept": short.get("visual_concept"),
        "duration_seconds": round(duration, 3),
        "avatar_engine": engine,
        "compositor": compositor,
        "dynamic_director_summary": {
            "total_segments": len(segments),
            "lip_sync_segments": len(lip_segments),
            "max_lip_segment_seconds": round(max_lip_dur, 3),
            "modes_used": modes_used,
            "has_closed_hold": True,
        },
        "facts_audit": _audit_facts(short.get("facts") or []),
        "facts": short.get("facts") or [],
        "assets": short.get("assets") or {},
        "optional_engines": {
            "blender_top": blender_top,
            "reallusion_avatar": reallusion_avatar,
            "remotion_props": remotion_props,
        },
        "tts_tag_lint": tag_lint,
    }

    return avatar_plan, text, short_brief


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Convert jornalismo-ia-shorts-pro pauta.json into avatar-journal plan & artifacts."
    )
    p.add_argument("--pauta", required=True, help="Path to pauta.json (output of Fase 1)")
    p.add_argument("--short", default=None, help="Short ID inside pauta.json (default: first short)")
    p.add_argument("--project", default="./project", help="Target avatar-journal project directory")
    p.add_argument("--duration", type=float, default=None, help="Optional duration override in seconds")
    p.add_argument("--fps", type=int, default=30, help="Target FPS (default: 30)")
    p.add_argument(
        "--max-block-sec",
        type=float,
        default=5.5,
        help="Max lip-sync segment duration in seconds for GTX 1060 budget (default: 5.5, capped at 6.0)",
    )
    p.add_argument("--hold-sec", type=float, default=0.64, help="Final closed-mouth hold duration (default: 0.64)")
    p.add_argument(
        "--engine",
        default=None,
        choices=["avatar-journal", "blender-hybrid", "reallusion"],
        help="Avatar/visual engine mode (default: from pauta.json or avatar-journal)",
    )
    p.add_argument(
        "--compositor",
        default=None,
        choices=["hyperframes", "openmontage", "remotion"],
        help="Compositor target (default: from pauta.json or hyperframes)",
    )
    p.add_argument("--tts-provider", default="voicestudio", help="TTS provider used to lint bracket tags")
    p.add_argument("--strict-tags", action="store_true", help="Exit with code 2 if unsupported TTS tags are detected")
    p.add_argument("--dry-run", action="store_true", help="Print generated plan summary without writing files")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    pauta_path = Path(args.pauta).expanduser().resolve()
    if not pauta_path.is_file():
        print(f"[pauta_to_plan] ERROR: pauta file not found: {pauta_path}", file=sys.stderr)
        return 1

    pauta = json.loads(pauta_path.read_text(encoding="utf-8"))
    plan, voiceover_text, brief = build_plan_from_pauta(
        pauta=pauta,
        short_id=args.short,
        duration_override=args.duration,
        fps=args.fps,
        max_block_sec=args.max_block_sec,
        hold_sec=args.hold_sec,
        engine_override=args.engine,
        compositor_override=args.compositor,
        tts_provider=args.tts_provider,
    )

    unsupported_tags = (brief.get("tts_tag_lint") or {}).get("unsupported") or []
    written: dict[str, str] = {}

    if not args.dry_run:
        artifacts_dir = Path(args.project).expanduser().resolve() / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        plan_path = artifacts_dir / "avatar_plan.json"
        voice_path = artifacts_dir / "voiceover.txt"
        brief_path = artifacts_dir / "short_brief.json"

        plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        voice_path.write_text(voiceover_text + ("\n" if voiceover_text else ""), encoding="utf-8")
        brief_path.write_text(json.dumps(brief, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        written = {
            "avatar_plan": str(plan_path),
            "voiceover": str(voice_path),
            "short_brief": str(brief_path),
        }

    summary = {
        "dry_run": args.dry_run,
        "pauta": str(pauta_path),
        "short_id": brief["short_id"],
        "headline": brief["headline"],
        "duration_seconds": plan["duration_seconds"],
        "avatar_engine": plan["avatar_engine"],
        "compositor": plan["compositor"],
        "dynamic_director_summary": brief["dynamic_director_summary"],
        "speech_blocks": plan["speech_blocks"],
        "facts_audit": brief["facts_audit"],
        "tts_tag_lint": brief["tts_tag_lint"],
        "written": written,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.strict_tags and unsupported_tags:
        print(
            f"[pauta_to_plan] ERROR: unsupported TTS tags for '{args.tts_provider}': {unsupported_tags}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
