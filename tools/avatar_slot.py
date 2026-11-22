"""Configure Dynamic Avatar Layout Director media in a HyperFrames composition.

Supports:
  - Full directory catalog mode (--avatar-dir) guided by avatar_plan.json across
    four layout modes: full_avatar, split, full_graphics, broll
  - Single-clip backward-compatible mode (--avatar-asset) for quick static/loop overrides
  - Deterministic fallback when media files are omitted or missing
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTS = {".mp4", ".webm", ".mov"}

AVATAR_CATALOG: dict[str, str] = {
    "speaking": "ale_speaking_to_camera.mp4",
    "pointing": "Man_pointing_in_studio_2faebef8.mp4",
    "idle": "Man_looking_at_camera_3b30a70c.mp4",
    "broll_laptop": "Man_typing_on_laptop_42509c8b.mp4",
    "broll_monitor": "Man_analyzing_monitor_in_studio_c04d7188.mp4",
}

MEDIA_START_MARKER = "<!-- AVATAR_SLOT_MEDIA_START -->"
MEDIA_END_MARKER = "<!-- AVATAR_SLOT_MEDIA_END -->"
DATA_START_MARKER = "/* AVATAR_PLAN_DATA_START */"
DATA_END_MARKER = "/* AVATAR_PLAN_DATA_END */"

PIP_MEDIA_STYLE = (
    "position:absolute; left:0; top:1056px; width:1080px; height:864px; "
    "object-fit:cover; object-position:center 20%; z-index:20; pointer-events:none;"
)
FULL_MEDIA_STYLE = (
    "position:absolute; left:0; top:0; width:1080px; height:1920px; "
    "object-fit:cover; object-position:center 20%; transform-origin:center 35%; "
    "z-index:20; pointer-events:none;"
)


def _find_ffmpeg(override: Optional[str] = None) -> str:
    """Resolve an available ffmpeg executable on host."""
    if override:
        candidate = Path(override)
        if candidate.is_file():
            return str(candidate)
        resolved = shutil.which(override)
        if resolved:
            return resolved
        raise FileNotFoundError(f"FFmpeg binary not found: {override}")

    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path

    windows_fallback = Path(r"D:\Utilitarios\ffmpeg\bin\ffmpeg.exe")
    if windows_fallback.is_file():
        return str(windows_fallback)

    raise FileNotFoundError(
        "ffmpeg executable not found on PATH or D:\\Utilitarios\\ffmpeg\\bin\\ffmpeg.exe"
    )


def _format_num(value: float) -> str:
    """Format numeric values compactly for HTML data attributes."""
    val = float(value)
    return str(int(val)) if val.is_integer() else f"{val:g}"


def _clear_single_slot_assets(assets_dir: Path) -> None:
    """Remove legacy single-clip avatar_slot.* files so unused copies do not linger."""
    if not assets_dir.exists():
        return
    for old_file in assets_dir.glob("avatar_slot.*"):
        if old_file.is_file():
            old_file.unlink()


def _encode_clip_variant(
    src: Path,
    dest: Path,
    width: int,
    height: int,
    crop_y_frac: float,
    fps: int,
    loop_seconds: float,
    ffmpeg_bin: str,
    *,
    preset: str = "fast",
    crf: int = 18,
    force: bool = False,
) -> bool:
    """Encode a smooth muted looping H.264 clip with 1s GOP keyframes. Returns True if re-encoded."""
    if not force and dest.is_file() and dest.stat().st_size > 0:
        if dest.stat().st_mtime >= src.stat().st_mtime:
            return False

    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={width}:{height}:(iw-{width})/2:(ih-{height})*{crop_y_frac}"
    )
    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-stream_loop",
        "-1",
        "-i",
        str(src),
        "-t",
        _format_num(loop_seconds),
        "-an",
        "-vf",
        vf,
        "-r",
        str(fps),
        "-g",
        str(fps),
        "-keyint_min",
        str(fps),
        "-c:v",
        "libx264",
        "-crf",
        str(crf),
        "-preset",
        preset,
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-y",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not dest.is_file():
        raise RuntimeError(f"FFmpeg encode failed for {dest.name} ({proc.returncode}): {proc.stderr.strip()}")
    return True


def _update_chrome_pip_variables(html_text: str, mode: str, avatar_label: str) -> str:
    """Update data-variable-values on #el-chrome-pip cleanly."""
    payload = json.dumps({"avatarMode": mode, "avatarLabel": avatar_label}, ensure_ascii=False)
    escaped_payload = payload.replace("'", "&#39;")
    replacement_attr = f"data-variable-values='{escaped_payload}'"

    tag_pattern = re.compile(r'(<div\b[^>]*\bid="el-chrome-pip"[^>]*>)', re.DOTALL)
    match = tag_pattern.search(html_text)
    if not match:
        raise ValueError('Could not locate <div id="el-chrome-pip" ...> in index.html')

    tag = match.group(1)
    attr_pattern = re.compile(r"""data-variable-values=(?:'[^']*'|"[^"]*")""")
    if attr_pattern.search(tag):
        new_tag = attr_pattern.sub(lambda _: replacement_attr, tag, count=1)
    else:
        new_tag = tag.replace('id="el-chrome-pip"', f'id="el-chrome-pip" {replacement_attr}', 1)
    return html_text[: match.start()] + new_tag + html_text[match.end() :]


