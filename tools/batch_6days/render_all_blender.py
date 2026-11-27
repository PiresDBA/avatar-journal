"""Batch 3D generator for all 6 Shorts using cli-anything-blender + Blender 5.3 EEVEE.

Stage 1 (driver mode, C:\\Docling\\venv):
  - Initializes each Short's scene blueprint via `cli-anything-blender` (`scene_template.blend-cli.json`)
  - Launches `D:\\Blender\\blender.exe --background --python render_all_blender.py -- --render-one <slug>`
    sequentially so VRAM stays safe and every Short renders cleanly.
  - Builds consolidated visual QA sheet `all6_blender_qa.png`.

Stage 2 (Blender internal `--render-one <slug>` mode):
  - Builds 4 distinct 120-frame seamless periodic animated scenes tailored to that day's aesthetic.
  - Renders half-res PNGs (`540x672` top / `540x960` full, EEVEE 6 samples + raytracing + AgX Punchy),
    then upscales 2x with FFmpeg Lanczos and loops continuously to exact segment durations in `timings.json`.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

OUT_ROOT = Path(r"D:\Utilitarios\avatar-journal\output\2026-11-26")
BLENDER_EXE = r"D:\Blender\blender.exe"
FFMPEG = r"D:\Utilitarios\ffmpeg\bin\ffmpeg.exe"
LOOP_FRAMES = 120


def driver_init_cli_anything(short_dir: Path, slug: str, theme: str) -> None:
    from cli_anything.blender.blender_cli import cli

    proj = short_dir / "scene_template.blend-cli.json"
    calls = [
        ["scene", "new", "--name", slug, "-o", str(proj)],
        ["--project", str(proj), "object", "add", "sphere", "--name", "HeroAnchor", "--location", "0,0,0"],
        ["--project", str(proj), "material", "create", "--name", f"Mat_{theme}", "--color", "0.2,0.75,0.95", "--metallic", "0.9", "--roughness", "0.1"],
        ["--project", str(proj), "material", "assign", "0", "0"],
        ["--project", str(proj), "light", "add", "area", "--name", "KeyLight", "-l", "-4,-3,4", "-w", "320"],
        ["--project", str(proj), "camera", "add", "--name", "MainCam", "-l", "0,-6,0.7"],
        ["--project", str(proj), "render", "settings", "--engine", "EEVEE", "--resolution-x", "1080", "--resolution-y", "1920", "--samples", "6"],
    ]
    for c in calls:
        cli.main(args=c, standalone_mode=False)


def run_driver() -> int:
    REPO_ROOT = Path(r"D:\Utilitarios\avatar-journal")
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from tools.batch_6days.specs import SHORTS_6DAYS

    os.environ["PATH"] = r"D:\Blender;D:\Utilitarios\ffmpeg\bin;" + os.environ.get("PATH", "")
    only = {a.strip() for a in sys.argv[1:] if a.strip()}

    for spec in SHORTS_6DAYS:
        slug = spec["slug"]
        if only and slug not in only and spec["day_key"] not in only:
            continue
        sdir = OUT_ROOT / slug
        sdir.mkdir(parents=True, exist_ok=True)
        print(f"[cli-anything-blender] Init template for {slug} ({spec['style']['lemo']})...", flush=True)
        driver_init_cli_anything(sdir, slug, spec["style"]["lemo"])

        print(f"[Blender 5.3] Rendering 4 animated clips for {slug}...", flush=True)
        subprocess.run(
            [BLENDER_EXE, "--background", "--python", str(Path(__file__).resolve()), "--", "--render-one", slug],
            check=True,
        )

    build_all6_qa(SHORTS_6DAYS)
    return 0


def build_all6_qa(specs: list[dict]) -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return
    tiles = []
    tw, th = 270, 480
    for spec in specs:
        sdir = OUT_ROOT / spec["slug"]
        bdir = sdir / "blender_out"
        for clip_dir, label in [("frames_02_b", f"{spec['day_short']} 02"), ("frames_03_c", f"{spec['day_short']} 03")]:
            p = bdir / clip_dir / "f_0030.png"
            if p.is_file():
                im = Image.open(p).convert("RGB").resize((tw, th), Image.Resampling.LANCZOS)
                dr = ImageDraw.Draw(im)
                dr.rectangle([0, 0, tw, 34], fill=(8, 12, 22))
                dr.text((10, 9), label, fill=(248, 250, 252))
                tiles.append(im)
    if not tiles:
        return
    cols = 6
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (6, 8, 14))
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
    out_png = OUT_ROOT / "all6_blender_qa.png"
    sheet.save(out_png)
    print(f"[OK] Saved consolidated 3D QA sheet -> {out_png}", flush=True)


# ---------------------------------------------------------------------------
# Blender Internal Engine (`bpy`)
# ---------------------------------------------------------------------------

def _blender_main(slug: str) -> int:
    import bpy
    from mathutils import Vector

    THEME_CFG = {
        "short_01_seg_ltx25": {
            "theme": "optical",
            "bg_bot": (0.004, 0.010, 0.025),
            "bg_top": (0.14, 0.52, 0.85),
            "side_l": (0.12, 0.80, 1.00),
            "side_r": (0.98, 0.65, 0.16),
            "floor": (0.014, 0.024, 0.050),
            "floor_rough": 0.04,
            "key_col": (0.75, 0.92, 1.0),
            "rim_col": (1.0, 0.70, 0.22),
            "accent_a": (0.20, 0.82, 1.0),
            "accent_b": (0.98, 0.65, 0.15),
        },
        "short_02_ter_visual_reasoning": {
            "theme": "porcelain",
            "bg_bot": (0.016, 0.018, 0.026),
            "bg_top": (0.45, 0.36, 0.28),
            "side_l": (0.85, 0.55, 0.20),
            "side_r": (0.92, 0.94, 0.98),
            "floor": (0.045, 0.048, 0.062),
            "floor_rough": 0.14,
            "key_col": (1.0, 0.93, 0.85),
            "rim_col": (0.96, 0.52, 0.16),
            "accent_a": (0.94, 0.26, 0.26),
            "accent_b": (0.10, 0.78, 0.52),
        },
        "short_03_qua_batalha_local": {
            "theme": "arena",
            "bg_bot": (0.005, 0.008, 0.022),
            "bg_top": (0.22, 0.28, 0.55),
            "side_l": (0.06, 0.85, 0.55),
            "side_r": (0.38, 0.40, 1.00),
            "floor": (0.022, 0.028, 0.044),
            "floor_rough": 0.06,
            "key_col": (0.85, 0.92, 1.0),
            "rim_col": (0.42, 0.45, 1.0),
            "accent_a": (0.07, 0.85, 0.54),
            "accent_b": (0.40, 0.42, 0.98),
        },
        "short_04_sex_anthropic_scion": {
            "theme": "tungsten",
            "bg_bot": (0.018, 0.013, 0.009),
            "bg_top": (0.78, 0.46, 0.14),
            "side_l": (0.98, 0.65, 0.18),
            "side_r": (0.65, 0.40, 0.20),
            "floor": (0.026, 0.020, 0.015),
            "floor_rough": 0.09,
            "key_col": (1.0, 0.78, 0.42),
            "rim_col": (0.95, 0.48, 0.15),
            "accent_a": (0.98, 0.66, 0.16),
            "accent_b": (0.96, 0.92, 0.85),
        },
        "short_05_sab_lado_b_mcp": {
            "theme": "circuit",
            "bg_bot": (0.006, 0.006, 0.009),
            "bg_top": (0.38, 0.12, 0.08),
            "side_l": (0.98, 0.26, 0.22),
            "side_r": (0.14, 0.82, 0.42),
            "floor": (0.012, 0.012, 0.018),
            "floor_rough": 0.08,
            "key_col": (1.0, 0.82, 0.65),
            "rim_col": (0.98, 0.26, 0.24),
            "accent_a": (0.98, 0.26, 0.24),
            "accent_b": (0.14, 0.84, 0.42),
        },
        "short_06_dom_world_models": {
            "theme": "blueprint",
            "bg_bot": (0.010, 0.022, 0.065),
            "bg_top": (0.98, 0.72, 0.24),
            "side_l": (0.20, 0.76, 1.00),
            "side_r": (0.98, 0.74, 0.22),
            "floor": (0.014, 0.028, 0.075),
            "floor_rough": 0.07,
            "key_col": (0.98, 0.88, 0.68),
            "rim_col": (0.22, 0.76, 1.00),
            "accent_a": (0.22, 0.76, 1.00),
            "accent_b": (0.98, 0.76, 0.22),
        },
    }

    cfg = THEME_CFG[slug]
    sdir = OUT_ROOT / slug
    bdir = sdir / "blender_out"
    bdir.mkdir(parents=True, exist_ok=True)
    timings = json.loads((sdir / "audio" / "timings.json").read_text(encoding="utf-8"))
    segs = timings["segments"]
    durs = [
        float(segs[0]["duration"]) + 0.25,
        float(segs[2]["start"]) - float(segs[1]["start"]),
        float(segs[3]["start"]) - float(segs[2]["start"]),
        float(timings["total_duration"]) - float(segs[3]["start"]),
    ]

    def clear_scene():
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def setup_hdri(scene):
        world = bpy.data.worlds.new("StudioHDRI")
        scene.world = world
        world.use_nodes = True
        nt = world.node_tree
        nt.nodes.clear()
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        rb = nt.nodes.new("ShaderNodeValToRGB")
        rs = nt.nodes.new("ShaderNodeValToRGB")
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        mx.blend_type = "ADD"
        bg = nt.nodes.new("ShaderNodeBackground")
        out = nt.nodes.new("ShaderNodeOutputWorld")
        mp.inputs["Rotation"].default_value = (0.25, 0.15, 0.40)
        nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], sep.inputs["Vector"])

        rb.color_ramp.elements[0].position = 0.22
        rb.color_ramp.elements[0].color = (*cfg["bg_bot"], 1.0)
        em = rb.color_ramp.elements.new(0.58)
        em.color = tuple(v * 0.45 for v in cfg["bg_top"]) + (1.0,)
        rb.color_ramp.elements[-1].position = 0.90
        rb.color_ramp.elements[-1].color = (*cfg["bg_top"], 1.0)

        rs.color_ramp.elements[0].position = 0.08
        rs.color_ramp.elements[0].color = (*cfg["side_l"], 1.0)
        s1 = rs.color_ramp.elements.new(0.22)
        s1.color = (0.0, 0.0, 0.0, 1.0)
        s2 = rs.color_ramp.elements.new(0.78)
        s2.color = (0.0, 0.0, 0.0, 1.0)
        rs.color_ramp.elements[-1].position = 0.92
        rs.color_ramp.elements[-1].color = (*cfg["side_r"], 1.0)

        nt.links.new(sep.outputs["Z"], rb.inputs["Fac"])
        nt.links.new(sep.outputs["X"], rs.inputs["Fac"])
        mx.inputs["Factor"].default_value = 0.92
        nt.links.new(rb.outputs["Color"], mx.inputs[6])
        nt.links.new(rs.outputs["Color"], mx.inputs[7])
        nt.links.new(mx.outputs[2], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 1.65

        # Camera sees deep dark luxury studio backdrop; glossy/diffuse rays still get rich HDRI
        rc = nt.nodes.new("ShaderNodeValToRGB")
        rc.color_ramp.elements[0].position = 0.15
        rc.color_ramp.elements[0].color = (*cfg["bg_bot"], 1.0)
        rc.color_ramp.elements[-1].position = 0.88
        rc.color_ramp.elements[-1].color = tuple(min(0.08, v * 0.14) for v in cfg["bg_top"]) + (1.0,)
        nt.links.new(sep.outputs["Z"], rc.inputs["Fac"])
        bg_cam = nt.nodes.new("ShaderNodeBackground")
        bg_cam.inputs["Strength"].default_value = 1.0
        nt.links.new(rc.outputs["Color"], bg_cam.inputs["Color"])

        lp = nt.nodes.new("ShaderNodeLightPath")
        mix_sh = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(lp.outputs["Is Camera Ray"], mix_sh.inputs["Fac"])
        nt.links.new(bg.outputs["Background"], mix_sh.inputs[1])
        nt.links.new(bg_cam.outputs["Background"], mix_sh.inputs[2])
        nt.links.new(mix_sh.outputs["Shader"], out.inputs["Surface"])

    def setup_scene(rx: int, ry: int):
        sc = bpy.context.scene
        sc.render.engine = "BLENDER_EEVEE"
        sc.render.resolution_x = rx
        sc.render.resolution_y = ry
        sc.render.resolution_percentage = 100
        sc.render.fps = 30
        sc.frame_start = 1
        sc.frame_end = LOOP_FRAMES
        sc.render.image_settings.file_format = "PNG"
        for a, v in [("taa_render_samples", 6), ("use_raytracing", True), ("shadow_ray_count", 1), ("shadow_step_count", 4), ("use_volumetric_shadows", False)]:
            try:
                setattr(sc.eevee, a, v)
            except Exception:
                pass
        setup_hdri(sc)
        sc.view_settings.view_transform = "AgX"
        try:
            sc.view_settings.look = "AgX - Punchy"
        except Exception:
            pass
        return sc

    def mat(name, rgb, *, metal=0.9, rough=0.08, coat=0.9, em_rgb=None, em_str=0.0, trans=0.0, ior=1.52):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        bsdf = m.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
        for k, v in [("Coat Weight", coat), ("Coat Roughness", 0.03), ("Transmission Weight", trans), ("IOR", ior)]:
            try:
                bsdf.inputs[k].default_value = v
            except Exception:
                pass
        if em_rgb and em_str > 0:
            bsdf.inputs["Emission Color"].default_value = (*em_rgb, 1.0)
            bsdf.inputs["Emission Strength"].default_value = em_str
        return m

    def lights():
        def area(name, loc, tgt, col, energy, sz):
            bpy.ops.object.light_add(type="AREA", location=loc)
            o = bpy.context.active_object
            o.name = name
            o.data.color = col
            o.data.energy = energy
            o.data.size = sz
            o.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        area("Key", (-4.2, -3.6, 4.5), (0, 0, 0.2), cfg["key_col"], 340.0, 4.2)
        area("Rim", (4.5, 3.2, 2.8), (0, 0, 0.2), cfg["rim_col"], 280.0, 3.0)
        area("Fill", (0.4, -5.2, 1.8), (0, 0, 0.0), (0.65, 0.78, 1.0), 70.0, 5.5)

    def floor():
        bpy.ops.mesh.primitive_plane_add(size=28.0, location=(0, 0, -1.35))
        fl = bpy.context.active_object
        fl.data.materials.append(mat("Floor", cfg["floor"], metal=0.82, rough=cfg["floor_rough"], coat=1.0))

    def cam_at(loc, tgt, lens=36.0):
        bpy.ops.object.camera_add(location=loc)
        c = bpy.context.active_object
        c.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        c.data.sensor_fit = "HORIZONTAL"
        c.data.lens = lens
        bpy.context.scene.camera = c
        return c

    def sphere(name, loc, r, m):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=r, location=loc)
        o = bpy.context.active_object
        o.name = name
        bpy.ops.object.shade_smooth()
        o.data.materials.append(m)
        return o

    def torus(name, loc, maj, min_r, rot, m):
        bpy.ops.mesh.primitive_torus_add(major_segments=96, minor_segments=24, major_radius=maj, minor_radius=min_r, location=loc, rotation=rot)
        o = bpy.context.active_object
        o.name = name
        bpy.ops.object.shade_smooth()
        o.data.materials.append(m)
        return o

    def prism(name, loc, scale, rot, m, bev_w=0.04):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
        o = bpy.context.active_object
        o.name = name
        o.scale = scale
        bpy.ops.object.transform_apply(scale=True)
        b = o.modifiers.new("Bevel", "BEVEL")
        b.width = bev_w
        b.segments = 4
        bpy.ops.object.shade_smooth()
        o.data.materials.append(m)
        return o

    def encode_clip(fdir: Path, out_mp4: Path, tw: int, th: int, dur: float):
        raw_mp4 = fdir.with_suffix(".raw.mp4")
        subprocess.run([
            FFMPEG, "-y", "-v", "error", "-framerate", "30", "-i", str(fdir / "f_%04d.png"),
            "-vf", f"scale={tw}:{th}:flags=lanczos", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", str(raw_mp4),
        ], check=True)
        subprocess.run([
            FFMPEG, "-y", "-v", "error", "-stream_loop", "-1", "-i", str(raw_mp4), "-t", f"{dur + 0.5:.3f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(out_mp4),
        ], check=True)

    m_a = mat("AccentA", cfg["accent_a"], metal=0.15, rough=0.12, em_rgb=cfg["accent_a"], em_str=2.2)
    m_b = mat("AccentB", cfg["accent_b"], metal=0.15, rough=0.12, em_rgb=cfg["accent_b"], em_str=2.2)
    m_glass = mat("OptGlass", (0.78, 0.90, 1.0), metal=0.05, rough=0.02, coat=1.0, trans=0.88, ior=1.52)
    m_metal = mat("DarkMetal", (0.14, 0.17, 0.24), metal=0.95, rough=0.14, coat=0.9)
    m_porc = mat("Porcelain", (0.86, 0.87, 0.90), metal=0.05, rough=0.22, coat=0.6)

    def make_mats():
        return (
            mat("AccentA", cfg["accent_a"], metal=0.20, rough=0.14, em_rgb=cfg["accent_a"], em_str=0.95),
            mat("AccentB", cfg["accent_b"], metal=0.20, rough=0.14, em_rgb=cfg["accent_b"], em_str=0.95),
            mat("OptGlass", (0.28, 0.70, 0.96), metal=0.05, rough=0.03, coat=1.0, trans=0.72, ior=1.52),
            mat("DarkMetal", (0.09, 0.11, 0.16), metal=0.95, rough=0.16, coat=0.9),
            mat("Porcelain", (0.76, 0.78, 0.82), metal=0.04, rough=0.24, coat=0.65),
        )

    specs_clips = [
        ("frames_01_a", "b3d_01_abertura.mp4", 540, 672, 1080, 1344, durs[0], 0),
        ("frames_02_b", "b3d_02_bloco_a.mp4", 540, 960, 1080, 1920, durs[1], 1),
        ("frames_03_c", "b3d_03_bloco_b.mp4", 540, 960, 1080, 1920, durs[2], 2),
        ("frames_04_d", "b3d_04_fechamento.mp4", 540, 672, 1080, 1344, durs[3], 3),
    ]

    for fname, mp4name, rx, ry, tw, th, dur, cidx in specs_clips:
        fdir = bdir / fname
        fdir.mkdir(parents=True, exist_ok=True)
        out_mp4 = bdir / mp4name
        if out_mp4.is_file() and out_mp4.stat().st_size > 20000:
            print(f"  [REUSE] {out_mp4}", flush=True)
            continue

        clear_scene()
        sc = setup_scene(rx, ry)
        lights()
        floor()
        ma, mb, mg, mm, mp = make_mats()
        theme = cfg["theme"]

        # Distinct hero architecture per theme & clip!
        anim_objs = []
        if theme == "optical":
            lens = torus("LensRing", (0, 0.15, 0.28), 0.92, 0.15, (1.35, 0.0, 0.15), mg)
            r_vid = torus("VideoRing", (0, 0.15, 0.28), 1.24, 0.024, (1.20, 0.35, 0.0), ma)
            r_aud = torus("AudioRing", (0, 0.15, 0.28), 1.42, 0.022, (1.05, -0.45, 0.0), mb)
            core = sphere("OpticalCore", (0, 0.15, 0.28), 0.38, ma)
            bars = [prism(f"WBar_{k}", (-0.96 + k * 0.24, -0.35, -0.82), (0.10, 0.10, 0.38 + 0.28 * (k % 3)), (0, 0, 0), ma if k % 2 == 0 else mb, 0.02) for k in range(9)] if cidx in (1, 2) else []
            cam = cam_at((0, -5.6 if cidx in (0, 3) else -6.4, 0.55), (0, 0.1, 0.05), 35.0)
            for f in range(1, LOOP_FRAMES + 1):
                th_a = 2 * math.pi * ((f - 1) / LOOP_FRAMES)
                lens.rotation_euler = (1.35 + 0.16 * math.sin(th_a), 0.15 * math.cos(th_a), th_a)
                r_vid.rotation_euler = (1.20, 0.35 + th_a, th_a * 2.0)
                r_aud.rotation_euler = (1.05, -0.45 - th_a, -th_a)
                core.location = (0, 0.15, 0.28 + 0.08 * math.sin(th_a * 2))
                for k, b in enumerate(bars):
                    s = 0.55 + 0.45 * abs(math.sin(th_a * 2 + k * 0.55))
                    b.scale = (1.0, 1.0, s)
                cam.location = (0.18 * math.sin(th_a), (-5.6 if cidx in (0, 3) else -6.4) + 0.15 * math.cos(th_a), 0.55)
                cam.rotation_euler = (Vector((0, 0.1, 0.05)) - Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()
                sc.render.filepath = str(fdir / f"f_{f:04d}.png")
                bpy.ops.render.render(write_still=True)

        elif theme == "porcelain":
            plinth = prism("LabPlinth", (0, 0.3, -1.02), (3.1, 1.6, 0.28), (0, 0, 0), mm, 0.04)
            col_base = prism("BaselineCol", (-0.82, 0.2, -0.22), (0.48, 0.48, 1.25), (0, 0, 0), mp, 0.04)
            col_drop = prism("DropCol", (0.0, 0.2, -0.52), (0.48, 0.48, 0.68), (0, 0, 0), ma, 0.04)
            col_erqa = prism("GainCol", (0.82, 0.2, -0.05), (0.48, 0.48, 1.55), (0, 0, 0), mb if cidx >= 2 else mp, 0.04)
            gyro = torus("CoppGyro", (0, 0.2, 0.45), 1.18, 0.024, (1.42, 0.20, 0.0), mat("CopperRing", (0.86, 0.52, 0.18), metal=0.95, rough=0.14))
            cam = cam_at((0, -5.9 if cidx in (0, 3) else -6.7, 0.85), (0, 0.2, -0.05), 35.0)
            for f in range(1, LOOP_FRAMES + 1):
                th_a = 2 * math.pi * ((f - 1) / LOOP_FRAMES)
                col_drop.scale = (1.0, 1.0, 0.88 + 0.16 * math.sin(th_a * 2))
                col_erqa.scale = (1.0, 1.0, 0.92 + 0.12 * math.cos(th_a * 2))
                gyro.rotation_euler = (1.42 + 0.12 * math.sin(th_a), 0.20 + 0.15 * math.cos(th_a), th_a)
                cam.location = (0.24 * math.sin(th_a), (-5.9 if cidx in (0, 3) else -6.7), 0.85 + 0.10 * math.sin(th_a * 2))
                cam.rotation_euler = (Vector((0, 0.2, -0.05)) - Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()
                sc.render.filepath = str(fdir / f"f_{f:04d}.png")
                bpy.ops.render.render(write_still=True)

        elif theme == "arena":
            beam = prism("DividerBeam", (0, 0.35, -0.92), (3.1, 0.28, 0.22), (0, 0, 0), mm, 0.03)
            cube_l = prism("BonsaiCube", (-0.78, 0.15, 0.12), (0.68, 0.68, 0.68), (0.3, 0.4, 0.5), ma, 0.06)
            ring_l = torus("BonsaiHalo", (-0.78, 0.15, 0.12), 0.58, 0.022, (1.3, 0.2, 0), ma)
            stack_r = [prism(f"InkLoop_{k}", (0.78, 0.15, -0.32 + k * 0.32), (0.76, 0.76, 0.18), (0, 0, 0.4 * k), mb if k != 1 else mm, 0.04) for k in range(3)]
            cam = cam_at((0, -5.9 if cidx in (0, 3) else -6.6, 0.72), (0, 0.15, 0.0), 34.0)
            for f in range(1, LOOP_FRAMES + 1):
                th_a = 2 * math.pi * ((f - 1) / LOOP_FRAMES)
                cube_l.rotation_euler = (0.3 + 0.4 * math.sin(th_a), 0.4 + th_a, 0.5)
                ring_l.rotation_euler = (1.3, 0.2 - th_a, th_a)
                for k, st in enumerate(stack_r):
                    st.rotation_euler = (0, 0, th_a * (1 if k % 2 == 0 else -1) + 0.4 * k)
                    st.location = (0.78, 0.15, -0.32 + k * 0.32 + 0.07 * math.sin(th_a * 2 + k))
                cam.location = (0.20 * math.sin(th_a), (-5.9 if cidx in (0, 3) else -6.6) + 0.16 * math.cos(th_a), 0.72)
                cam.rotation_euler = (Vector((0, 0.15, 0.0)) - Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()
                sc.render.filepath = str(fdir / f"f_{f:04d}.png")
                bpy.ops.render.render(write_still=True)

        elif theme == "tungsten":
            slab = prism("LightTable", (0, 0.3, -1.04), (3.3, 2.0, 0.20), (0, 0, 0), mm, 0.04)
            step_bars = [prism(f"MergeStep_{k}", (-0.96 + k * 0.48, 0.25, -0.72 + k * 0.20), (0.32, 0.32, 0.38 + k * 0.34), (0, 0, 0), ma if k >= 3 else mp, 0.03) for k in range(5)]
            gear_a = torus("ScionGearA", (0.12, 0.15, 0.68), 0.78, 0.068, (1.45, 0.0, 0.0), ma)
            gear_b = torus("ScionGearB", (-0.68, -0.15, 0.42), 0.48, 0.048, (1.45, 0.2, 0.0), mm)
            cam = cam_at((0, -6.1 if cidx in (0, 3) else -6.8, 0.90), (0, 0.2, 0.05), 35.0)
            for f in range(1, LOOP_FRAMES + 1):
                th_a = 2 * math.pi * ((f - 1) / LOOP_FRAMES)
                gear_a.rotation_euler = (1.45, th_a, 0.08 * math.sin(th_a))
                gear_b.rotation_euler = (1.45, 0.2 - th_a * 2.0, 0.0)
                for k, sb in enumerate(step_bars):
                    sb.scale = (1.0, 1.0, 0.92 + 0.10 * math.sin(th_a * 2 - k * 0.5))
                cam.location = (0.22 * math.sin(th_a), (-6.1 if cidx in (0, 3) else -6.8), 0.90 + 0.10 * math.cos(th_a))
                cam.rotation_euler = (Vector((0, 0.2, 0.05)) - Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()
                sc.render.filepath = str(fdir / f"f_{f:04d}.png")
                bpy.ops.render.render(write_still=True)

        elif theme == "circuit":
            rails = [prism(f"BusRail_{k}", (0, 0.2, -1.02), (3.2, 0.08, 0.06), (0, 0, (k - 1) * 0.22), mb if cidx >= 2 else ma, 0.01) for k in range(3)]
            shield = prism("ReadOnlyBarrier", (0, 0.2, 0.20), (1.45, 0.16, 1.25), (0, 0, 0.05), mg, 0.04)
            packet = sphere("PacketNode", (-1.1, -0.25, -0.25), 0.24, mb if cidx >= 2 else ma)
            ring_sec = torus("ShieldOrbit", (0, 0.2, 0.20), 1.08, 0.025, (1.38, 0.15, 0), mb if cidx >= 2 else ma)
            cam = cam_at((0, -5.8 if cidx in (0, 3) else -6.5, 0.70), (0, 0.2, 0.05), 35.0)
            for f in range(1, LOOP_FRAMES + 1):
                th_a = 2 * math.pi * ((f - 1) / LOOP_FRAMES)
                shield.rotation_euler = (0.05 * math.sin(th_a), 0, 0.08 * math.cos(th_a))
                packet.location = (1.15 * math.sin(th_a), -0.35, -0.22 + 0.20 * math.cos(th_a * 2))
                ring_sec.rotation_euler = (1.38 + 0.12 * math.sin(th_a), 0.15 + th_a, -th_a)
                cam.location = (0.18 * math.sin(th_a), (-5.8 if cidx in (0, 3) else -6.5) + 0.14 * math.cos(th_a), 0.70)
                cam.rotation_euler = (Vector((0, 0.2, 0.05)) - Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()
                sc.render.filepath = str(fdir / f"f_{f:04d}.png")
                bpy.ops.render.render(write_still=True)

        else:  # blueprint / world models
            s1 = prism("Step1_Plausible", (-0.86, 0.35, -0.78), (0.68, 0.95, 0.42), (0, 0, 0), mm, 0.03)
            s2 = prism("Step2_Controllable", (0.0, 0.35, -0.56), (0.68, 0.95, 0.84), (0, 0, 0), ma, 0.03)
            s3 = prism("Step3_Actionable", (0.86, 0.35, -0.32), (0.68, 0.95, 1.30), (0, 0, 0), mb, 0.03)
            world_orb = sphere("WorldHorizonOrb", (0, -0.05, 0.85), 0.44, mb)
            cage_ring = torus("BlueMeshRing", (0, -0.05, 0.85), 0.72, 0.022, (1.28, 0.22, 0), ma)
            cam = cam_at((0, -5.9 if cidx in (0, 3) else -6.6, 0.85), (0, 0.15, 0.12), 34.0)
            for f in range(1, LOOP_FRAMES + 1):
                th_a = 2 * math.pi * ((f - 1) / LOOP_FRAMES)
                world_orb.location = (0.28 * math.sin(th_a), -0.05, 0.85 + 0.09 * math.sin(th_a * 2))
                cage_ring.location = world_orb.location
                cage_ring.rotation_euler = (1.28 + 0.25 * math.sin(th_a), 0.22 + th_a, th_a * 2)
                s2.scale = (1.0, 1.0, 0.92 + 0.10 * math.sin(th_a))
                s3.scale = (1.0, 1.0, 0.92 + 0.12 * math.cos(th_a))
                cam.location = (0.22 * math.sin(th_a), (-5.9 if cidx in (0, 3) else -6.6) + 0.14 * math.cos(th_a), 0.85)
                cam.rotation_euler = (Vector((0, 0.15, 0.12)) - Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()
                sc.render.filepath = str(fdir / f"f_{f:04d}.png")
                bpy.ops.render.render(write_still=True)

        encode_clip(fdir, out_mp4, tw, th, dur)
        print(f"  [OK] {out_mp4}", flush=True)

    return 0


if __name__ == "__main__":
    if "--render-one" in sys.argv:
        idx = sys.argv.index("--render-one")
        raise SystemExit(_blender_main(sys.argv[idx + 1]))
    raise SystemExit(run_driver())
