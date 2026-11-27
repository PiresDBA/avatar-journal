"""Build and optionally render all 6 distinct HyperFrames --strict Shorts projects."""

from __future__ import annotations

import html
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(r"D:\Utilitarios\avatar-journal")
OUT_ROOT = REPO_ROOT / "output" / "2026-11-26"
NPX_EXE = r"C:\Program Files\nodejs\npx.cmd"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.batch_6days.specs import SHORTS_6DAYS  # noqa: E402


def link_or_copy(src: Path, dst: Path) -> None:
    if not src.is_file():
        raise FileNotFoundError(f"Missing required asset: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def format_caption_html(chunks: list[tuple[str, bool]]) -> str:
    parts = []
    for txt, hl in chunks:
        esc = html.escape(txt)
        parts.append(f'<span class="cap-hl">{esc}</span>' if hl else esc)
    return "".join(parts)


def split_caption_cues(raw_chunks: list[tuple[str, bool]], t0: float, t1: float) -> list[tuple[float, float, str]]:
    total_len = sum(len(t) for t, _ in raw_chunks)
    if total_len <= 92 or len(raw_chunks) < 3:
        return [(t0, t1, format_caption_html(raw_chunks))]

    # Find sentence boundary near midpoint (uppercase start after running chars >= 35)
    acc = 0
    best_idx = None
    best_dist = 10**9
    target = total_len * 0.5
    for i, (txt, _) in enumerate(raw_chunks):
        if i > 0 and acc >= 32 and txt and txt[0].isupper():
            dist = abs(acc - target)
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        acc += len(txt)
    if best_idx is None:
        best_idx = max(1, len(raw_chunks) // 2)

    left = raw_chunks[:best_idx]
    right = raw_chunks[best_idx:]
    w_left = max(1, sum(len(t) for t, _ in left))
    w_right = max(1, sum(len(t) for t, _ in right))
    t_mid = round(t0 + (t1 - t0) * (w_left / (w_left + w_right)), 3)
    return [
        (t0, t_mid, format_caption_html(left)),
        (t_mid, t1, format_caption_html(right)),
    ]


def build_subcomposition_html(spec: dict, scene_idx: int, dur: float) -> str:
    sc = spec["scenes"][scene_idx]
    st = spec["style"]
    day = spec["day_key"]
    comp_id = f"ov_{scene_idx + 1:02d}"
    is_avatar_scene = scene_idx in (0, 3)

    bg = st["bg"]
    acc1 = st["accent"]
    acc2 = st["accent2"]
    acc3 = st.get("accent3", acc1)
    card_bg = st["card_bg"]
    stage_pad = "152px 52px 0 52px" if is_avatar_scene else "152px 52px 436px 52px"
    stage_h = "1168px" if is_avatar_scene else "1920px"

    tone_colors = {"accent": acc1, "accent2": acc2, "accent3": acc3, "light": "#f8fafc"}

    cards_html = []
    for i, card in enumerate(sc["cards"]):
        c_col = tone_colors.get(card.get("tone", "accent"), acc1)
        cards_html.append(
            f'<div class="m-card" id="mc-{i}" style="border-color:{c_col};">'
            f'<div class="m-lbl">{html.escape(card["lbl"])}</div>'
            f'<div class="m-val" style="color:{c_col};">{html.escape(card["val"])}</div>'
            f"</div>"
        )
    cards_block = "".join(cards_html)

    # Distinct visual CSS & canvas/SVG treatment per day_key
    extra_css = {
        "segunda": f"""
            .hdr-card {{ border-radius: 26px; border: 2px solid {acc1}; backdrop-filter: blur(8px); }}
            .kicker {{ border-radius: 999px; }}
            .m-card {{ border-radius: 22px; background: rgba(6, 12, 26, 0.90); }}
        """,
        "terca": f"""
            .hdr-card {{ border-radius: 14px; border-left: 8px solid {acc1}; border-top: 1px solid rgba(255,255,255,0.16); }}
            .kicker {{ border-radius: 6px; }}
            .m-card {{ border-radius: 14px; border-top-width: 4px; background: rgba(18, 21, 30, 0.93); }}
        """,
        "quarta": f"""
            .hdr-card {{ border-radius: 18px; border: 2px solid {acc1}; box-shadow: 0 0 36px rgba(16,185,129,0.22); }}
            .kicker {{ border-radius: 4px; letter-spacing: 0.08em; }}
            .m-card {{ border-radius: 16px; background: rgba(6, 10, 24, 0.92); }}
        """,
        "sexta": f"""
            .hdr-card {{ border-radius: 10px; border: 2px solid {acc1}; border-left: 10px solid {acc1}; }}
            .kicker {{ border-radius: 4px; }}
            .m-card {{ border-radius: 10px; background: rgba(22, 19, 14, 0.94); }}
        """,
        "sabado": f"""
            .hdr-card {{ border-radius: 12px; border: 2px solid {acc2}; box-shadow: 0 0 30px rgba(239,68,68,0.22); }}
            .kicker {{ border-radius: 4px; }}
            .m-card {{ border-radius: 12px; border-left-width: 6px; background: rgba(12, 12, 16, 0.94); }}
        """,
        "domingo": f"""
            .hdr-card {{ border-radius: 16px; border: 2px dashed {acc1}; background: rgba(9, 17, 40, 0.90); }}
            .kicker {{ border-radius: 6px; }}
            .m-card {{ border-radius: 14px; border: 1.5px solid {acc1}; background: rgba(9, 17, 40, 0.92); }}
        """,
    }[day]

    # Mid-stage procedural canvas keeps center 3D object visible while animating edge/rail graphics in every band
    mid_h = 460 if is_avatar_scene else 720
    sub_js = f"""
      const canvas = document.getElementById("viz-canvas");
      const ctx = canvas.getContext("2d");
      const W = canvas.width, H = canvas.height;
      const DAY = {json.dumps(day)};
      const SIDX = {scene_idx};
      const C1 = {json.dumps(acc1)}, C2 = {json.dumps(acc2)}, C3 = {json.dumps(acc3)};

      function drawViz(t) {{
        ctx.clearRect(0, 0, W, H);
        // Side rail vertical guides keep B2 and B3 visually active without hiding central Blender 3D hero
        ctx.save();
        if (DAY === "segunda") {{
          // Dual optical audio + video waveforms across top-mid & lower-mid rails
          const pts = 64;
          for (let band = 0; band < 2; band++) {{
            const baseY = band === 0 ? 58 : H - 54;
            ctx.beginPath();
            ctx.strokeStyle = band === 0 ? C1 : C2;
            ctx.lineWidth = 4;
            for (let i = 0; i <= pts; i++) {{
              const x = 18 + (W - 36) * (i / pts);
              const env = Math.sin(Math.PI * (i / pts));
              const y = baseY + env * 28 * Math.sin(t * (band ? 7.2 : 5.6) + i * 0.36 + band * 1.4);
              if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            }}
            ctx.stroke();
          }}
          // Refraction reticle corners
          ctx.strokeStyle = "rgba(56,189,248,0.55)";
          ctx.lineWidth = 2.5;
          const r = 14 + 4 * Math.sin(t * 3.0);
          [[36,90],[W-36,90],[36,H-90],[W-36,H-90]].forEach(([cx, cy]) => {{
            ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();
          }});
        }} else if (DAY === "terca") {{
          // Scientific porcelain & copper benchmark gauge rails on left & right
          const bars = [
            {{ lbl: "BASE", pct: 0.72, col: "#94a3b8" }},
            {{ lbl: "VLM+GEN", pct: 0.56 + 0.04 * Math.sin(t * 2.5), col: C2 }},
            {{ lbl: "VSTAR", pct: 0.36 + 0.05 * Math.cos(t * 2.8), col: C2 }},
            {{ lbl: "ERQA 10x", pct: 0.84 + 0.04 * Math.sin(t * 2.2), col: C3 }}
          ];
          bars.forEach((b, idx) => {{
            const x = idx < 2 ? 20 + idx * 54 : W - 122 + (idx - 2) * 54;
            const maxH = H * 0.56;
            const y0 = (H - maxH) / 2;
            ctx.fillStyle = "rgba(255,255,255,0.08)";
            ctx.fillRect(x, y0, 36, maxH);
            const hFill = maxH * b.pct;
            ctx.fillStyle = b.col;
            ctx.fillRect(x, y0 + maxH - hFill, 36, hFill);
            ctx.fillStyle = "#f8fafc";
            ctx.font = "800 13px 'JetBrains Mono', monospace";
            ctx.fillText(b.lbl, x - 4, y0 + maxH + 22);
          }});
        }} else if (DAY === "quarta") {{
          // Split arena battle rails (Emerald Bonsai vs Indigo Inkling)
          ctx.fillStyle = "rgba(16,185,129,0.16)";
          ctx.fillRect(10, 20, 178, 44);
          ctx.strokeStyle = C1; ctx.lineWidth = 2; ctx.strokeRect(10, 20, 178, 44);
          ctx.fillStyle = C1; ctx.font = "900 17px Outfit, sans-serif";
          ctx.fillText("BONSAI · 5,93 GB", 20, 48);

          ctx.fillStyle = "rgba(99,102,241,0.18)";
          ctx.fillRect(W - 210, 20, 200, 44);
          ctx.strokeStyle = C2; ctx.strokeRect(W - 210, 20, 200, 44);
          ctx.fillStyle = "#c7d2fe";
          ctx.fillText("INKLING · 3x LOOP", W - 196, 48);

          // Animated dual progress arcs on left/right edges
          const a1 = 0.25 + 0.65 * (0.5 + 0.5 * Math.sin(t * 2.4));
          ctx.lineWidth = 6;
          ctx.strokeStyle = C1;
          ctx.beginPath(); ctx.arc(62, H * 0.54, 40, -Math.PI/2, -Math.PI/2 + Math.PI * 1.65 * a1); ctx.stroke();
          ctx.strokeStyle = C2;
          ctx.beginPath(); ctx.arc(W - 62, H * 0.54, 40, -Math.PI/2, -Math.PI/2 + Math.PI * 1.35 * (1.2 - a1 * 0.4)); ctx.stroke();
        }} else if (DAY === "sexta") {{
          // Tungsten editorial curve (2.5k -> 30k+ merges/day) anchored along bottom rail
          ctx.strokeStyle = "rgba(245,158,11,0.28)";
          ctx.lineWidth = 1.5;
          for (let g = 0; g < 4; g++) {{
            const gy = 30 + g * ((H - 60) / 3);
            ctx.beginPath(); ctx.moveTo(16, gy); ctx.lineTo(W - 16, gy); ctx.stroke();
          }}
          ctx.beginPath();
          ctx.strokeStyle = C1;
          ctx.lineWidth = 4.5;
          const prog = Math.min(1, 0.35 + (t / {dur:.2f}) * 0.65);
          const steps = 42;
          for (let i = 0; i <= Math.floor(steps * prog); i++) {{
            const u = i / steps;
            const x = 24 + u * (W - 48);
            const y = H - 38 - Math.pow(u, 2.3) * (H * 0.32);
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
          }}
          ctx.stroke();
          ctx.fillStyle = C1; ctx.font = "800 16px 'JetBrains Mono', monospace";
          ctx.fillText("MAI: 2.500/DIA", 24, H - 14);
          ctx.fillText("SET: 30.000+/DIA", W - 188, H - 14);
        }} else if (DAY === "sabado") {{
          // PCB bus lines + traveling packet dot on top/bottom border of viewport
          const railCol = SIDX >= 2 ? C3 : C2;
          ctx.strokeStyle = railCol;
          ctx.lineWidth = 3;
          [34, H - 34].forEach((ry, idx) => {{
            ctx.beginPath();
            ctx.moveTo(18, ry); ctx.lineTo(W * 0.32, ry); ctx.lineTo(W * 0.38, ry + (idx ? -16 : 16));
            ctx.lineTo(W * 0.62, ry + (idx ? -16 : 16)); ctx.lineTo(W * 0.68, ry); ctx.lineTo(W - 18, ry);
            ctx.stroke();
            const px = 24 + (((t * 280) + idx * 340) % (W - 48));
            ctx.fillStyle = idx === 0 ? C1 : railCol;
            ctx.beginPath(); ctx.arc(px, ry, 8, 0, Math.PI * 2); ctx.fill();
          }});
          ctx.fillStyle = railCol; ctx.font = "900 16px 'JetBrains Mono', monospace";
          ctx.fillText(SIDX >= 2 ? "SANDBOX VERIFICADO" : "BYPASS DETECTADO", 24, 24);
        }} else {{
          // Domingo blueprint grid corners + 3-rung elevation markers
          ctx.strokeStyle = "rgba(56,189,248,0.22)";
          ctx.lineWidth = 1.5;
          for (let gx = 40; gx < W; gx += 110) {{
            ctx.beginPath(); ctx.moveTo(gx, 14); ctx.lineTo(gx, 32); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(gx, H - 32); ctx.lineTo(gx, H - 14); ctx.stroke();
          }}
          const rungs = ["1. PLAUSIBLE", "2. CONTROLLABLE", "3. ACTIONABLE"];
          rungs.forEach((txt, idx) => {{
            const ry = H - 36 - idx * 38;
            const pulse = 0.72 + 0.28 * Math.sin(t * 3.0 - idx * 0.8);
            ctx.fillStyle = idx === 2 ? C2 : C1;
            ctx.globalAlpha = pulse;
            ctx.fillRect(18, ry - 14, 14 + idx * 10, 14);
            ctx.font = "800 15px 'JetBrains Mono', monospace";
            ctx.fillText(txt, 48 + idx * 10, ry - 2);
            ctx.globalAlpha = 1;
          }});
        }}
        ctx.restore();
      }}
    """

    cta_pills = {
        "segunda": "COMENTE: QUAL CENA VOCÊ TESTARIA NO LTX-2.5?",
        "terca": "COMENTE: VOCÊ JÁ TESTOU RASCUNHO VISUAL NA IA?",
        "quarta": "COMENTE: BONSAI 5,93 GB OU INKLING MOE 3X?",
        "sexta": "COMENTE: SEU TIME JÁ SENTIU ESSE GARGALO?",
        "sabado": "COMENTE: VOCÊ AUDITA SEUS PLUGINS MCP?",
        "domingo": "COMENTE: EM QUAL SETOR CHEGA PRIMEIRO?",
    }
    cta_block = (
        f'<div class="cta-pill" id="cta-pill">{html.escape(cta_pills[day])}</div>'
        if scene_idx == 3 else ""
    )

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{ width: 1080px; height: 1920px; overflow: hidden; background: transparent; font-family: Outfit, Inter, sans-serif; color: #f8fafc; }}
    #top-grad {{ position: absolute; left: 0; right: 0; top: 0; height: 410px; background: linear-gradient(180deg, rgba(4,7,14,0.90) 0%, rgba(4,7,14,0.52) 68%, rgba(4,7,14,0) 100%); }}
    #stage {{ position: relative; width: 1080px; height: {stage_h}; padding: {stage_pad}; display: flex; flex-direction: column; justify-content: space-between; }}
    .hdr-card {{
      background: {card_bg};
      padding: 20px 26px; box-shadow: 0 18px 42px rgba(0, 0, 0, 0.58);
    }}
    .kicker {{
      display: inline-block; padding: 5px 14px;
      background: rgba(255, 255, 255, 0.08); border: 1.5px solid {acc1};
      color: {acc1}; font-family: "JetBrains Mono", monospace; font-size: 19px; font-weight: 800; margin-bottom: 10px;
    }}
    h1 {{ font-size: 46px; font-weight: 900; line-height: 1.07; color: #f8fafc; }}
    .sub {{ margin-top: 8px; font-family: Inter, sans-serif; font-size: 22px; font-weight: 600; color: #cbd5e1; line-height: 1.25; }}
    #mid-viz {{ flex: 1; position: relative; display: flex; align-items: center; justify-content: center; }}
    #viz-canvas {{ width: 976px; height: {mid_h}px; display: block; }}
    .metrics-row {{
      display: grid; grid-template-columns: repeat({len(sc["cards"])}, 1fr); gap: 14px;
      margin-bottom: {"18px" if is_avatar_scene else "0"};
    }}
    .m-card {{
      border: 2px solid {acc1}; padding: 14px 16px;
      box-shadow: 0 12px 28px rgba(0, 0, 0, 0.55);
    }}
    .m-lbl {{ font-family: "JetBrains Mono", monospace; font-size: 15px; font-weight: 700; color: #cbd5e1; letter-spacing: 0.05em; margin-bottom: 5px; }}
    .m-val {{ font-family: Outfit, sans-serif; font-size: 27px; font-weight: 900; line-height: 1.1; }}
    .cta-pill {{
      align-self: center; margin-bottom: 12px; padding: 10px 22px; border-radius: 999px;
      background: rgba(7, 10, 18, 0.94); border: 2px solid {acc1};
      color: {acc1}; font-family: "JetBrains Mono", monospace; font-size: 20px; font-weight: 800; letter-spacing: 0.03em;
      box-shadow: 0 10px 26px rgba(0, 0, 0, 0.55);
    }}
    {extra_css}
  </style>
</head>
<body>
  <div id="scene" data-composition-id="{comp_id}" data-width="1080" data-height="1920" data-fps="30" data-duration="{dur:.3f}">
    <div id="top-grad"></div>
    <div id="stage">
      <div class="hdr-card" id="hdr-card">
        <div class="kicker">{html.escape(sc["kicker"])}</div>
        <h1>{html.escape(sc["headline"])}</h1>
        <div class="sub">{html.escape(sc["sub"])}</div>
      </div>
      <div id="mid-viz"><canvas id="viz-canvas" width="976" height="{mid_h}"></canvas></div>
      {cta_block}
      <div class="metrics-row">{cards_block}</div>
    </div>
  </div>
  <script>
    const hdr = document.getElementById("hdr-card");
    const cards = Array.from(document.querySelectorAll(".m-card"));
    {sub_js}
    const tl = gsap.timeline({{ paused: true }});
    tl.fromTo(hdr, {{ y: 12, opacity: 0.94 }}, {{ y: 0, opacity: 1, duration: 0.40, ease: "power2.out" }}, 0);
    cards.forEach((c, i) => {{
      tl.fromTo(c, {{ y: 16, opacity: 0.90 }}, {{ y: 0, opacity: 1, duration: 0.42, ease: "power2.out" }}, 0.06 * i);
    }});
    tl.to({{}}, {{
      duration: {dur:.3f},
      onUpdate: function () {{ drawViz(tl.time()); }}
    }}, 0);
    drawViz(0);
    window.__timelines = window.__timelines || {{}};
    window.__timelines["{comp_id}"] = tl;
  </script>
</body>
</html>
"""


def build_root_index_html(spec: dict, timings: dict) -> str:
    st = spec["style"]
    segs = timings["segments"]
    total_dur = float(timings["total_duration"])

    s0_t0 = 0.0
    s0_dur = round(float(segs[1]["start"]), 3)
    s1_t0 = float(segs[1]["start"])
    s1_dur = round(float(segs[2]["start"]) - s1_t0, 3)
    s2_t0 = float(segs[2]["start"])
    s2_dur = round(float(segs[3]["start"]) - s2_t0, 3)
    s3_t0 = float(segs[3]["start"])
    s3_dur = round(total_dur - s3_t0, 3)

    s3_end = float(segs[3]["end"])
    av_seg2_dur = round(s3_end - s3_t0, 3)
    av_hold1_start = round(max(0.0, s0_dur - 0.12), 3)
    av_hold1_dur = round((s0_dur - av_hold1_start) + 0.04, 3)
    av_hold2_start = round(max(s3_t0, s3_end - 0.08), 3)
    av_hold2_dur = round(max(0.18, total_dur - av_hold2_start), 3)

    cuts = [s1_t0, s2_t0, s3_t0]

    cues: list[dict] = []
    seg_windows = [(0.0, s0_dur), (s1_t0, s2_t0), (s2_t0, s3_t0), (s3_t0, total_dur)]
    for i, (t0, t1) in enumerate(seg_windows):
        sc = spec["scenes"][i]
        sub_cues = split_caption_cues(spec["captions"][i], t0, t1)
        for ct0, ct1, cap_html in sub_cues:
            cues.append({
                "t0": round(ct0, 3),
                "t1": round(ct1, 3),
                "segIdx": i,
                "segT0": round(t0, 3),
                "segT1": round(t1, 3),
                "lbl": sc["lbl"],
                "col": sc["col"],
                "cap": cap_html,
            })

    bg = st["bg"]
    acc1 = st["accent"]
    acc2 = st["accent2"]
    pill_fg = st["pill_fg"]

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=1080, height=1920" />
  <title>{html.escape(spec["title"])}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@600;700;800&family=JetBrains+Mono:wght@600;700;800&family=Outfit:wght@700;800;900&display=swap" rel="stylesheet" />
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{ width: 1080px; height: 1920px; overflow: hidden; background: {bg}; font-family: Inter, system-ui, sans-serif; }}
    #root {{ position: relative; width: 1080px; height: 1920px; overflow: hidden; background: {bg}; }}
    #root > div[data-composition-src] {{ position: absolute; inset: 0; }}

    #stories-hud {{
      position: absolute; top: 36px; left: 48px; right: 48px; z-index: 40;
      display: flex; flex-direction: column; gap: 14px; pointer-events: none;
    }}
    #stories-track {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }}
    .st-seg {{ height: 8px; border-radius: 99px; background: rgba(148, 163, 184, 0.30); overflow: hidden; }}
    .st-fill {{ height: 100%; width: 100%; background: {acc1}; transform-origin: left center; }}
    #hud-meta {{ display: flex; justify-content: space-between; align-items: center; }}
    .brand-plate {{
      padding: 8px 22px; background: {acc1}; color: {pill_fg};
      border-left: 6px solid {acc2};
      font-family: Outfit, sans-serif; font-size: 21px; font-weight: 900; letter-spacing: 0.06em;
      transform: skewX(-10deg);
      box-shadow: 0 6px 18px rgba(0, 0, 0, 0.45);
    }}
    .brand-plate > span {{ display: inline-block; transform: skewX(10deg); }}
    .hud-pill {{
      padding: 8px 18px; border-radius: 10px;
      background: rgba(11, 15, 25, 0.92); border: 1.5px solid {acc1};
      color: #f8fafc; font-family: "JetBrains Mono", monospace; font-size: 20px; font-weight: 800; letter-spacing: 0.05em;
    }}

    #wipe-band {{ position: absolute; inset: 0; z-index: 36; pointer-events: none; overflow: hidden; }}
    #wipe-strip {{ position: absolute; top: 0; bottom: 0; left: 0; width: 96px; display: flex; }}
    .wb-accent {{ width: 76px; height: 100%; background: {acc1}; }}
    .wb-ink {{ width: 6px; height: 100%; background: {bg}; }}
    .wb-gold {{ width: 14px; height: 100%; background: {acc2}; }}

    #av-divider {{ position: absolute; left: 0; top: 1341px; width: 1080px; height: 4px; background: {acc1}; z-index: 30; pointer-events: none; }}

    #captions {{
      position: absolute; left: 44px; right: 44px; top: 1188px; z-index: 42;
      display: flex; justify-content: center; pointer-events: none;
    }}
    .cap-box {{
      display: flex; align-items: center; gap: 18px;
      background: rgba(7, 10, 18, 0.94); border: 2px solid {acc1};
      border-radius: 18px; padding: 15px 24px; color: #f8fafc;
      font-family: Outfit, Inter, sans-serif; font-size: 33px; font-weight: 800; line-height: 1.22;
      text-align: center; box-shadow: 0 16px 40px rgba(0, 0, 0, 0.65);
    }}
    .cap-hl {{ color: {acc1}; }}
    .vp-bars {{ display: flex; align-items: flex-end; gap: 4px; height: 30px; flex-shrink: 0; }}
    .vp-b {{ width: 5px; height: 30px; border-radius: 3px; background: {acc1}; transform-origin: bottom center; }}
  </style>
</head>
<body>
  <div id="root" data-composition-id="root" data-width="1080" data-height="1920" data-fps="30" data-duration="{total_dur:.3f}">
    <audio id="audio-mix" data-media="audio" src="assets/final_mix.wav" data-start="0"></audio>

    <video id="vid-01" data-media="video" src="assets/b3d_01_abertura.mp4" data-start="0" data-duration="{s0_dur:.3f}" data-media-start="0" muted playsinline style="position:absolute;left:0;top:0;width:1080px;height:1344px;object-fit:cover;z-index:10;pointer-events:none;"></video>
    <div id="host-01" data-composition-id="ov_01" data-composition-src="compositions/ov_01.html" data-start="0" data-duration="{s0_dur:.3f}" style="z-index:11;"></div>

    <video id="vid-02" data-media="video" src="assets/b3d_02_bloco_a.mp4" data-start="{s1_t0:.3f}" data-duration="{s1_dur:.3f}" data-media-start="0" muted playsinline style="position:absolute;left:0;top:0;width:1080px;height:1920px;object-fit:cover;z-index:12;pointer-events:none;"></video>
    <div id="host-02" data-composition-id="ov_02" data-composition-src="compositions/ov_02.html" data-start="{s1_t0:.3f}" data-duration="{s1_dur:.3f}" style="z-index:13;"></div>

    <video id="vid-03" data-media="video" src="assets/b3d_03_bloco_b.mp4" data-start="{s2_t0:.3f}" data-duration="{s2_dur:.3f}" data-media-start="0" muted playsinline style="position:absolute;left:0;top:0;width:1080px;height:1920px;object-fit:cover;z-index:14;pointer-events:none;"></video>
    <div id="host-03" data-composition-id="ov_03" data-composition-src="compositions/ov_03.html" data-start="{s2_t0:.3f}" data-duration="{s2_dur:.3f}" style="z-index:15;"></div>

    <video id="vid-04" data-media="video" src="assets/b3d_04_fechamento.mp4" data-start="{s3_t0:.3f}" data-duration="{s3_dur:.3f}" data-media-start="0" muted playsinline style="position:absolute;left:0;top:0;width:1080px;height:1344px;object-fit:cover;z-index:16;pointer-events:none;"></video>
    <div id="host-04" data-composition-id="ov_04" data-composition-src="compositions/ov_04.html" data-start="{s3_t0:.3f}" data-duration="{s3_dur:.3f}" style="z-index:17;"></div>

    <video id="av-seg-01" data-media="video" src="assets/avatar_seg_01.mp4" data-start="0" data-duration="{s0_dur:.3f}" data-media-start="0" muted playsinline style="position:absolute;left:0;top:1344px;width:1080px;height:576px;object-fit:cover;z-index:27;pointer-events:none;"></video>
    <video id="av-hold-01" data-media="video" src="assets/avatar_hold_bar.mp4" data-start="{av_hold1_start:.3f}" data-duration="{av_hold1_dur:.3f}" data-media-start="0" muted playsinline style="position:absolute;left:0;top:1344px;width:1080px;height:576px;object-fit:cover;z-index:28;pointer-events:none;"></video>
    <video id="av-seg-02" data-media="video" src="assets/avatar_seg_02.mp4" data-start="{s3_t0:.3f}" data-duration="{av_seg2_dur:.3f}" data-media-start="0" muted playsinline style="position:absolute;left:0;top:1344px;width:1080px;height:576px;object-fit:cover;z-index:27;pointer-events:none;"></video>
    <video id="av-hold" data-media="video" src="assets/avatar_hold_bar.mp4" data-start="{av_hold2_start:.3f}" data-duration="{av_hold2_dur:.3f}" data-media-start="0" muted playsinline style="position:absolute;left:0;top:1344px;width:1080px;height:576px;object-fit:cover;z-index:28;pointer-events:none;"></video>
    <div id="av-divider"></div>

    <div id="wipe-band">
      <div id="wipe-strip"><div class="wb-accent"></div><div class="wb-ink"></div><div class="wb-gold"></div></div>
    </div>

    <div id="stories-hud">
      <div id="stories-track">
        <div class="st-seg"><div class="st-fill" id="sf-1"></div></div>
        <div class="st-seg"><div class="st-fill" id="sf-2"></div></div>
        <div class="st-seg"><div class="st-fill" id="sf-3"></div></div>
        <div class="st-seg"><div class="st-fill" id="sf-4"></div></div>
      </div>
      <div id="hud-meta">
        <div class="brand-plate"><span>{html.escape(spec["hud_brand"])}</span></div>
        <span class="hud-pill" id="hud-counter">{html.escape(spec["scenes"][0]["lbl"])}</span>
      </div>
    </div>

    <div id="captions">
      <div class="cap-box">
        <div class="vp-bars" aria-hidden="true">
          <div class="vp-b" id="vp-1"></div><div class="vp-b" id="vp-2"></div><div class="vp-b" id="vp-3"></div><div class="vp-b" id="vp-4"></div><div class="vp-b" id="vp-5"></div>
        </div>
        <div id="cap-text"></div>
      </div>
    </div>
  </div>

  <script>
    const cuts = {json.dumps(cuts)};
    const cues = {json.dumps(cues, ensure_ascii=False)};
    const segBounds = {json.dumps([[round(t0, 3), round(t1, 3), spec["scenes"][i]["col"]] for i, (t0, t1) in enumerate(seg_windows)])};
    const S0_END = {s0_dur:.3f};
    const S3_START = {s3_t0:.3f};

    const counterEl = document.getElementById("hud-counter");
    const capWrap = document.getElementById("captions");
    const capEl = document.getElementById("cap-text");
    const avDiv = document.getElementById("av-divider");
    const wipeEl = document.getElementById("wipe-strip");
    const fills = Array.from({{ length: 4 }}, (_, i) => document.getElementById("sf-" + (i + 1)));
    const vpBars = Array.from({{ length: 5 }}, (_, i) => document.getElementById("vp-" + (i + 1)));

    const tl = gsap.timeline({{ paused: true }});
    gsap.set(wipeEl, {{ x: -160 }});
    for (const tc of cuts) {{
      tl.fromTo(wipeEl, {{ x: -140 }}, {{ x: 1140, duration: 0.22, ease: "power2.inOut", immediateRender: false }}, Math.max(0, tc - 0.11));
    }}
    tl.to({{}}, {{
      duration: {total_dur:.3f},
      onUpdate: function () {{
        const t = tl.time();
        const cue = cues.find(c => t >= c.t0 && t < c.t1) || cues[cues.length - 1];
        if (counterEl.textContent !== cue.lbl) {{
          counterEl.textContent = cue.lbl;
          counterEl.style.background = cue.col;
          counterEl.style.borderColor = cue.col;
          counterEl.style.color = (cue.col === "#EF4444" || cue.col === "#6366F1") ? "#ffffff" : "#070b14";
        }}
        if (capEl.innerHTML !== cue.cap) capEl.innerHTML = cue.cap;

        const avActive = (t < S0_END) || (t >= S3_START);
        capWrap.style.top = avActive ? "1188px" : "1512px";
        avDiv.style.opacity = avActive ? "1" : "0";

        for (let i = 0; i < 4; i++) {{
          const [b0, b1, bCol] = segBounds[i];
          let p = 0;
          if (t >= b1) p = 1;
          else if (t > b0) p = (t - b0) / (b1 - b0);
          fills[i].style.transform = "scaleX(" + p.toFixed(4) + ")";
          fills[i].style.background = p > 0 ? bCol : {json.dumps(acc1)};
        }}
        for (let k = 0; k < 5; k++) {{
          const amp = 0.25 + 0.72 * Math.abs(Math.sin(t * 11.5 + k * 1.35));
          vpBars[k].style.transform = "scaleY(" + amp.toFixed(3) + ")";
        }}
      }}
    }}, 0);
    window.__timelines = window.__timelines || {{}};
    window.__timelines["root"] = tl;
  </script>
</body>
</html>
"""


def build_short_project(spec: dict, do_render: bool) -> Path:
    slug = spec["slug"]
    sdir = OUT_ROOT / slug
    timings = json.loads((sdir / "audio" / "timings.json").read_text(encoding="utf-8"))
    segs = timings["segments"]
    total_dur = float(timings["total_duration"])

    hf_dir = sdir / "hyperframes"
    assets_dir = hf_dir / "assets"
    comp_dir = hf_dir / "compositions"
    assets_dir.mkdir(parents=True, exist_ok=True)
    comp_dir.mkdir(parents=True, exist_ok=True)

    # Link/copy all local media strictly inside hyperframes/assets/
    link_or_copy(sdir / "audio" / "final_mix.wav", assets_dir / "final_mix.wav")
    for clip in ("b3d_01_abertura.mp4", "b3d_02_bloco_a.mp4", "b3d_03_bloco_b.mp4", "b3d_04_fechamento.mp4"):
        link_or_copy(sdir / "blender_out" / clip, assets_dir / clip)
    for av in ("avatar_seg_01.mp4", "avatar_seg_02.mp4", "avatar_hold_bar.mp4"):
        link_or_copy(sdir / "avatar_out" / av, assets_dir / av)

    durs = [
        round(float(segs[1]["start"]), 3),
        round(float(segs[2]["start"]) - float(segs[1]["start"]), 3),
        round(float(segs[3]["start"]) - float(segs[2]["start"]), 3),
        round(total_dur - float(segs[3]["start"]), 3),
    ]
    for i, dur in enumerate(durs):
        (comp_dir / f"ov_{i + 1:02d}.html").write_text(
            build_subcomposition_html(spec, i, dur),
            encoding="utf-8",
        )

    (hf_dir / "index.html").write_text(build_root_index_html(spec, timings), encoding="utf-8")

    out_mp4 = sdir / f"final_{slug}.mp4"
    if do_render:
        print(f"[{slug}] HyperFrames lint + validate + render --strict...", flush=True)
        for gate in (
            [NPX_EXE, "-y", "hyperframes", "lint", "--json"],
            [NPX_EXE, "-y", "hyperframes", "validate", "--json"],
            [NPX_EXE, "-y", "hyperframes", "render", "--strict", "--output", str(out_mp4)],
        ):
            subprocess.run(gate, cwd=str(hf_dir), check=True)
        print(f"[{slug}] RENDERED -> {out_mp4}", flush=True)
    return out_mp4


def main() -> int:
    do_render = "--render" in sys.argv
    only = {a.strip() for a in sys.argv[1:] if a.strip() and not a.startswith("--")}
    for spec in SHORTS_6DAYS:
        if only and spec["slug"] not in only and spec["day_key"] not in only:
            continue
        build_short_project(spec, do_render=do_render)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