def _replace_media_slot(html_text: str, tag_markup: str) -> str:
    """Replace content between AVATAR_SLOT_MEDIA_START and AVATAR_SLOT_MEDIA_END."""
    block_pattern = re.compile(
        r"([ \t]*)" + re.escape(MEDIA_START_MARKER) + r".*?" + re.escape(MEDIA_END_MARKER),
        re.DOTALL,
    )
    match = block_pattern.search(html_text)
    if not match:
        raise ValueError(f"Could not find {MEDIA_START_MARKER} ... {MEDIA_END_MARKER} markers in index.html")

    indent = match.group(1)
    if tag_markup:
        indented_lines = "\n".join(f"{indent}{line}" for line in tag_markup.splitlines())
        body = f"{indent}{MEDIA_START_MARKER}\n{indented_lines}\n{indent}{MEDIA_END_MARKER}"
    else:
        body = f"{indent}{MEDIA_START_MARKER}\n{indent}{MEDIA_END_MARKER}"
    return html_text[: match.start()] + body + html_text[match.end() :]


def _sync_plan_data_into_subcomp(file_path: Path, resolved_segments: list[dict[str, Any]]) -> None:
    """Sync AVATAR_SEGMENTS JSON into /* AVATAR_PLAN_DATA_START */ ... /* AVATAR_PLAN_DATA_END */."""
    if not file_path.is_file():
        return
    text = file_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"([ \t]*)" + re.escape(DATA_START_MARKER) + r".*?" + re.escape(DATA_END_MARKER),
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return
    indent = match.group(1)
    compact_json = json.dumps(resolved_segments, ensure_ascii=False)
    replacement = (
        f"{indent}{DATA_START_MARKER}\n"
        f"{indent}const AVATAR_SEGMENTS = {compact_json};\n"
        f"{indent}{DATA_END_MARKER}"
    )
    updated = text[: match.start()] + replacement + text[match.end() :]
    file_path.write_text(updated, encoding="utf-8")


