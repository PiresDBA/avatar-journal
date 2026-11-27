"""7-field visual creative brief & Parte 11 editorial analysis aligned with local style catalogs."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .memory_store import EditorialMemoryStore
from .programs import get_program

ROOT_DIR = Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT_DIR / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from editorial_memory import suggest_styles  # type: ignore  # noqa: E402

OPUS5_VIDEOS_JSON = Path(r"D:\Utilitarios\opus5-reference\videos.json")


def _query_opus5_references(keywords: list[str], top_k: int = 3) -> list[dict[str, str]]:
    if not OPUS5_VIDEOS_JSON.exists():
        return []
    try:
        videos = json.loads(OPUS5_VIDEOS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return []

    scored: list[tuple[int, dict[str, Any]]] = []
    kw_lower = [k.lower() for k in keywords if len(k) >= 3]
    for v in videos:
        blob = " ".join([
            str(v.get("slug", "")),
            str(v.get("title", "")),
            str(v.get("description", "")),
            " ".join(v.get("tech_tags") or []),
            str(v.get("category", "")),
        ]).lower()
        score = sum(2 for k in kw_lower if k in blob)
        if v.get("category") in {"3d", "explainer", "motion"}:
            score += 1
        if score > 1:
            scored.append((score, v))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "slug": str(v.get("slug", "")),
            "title": str(v.get("title", ""))[:80],
            "category": str(v.get("category", "")),
            "tech_tags": ", ".join((v.get("tech_tags") or [])[:4]),
        }
        for _, v in scored[:top_k]
    ]


def build_creative_brief(
    *,
    program_key: str | None = None,
    item_ids: list[int] | None = None,
    store: EditorialMemoryStore | None = None,
) -> dict[str, Any]:
    """Generate a structured Parte 11 (A-F) proposal + 7-field visual brief without repeating styles."""
    db = store or EditorialMemoryStore()
    program = get_program(program_key)

    if item_ids:
        selected = [db.get_item(i) for i in item_ids]
        candidates = [x for x in selected if x is not None]
    else:
        candidates = db.list_items(
            states=("aprovado", "selecionado", "apresentado", "pesquisado"),
            program=program.key,
            limit=5,
        )
        if not candidates:
            candidates = db.list_items(
                states=("aprovado", "selecionado", "apresentado", "pesquisado"),
                limit=5,
            )

    style_recs = suggest_styles()
    recent_styles = style_recs.get("recent_styles_to_avoid", [])
    fresh_candidates = style_recs.get("recommended_fresh_candidates", [])
    chosen_style = fresh_candidates[0] if fresh_candidates else {
        "style_id": "tactile-brushed-titanium",
        "family": "precision-editorial-3d",
        "lemo_count": 100,
    }

    search_terms = list(program.visual_affinity)
    for c in candidates[:3]:
        search_terms.extend(c.get("keywords", [])[:3])
    opus_refs = _query_opus5_references(search_terms, top_k=4)

    visual_brief = {
        "1_metafora_visual": (
            f"Palco editorial {program.name} em '{chosen_style.get('family', 'kinetic-3d')}': "
            "dispositivo fisico de precisao mostrando fluxo real de dados e metricas verificadas."
        ),
        "2_conceito_3d": (
            "Blender 5.3 EEVEE 1080x1344 com subdivisao >= 64, Shade Smooth obrigatorio, "
            "iluminacao 3 pontos (key quente + rim ciano/ambar + fill suave) e World HDRI procedural — zero emissao chapada."
        ),
        "3_paleta_cor_material": (
            f"Estilo '{chosen_style.get('style_id', 'curated-fresh')}' "
            f"(evitando estilos recentes: {', '.join(recent_styles) or 'nenhum'}): "
            "base grafite fosco (#0B0E14), acentos bronze/ambar ou ciano cirurgico com contraste WCAG AAA (>= 7:1)."
        ),
        "4_composicao_quadro": (
            "Padrao short_github_10_v2 (70/30 + Full-Stage Flex 1080x1920): avatar V17C nativo 1080x576 "
            "(top:1344px, z-index:27) APENAS na abertura (0-3s) e fechamento (ultimos 4-5s), com #av-divider em 1341px "
            "(opacity:1 so com avActive), #captions dinamico (1188px com avatar / 1512px tela cheia) e >=80-85% em tela cheia."
        ),
        "5_dinamica_movimento": (
            "Curva GSAP expo.out / back.out(1.2) sincronizada com pauta e Canvas/Three.js deterministico "
            "(zero requestAnimationFrame solto; data-media-start='2.0' em cortes subsequentes do Blender)."
        ),
        "6_ritmo_edicao": (
            "Abertura avatar 0-3s + overlap av-hold-01 (-0.08s, z-index 28/27) -> blocos tela cheia 1080x1920 a cada 3-6s "
            "(full_graphics/broll >=80%) -> fechamento split ultimos 4-5s com av-hold (-0.08s) sem blink preto."
        ),
        "7_elementos_visuais_especificos": {
            "opus5_refs": opus_refs,
            "lemo_opuscar_styles": "C:\\Users\\Pires\\lemo-opuscar\\styles\\",
            "openmontage": "D:\\Utilitarios\\OpenMontage\\PROMPT_GALLERY.md",
            "blender_audit_cmd": "blender -b ... --still-only -> read_file QA antes da renderizacao animada",
        },
    }

    if candidates:
        db.save_visual_brief(candidates[0]["id"], visual_brief)

    insights = db.list_insights(limit=5)
    primary = candidates[0] if candidates else None
    backups = candidates[1:4]

    parte_11_brief = {
        "A_diagnostico_intencao": (
            f"Programa {program.day_pt} — {program.name} ({program.category_label}): "
            f"{program.mission}"
        ),
        "B_descoberta_investigacao": [
            {
                "id": c["id"],
                "title": c["title"],
                "source": c["primary_source"],
                "url": c["source_url"],
                "state": c["state"],
                "maturity": c["maturity"],
                "novelty_score": c["novelty_score"],
            }
            for c in candidates
        ],
        "C_analise_critica": (
            "Priorizar itens com URL primaria alcancavel e metricas quantitativas verificadas. "
            "Sinalizar riscos de fonte unica ou falta de licenca antes da aprovacao."
            if candidates
            else "Nenhum candidato salvo ainda para este programa. Rode `editorial_chief.py discover --save`."
        ),
        "D_recomendacao_editorial": {
            "principal_sugerido": primary["title"] if primary else None,
            "reservas": [b["title"] for b in backups],
            "licoes_aplicadas": [i["summary"] for i in insights],
        },
        "E_direcao_criativa_visual": visual_brief,
        "F_pergunta_para_decisao": (
            f"Para '{program.name}', recomendo '{primary['title']}' com o estilo visual '{chosen_style.get('style_id')}'. "
            "Voce aprova essa escolha ou prefere trocar o assunto/estilo antes de exportar a pauta?"
            if primary
            else f"Deseja que eu rode `discover --program {program.key} --save` para buscar candidatos reais agora?"
        ),
    }

    return {
        "program": program.to_dict(),
        "style_rotation": style_recs,
        "visual_brief_7_campos": visual_brief,
        "parte_11": parte_11_brief,
    }