def configure_avatar_dir(
    project_dir: Path,
    avatar_dir: Path,
    plan_path: Optional[Path] = None,
    avatar_label: str = "AVATAR LOCAL",
    fps: int = 30,
    loop_seconds: float = 10.0,
    ffmpeg_override: Optional[str] = None,
    force: bool = False,
) -> dict[str, Any]:
    """Prepare 1080x1920 & 1080x864 catalog clips and apply avatar_plan.json choreography."""
    hf_dir = project_dir / "hyperframes"
    index_path = hf_dir / "index.html"
    assets_dir = hf_dir / "assets"
    avatar_out_dir = assets_dir / "avatar"
    resolved_plan_path = plan_path or (project_dir / "artifacts" / "avatar_plan.json")

    if not index_path.is_file():
        raise FileNotFoundError(f"HyperFrames entry file not found: {index_path}")
    if not resolved_plan_path.is_file():
        raise FileNotFoundError(f"Avatar plan not found: {resolved_plan_path}")

    avatar_out_dir.mkdir(parents=True, exist_ok=True)
    _clear_single_slot_assets(assets_dir)

    plan = json.loads(resolved_plan_path.read_text(encoding="utf-8"))
    ffmpeg_bin = _find_ffmpeg(ffmpeg_override)

    catalog_manifest: dict[str, dict[str, Any]] = {}
    for key, filename in AVATAR_CATALOG.items():
        src = avatar_dir / filename
        if not src.is_file():
            catalog_manifest[key] = {
                "available": False,
                "source": str(src),
                "full_path": None,
                "split_path": None,
            }
            continue

        full_dest = avatar_out_dir / f"{key}_full.mp4"
        split_dest = avatar_out_dir / f"{key}_split.mp4"
        full_encoded = _encode_clip_variant(
            src, full_dest, 1080, 1920, 0.15, fps, loop_seconds, ffmpeg_bin, force=force
        )
        split_encoded = _encode_clip_variant(
            src, split_dest, 1080, 864, 0.20, fps, loop_seconds, ffmpeg_bin, force=force
        )
        catalog_manifest[key] = {
            "available": True,
            "source": str(src),
            "full_path": f"assets/avatar/{key}_full.mp4",
            "split_path": f"assets/avatar/{key}_split.mp4",
            "reencoded": {"full": full_encoded, "split": split_encoded},
        }

    manifest_path = avatar_out_dir / "manifest.json"
    manifest_payload = {
        "version": "1.0",
        "avatar_dir": str(avatar_dir),
        "fps": fps,
        "loop_seconds": loop_seconds,
        "catalog": catalog_manifest,
    }
    manifest_path.write_text(json.dumps(manifest_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    video_tags: list[str] = []
    resolved_segments: list[dict[str, Any]] = []
    for seg in plan.get("segments", []):
        seg_id = str(seg["id"])
        mode = str(seg["mode"])
        start = float(seg["start"])
        end = float(seg["end"])
        dur = round(end - start, 4)
        clip_key = seg.get("clip")
        media_start = float(seg.get("media_start", 0.0))
        zoom = seg.get("zoom") or {}
        fade_in = float(seg.get("fade_in") or 0.0)
        fade_out = float(seg.get("fade_out") or 0.0)

        clip_info = catalog_manifest.get(clip_key, {}) if clip_key else {}
        override = seg.get("media_override")
        override_src = (hf_dir / override) if override else None
        has_media = False
        if mode in {"full_avatar", "broll"} and (override_src or clip_info.get("available")):
            has_media = True
            rel_src = override if override_src is not None else clip_info["full_path"]
            style = FULL_MEDIA_STYLE
        elif mode == "split" and (override_src or clip_info.get("available")):
            has_media = True
            rel_src = override if override_src is not None else clip_info["split_path"]
            style = PIP_MEDIA_STYLE
        else:
            rel_src = None
            style = ""

        resolved_segments.append(
            {
                "id": seg_id,
                "start": start,
                "end": end,
                "mode": mode,
                "clip": clip_key,
                "has_media": has_media,
            }
        )

        if has_media and rel_src:
            dom_id = "av-" + re.sub(r"[^a-zA-Z0-9_-]+", "-", seg_id).strip("-")
            zoom_attrs = ""
            if "from" in zoom and "to" in zoom:
                zoom_attrs = (
                    f' data-zoom-from="{_format_num(zoom["from"])}" '
                    f'data-zoom-to="{_format_num(zoom["to"])}"'
                )
            if fade_in > 0:
                zoom_attrs += f' data-fade-in="{_format_num(fade_in)}"'
            if fade_out > 0:
                zoom_attrs += f' data-fade-out="{_format_num(fade_out)}"'

            # Important hyperframes-core rule: never put class="clip" on <video> host children
            video_tags.append(
                f'<video id="{dom_id}" src="{rel_src}" '
                f'data-start="{_format_num(start)}" data-duration="{_format_num(dur)}" '
                f'data-media-start="{_format_num(media_start)}" data-track-index="4" '
                f'data-layout-mode="{mode}"{zoom_attrs} muted playsinline style="{style}"></video>'
            )

    html_text = index_path.read_text(encoding="utf-8")
    html_text = _update_chrome_pip_variables(html_text, "director", avatar_label)
    html_text = _replace_media_slot(html_text, "\n".join(video_tags))
    index_path.write_text(html_text, encoding="utf-8")

    _sync_plan_data_into_subcomp(hf_dir / "compositions" / "chrome-pip.html", resolved_segments)
    _sync_plan_data_into_subcomp(hf_dir / "compositions" / "captions.html", resolved_segments)

    return {
        "mode": "director",
        "avatar_dir": str(avatar_dir),
        "plan_path": str(resolved_plan_path),
        "manifest_path": str(manifest_path),
        "index_html": str(index_path),
        "segments_total": len(resolved_segments),
        "videos_mounted": len(video_tags),
        "segments": resolved_segments,
    }


def configure_avatar_slot(
    project_dir: Path,
    avatar_asset: Optional[str],
    avatar_label: str = "AVATAR LOCAL",
    duration: float = 18.0,
    fps: int = 30,
    ffmpeg_override: Optional[str] = None,
) -> dict[str, Any]:
    """Single-clip or deterministic fallback #talking-head-slot configuration."""
    hf_dir = project_dir / "hyperframes"
    index_path = hf_dir / "index.html"
    assets_dir = hf_dir / "assets"
    if not index_path.is_file():
        raise FileNotFoundError(f"HyperFrames entry file not found: {index_path}")

    assets_dir.mkdir(parents=True, exist_ok=True)
    _clear_single_slot_assets(assets_dir)

    dur_str = _format_num(duration)
    html_text = index_path.read_text(encoding="utf-8")

    mode = "fallback"
    mounted_rel: Optional[str] = None
    tag_markup = ""
    asset_in_resolved: Optional[str] = None

    if avatar_asset:
        src = Path(avatar_asset).expanduser().resolve()
        if not src.is_file():
            raise FileNotFoundError(f"Avatar asset not found: {src}")
        asset_in_resolved = str(src)
        ext = src.suffix.lower()

        if ext in IMAGE_EXTS:
            mode = "image"
            dest = assets_dir / f"avatar_slot{ext}"
            shutil.copy2(src, dest)
            mounted_rel = f"assets/avatar_slot{ext}"
            tag_markup = (
                f'<img id="talking-head-image" class="clip" src="{mounted_rel}" alt="Avatar local" '
                f'data-start="0" data-duration="{dur_str}" data-track-index="4" '
                f'style="{PIP_MEDIA_STYLE}" />'
            )
        elif ext in VIDEO_EXTS:
            mode = "video"
            ffmpeg_bin = _find_ffmpeg(ffmpeg_override)
            dest = assets_dir / "avatar_slot.mp4"
            _encode_clip_variant(
                src, dest, 1080, 864, 0.20, fps, duration, ffmpeg_bin, preset="medium", force=True
            )
            mounted_rel = "assets/avatar_slot.mp4"
            tag_markup = (
                f'<video id="talking-head-video" src="{mounted_rel}" '
                f'data-start="0" data-duration="{dur_str}" data-track-index="4" '
                f'muted playsinline style="{PIP_MEDIA_STYLE}"></video>'
            )
        else:
            supported = ", ".join(sorted(IMAGE_EXTS | VIDEO_EXTS))
            raise ValueError(f"Unsupported avatar extension '{ext}'. Supported: {supported}")

    html_text = _update_chrome_pip_variables(html_text, mode, avatar_label)
    html_text = _replace_media_slot(html_text, tag_markup)
    index_path.write_text(html_text, encoding="utf-8")

    return {
        "mode": mode,
        "asset_in": asset_in_resolved,
        "asset_mounted": mounted_rel,
        "index_html": str(index_path),
        "duration_seconds": float(duration),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure Dynamic Avatar Layout Director (--avatar-dir) or single slot (--avatar-asset)."
    )
    parser.add_argument("--project", default="projects/teste-jornal-ia", help="Project directory path")
    parser.add_argument("--avatar-dir", default=None, help="Directory with catalog MP4 clips for Dynamic Director")
    parser.add_argument("--plan", default=None, help="Path to avatar_plan.json (default: <project>/artifacts/avatar_plan.json)")
    parser.add_argument("--avatar-asset", default=None, help="Optional single PNG/JPG/MP4 fallback asset")
    parser.add_argument("--avatar-label", default="AVATAR LOCAL", help="Badge label shown in fallback mode")
    parser.add_argument("--duration", type=float, default=18.0, help="Single-asset fallback duration in seconds")
    parser.add_argument("--fps", type=int, default=30, help="Target FPS for encoded loops")
    parser.add_argument("--ffmpeg", default=None, help="Optional path to ffmpeg executable")
    parser.add_argument("--force", action="store_true", help="Force re-encode cached catalog variants")
    args = parser.parse_args()

    project_dir = Path(args.project).resolve()
    if args.avatar_dir:
        result = configure_avatar_dir(
            project_dir=project_dir,
            avatar_dir=Path(args.avatar_dir).expanduser().resolve(),
            plan_path=Path(args.plan).expanduser().resolve() if args.plan else None,
            avatar_label=args.avatar_label,
            fps=args.fps,
            ffmpeg_override=args.ffmpeg,
            force=args.force,
        )
    else:
        result = configure_avatar_slot(
            project_dir=project_dir,
            avatar_asset=args.avatar_asset,
            avatar_label=args.avatar_label,
            duration=args.duration,
            fps=args.fps,
            ffmpeg_override=args.ffmpeg,
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
