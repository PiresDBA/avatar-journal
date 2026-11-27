"""Banco de memoria editorial anti-repeticao e consultor de estilos visuais do avatar-journal."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_HISTORY = ROOT_DIR / "data" / "published_history.json"
OPUS_VIDEOS_JSON = Path(r"D:\Utilitarios\opus5-reference\videos.json")
LEMO_STYLES_DIR = Path(r"C:\Users\Pires\lemo-opuscar\styles")
OPENMONTAGE_GALLERY = Path(r"D:\Utilitarios\OpenMontage\PROMPT_GALLERY.md")

STOPWORDS = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do", "dos",
    "e", "em", "na", "nas", "no", "nos", "o", "os", "ou", "para", "pelo",
    "pela", "por", "que", "se", "sem", "seu", "sua", "um", "uma", "ia", "ai",
    "the", "and", "for", "with", "from", "into", "new", "novo", "nova",
    "github", "repo", "repos", "agentes", "agente", "agent", "agents",
    "modelo", "modelos", "code", "codigo", "sistema", "sistemas",
}


def _strip_accents(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def _norm_text(text: str) -> str:
    cleaned = _strip_accents(text).lower()
    cleaned = re.sub(r"https?://github\.com/", " ", cleaned)
    cleaned = re.sub(r"[^a-z0-9._/+%-]+", " ", cleaned)
    return " ".join(cleaned.split())


def _tokenize(text: str) -> set[str]:
    norm = _norm_text(text)
    raw = re.split(r"[\s/,_:()]+", norm)
    tokens: set[str] = set()
    for tok in raw:
        t = tok.strip(".-+")
        if len(t) >= 2 and t not in STOPWORDS:
            tokens.add(t)
    return tokens


def load_history(path: Path = DEFAULT_HISTORY) -> dict:
    """Carrega o JSON do historico editorial criando estrutura padrao se ausente."""
    if not path.exists():
        return {
            "version": 1,
            "channel": {"title": "AI Journal 4 ALL", "handle": "@ai-journal-4-all", "id": ""},
            "videos": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_history(data: dict, path: Path = DEFAULT_HISTORY) -> None:
    """Persiste o historico editorial formatado em UTF-8."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _extract_candidates_from_pauta(pauta_path: Path) -> list[str]:
    payload = json.loads(pauta_path.read_text(encoding="utf-8"))
    out: list[str] = []
    for item in payload.get("shorts", []):
        hl = str(item.get("headline") or "").strip()
        if hl:
            out.append(hl)
        for f in item.get("facts", []):
            claim = str(f.get("claim") or "").strip()
            if claim:
                out.append(claim)
                break
    return out


def _topic_identifiers(topic: dict) -> tuple[set[str], set[str], list[str]]:
    """Retorna (identificadores fortes de repo/slug/kw, tokens gerais, frases normalizadas)."""
    strong: set[str] = set()
    phrases: list[str] = []

    slug = _norm_text(str(topic.get("slug", "")))
    entity = _norm_text(str(topic.get("entity", "")))
    title = _norm_text(str(topic.get("title", "")))
    kws = [_norm_text(str(k)) for k in topic.get("keywords", []) if str(k).strip()]

    for phrase in (slug, entity, title, *kws):
        if phrase:
            phrases.append(phrase)

    # Parte apos "/" em repositorios owner/repo (ex: "graphify", "minimind", "t3code")
    for source in (entity, title):
        for match in re.findall(r"([a-z0-9_.-]+)/([a-z0-9_.-]+)", source):
            owner, repo = match
            if len(owner) >= 3:
                strong.add(owner)
            if len(repo) >= 3:
                strong.add(repo)
                strong.add(f"{owner}/{repo}")

    if kws:
        # Primeiro keyword de cada item normalmente e o identificador unico do assunto
        first_kw = kws[0]
        if len(first_kw) >= 4:
            strong.add(first_kw)

    all_tokens = _tokenize(" ".join(phrases))
    return strong, all_tokens, phrases


def check_candidate(candidate: str, videos: list[dict]) -> dict | None:
    """Retorna o registro conflitante se o candidato repetir um assunto ja publicado."""
    cand_norm = _norm_text(candidate)
    cand_tokens = _tokenize(candidate)
    if not cand_norm:
        return None

    for vid in videos:
        for topic in vid.get("topics", []):
            strong, past_tokens, phrases = _topic_identifiers(topic)

            # 1) Match direto por identificador forte (ex: repo slug, nome exato do produto)
            for ident in strong:
                if ident in cand_tokens or (len(ident) >= 6 and ident in cand_norm):
                    return {
                        "video_id": vid.get("video_id", ""),
                        "published_at": vid.get("published_at", ""),
                        "url": vid.get("url", ""),
                        "past_title": topic.get("title", ""),
                        "reason": f"identificador '{ident}'",
                    }

            # 2) Sobreposicao de tokens significativos ou similaridade textual alta
            shared = cand_tokens & past_tokens
            union = cand_tokens | past_tokens
            jaccard = len(shared) / len(union) if union else 0.0
            if len(shared) >= 2 and jaccard >= 0.25:
                return {
                    "video_id": vid.get("video_id", ""),
                    "published_at": vid.get("published_at", ""),
                    "url": vid.get("url", ""),
                    "past_title": topic.get("title", ""),
                    "reason": f"tokens compartilhados {sorted(shared)}",
                }

            for phr in phrases:
                if len(phr) >= 8 and SequenceMatcher(None, cand_norm, phr).ratio() >= 0.72:
                    return {
                        "video_id": vid.get("video_id", ""),
                        "published_at": vid.get("published_at", ""),
                        "url": vid.get("url", ""),
                        "past_title": topic.get("title", ""),
                        "reason": "alta similaridade textual",
                    }
    return None


def record_published_video(
    video_id: str,
    title: str,
    url: str,
    topics: list[dict | str],
    file_path: str = "",
    published_at: str = "",
    style_name: str = "",
    style_family: str = "",
    engines: list[str] | None = None,
    materials: list[str] | None = None,
    opus5_refs: list[str] | None = None,
    lessons: str = "",
    history_path: Path = DEFAULT_HISTORY,
) -> dict:
    """Insere ou atualiza um video publicado no banco editorial anti-repeticao."""
    data = load_history(history_path)
    norm_topics: list[dict] = []
    for idx, t in enumerate(topics, 1):
        if isinstance(t, dict):
            norm_topics.append({
                "slug": str(t.get("slug") or f"topic-{idx}"),
                "title": str(t.get("title") or ""),
                "entity": str(t.get("entity") or t.get("title") or ""),
                "keywords": list(t.get("keywords") or []),
            })
        else:
            txt = str(t).strip()
            if txt:
                slug = re.sub(r"[^a-z0-9]+", "-", _strip_accents(txt).lower()).strip("-")[:48]
                norm_topics.append({
                    "slug": slug or f"topic-{idx}",
                    "title": txt,
                    "entity": txt,
                    "keywords": sorted(_tokenize(txt))[:5],
                })

    entry = {
        "video_id": video_id,
        "published_at": published_at or date.today().isoformat(),
        "url": url,
        "title": title,
        "file": file_path,
        "visual_style": {
            "name": style_name,
            "family": style_family,
            "engines": engines or [],
            "materials": materials or [],
            "opus5_refs": opus5_refs or [],
        },
        "lessons_learned": lessons,
        "topics": norm_topics,
    }

    videos = [v for v in data.get("videos", []) if v.get("video_id") != video_id]
    videos.append(entry)
    data["videos"] = videos
    save_history(data, history_path)

    try:
        tools_dir = str(Path(__file__).resolve().parent)
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        from editorial.memory_store import EditorialMemoryStore, slugify as _db_slugify

        store = EditorialMemoryStore()
        store.record_publication(
            video_id=video_id,
            title=title,
            url=url,
            file_path=file_path,
            published_at=entry["published_at"],
            style_name=style_name,
            style_family=style_family,
            engines=engines or [],
            materials=materials or [],
            opus5_refs=opus5_refs or [],
            lessons=lessons,
        )
        for nt in norm_topics:
            item = store.upsert_item(
                slug=_db_slugify(nt.get("slug") or nt.get("title") or ""),
                title=nt.get("title") or nt.get("slug") or "",
                summary=f"Publicado em {video_id}: {nt.get('title') or ''}",
                primary_source="published_history",
                source_url=url,
                entities=[nt.get("entity")] if nt.get("entity") else [],
                keywords=nt.get("keywords") or [],
                maturity="verified_release",
                initial_state="publicado",
                video_id=video_id,
                actor="editorial_memory",
                reason=f"record_published_video({video_id})",
            )
            if item["state"] != "publicado":
                store.transition(
                    item["id"],
                    "publicado",
                    reason=f"Synced via record_published_video({video_id})",
                    actor="editorial_memory",
                    video_id=video_id,
                    force=True,
                )
    except Exception as exc:
        print(f"[WARN] Nao foi possivel sincronizar editorial_memory.db: {exc}", file=sys.stderr)

    return entry


def _load_opus_sample(techs: set[str], limit: int = 3) -> list[str]:
    if not OPUS_VIDEOS_JSON.exists():
        return []
    videos = json.loads(OPUS_VIDEOS_JSON.read_text(encoding="utf-8"))
    picked: list[str] = []
    for v in videos:
        vtags = {t.lower() for t in v.get("tech_tags", [])}
        if v.get("category") == "3d" and (vtags & techs):
            picked.append(f"{v['slug']} ({', '.join(v.get('tech_tags', []))})")
        if len(picked) >= limit:
            break
    if len(picked) < limit:
        for v in videos:
            vtags = {t.lower() for t in v.get("tech_tags", [])}
            if vtags & techs:
                s = f"{v['slug']} ({', '.join(v.get('tech_tags', []))})"
                if s not in picked:
                    picked.append(s)
            if len(picked) >= limit:
                break
    return picked


def _list_lemo_styles(candidates: list[str]) -> list[str]:
    if not LEMO_STYLES_DIR.exists():
        return []
    available = {p.name for p in LEMO_STYLES_DIR.iterdir() if p.is_dir()}
    return [c for c in candidates if c in available]


def cmd_list(args: argparse.Namespace) -> int:
    data = load_history(Path(args.history))
    ch = data.get("channel", {})
    videos = data.get("videos", [])
    total_topics = sum(len(v.get("topics", [])) for v in videos)
    print(f"Canal: {ch.get('title')} ({ch.get('handle')}) | Videos: {len(videos)} | Assuntos bloqueados: {total_topics}")
    print("-" * 78)
    for v in videos:
        vs = v.get("visual_style", {})
        print(f"[{v.get('published_at')}] {v.get('video_id')} | {v.get('url')}")
        print(f"  Titulo : {v.get('title')}")
        print(f"  Estilo : {vs.get('name')} (family={vs.get('family')})")
        if v.get("lessons_learned"):
            print(f"  Licoes : {v.get('lessons_learned')}")
        print(f"  Topicos ({len(v.get('topics', []))}):")
        for idx, t in enumerate(v.get("topics", []), 1):
            print(f"    {idx:02d}. {t.get('title')}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    data = load_history(Path(args.history))
    videos = data.get("videos", [])
    candidates: list[str] = []
    if args.topics:
        candidates.extend([t.strip() for t in args.topics.split(",") if t.strip()])
    if args.pauta:
        candidates.extend(_extract_candidates_from_pauta(Path(args.pauta)))

    if not candidates:
        print("[ERROR] Informe --topics ou --pauta para checar repeticao.", flush=True)
        return 1

    duplicates = 0
    for cand in candidates:
        hit = check_candidate(cand, videos)
        if hit:
            duplicates += 1
            print(
                f"[BLOQUEADO REPETIDO] '{cand}' -> ja publicado em {hit['published_at']} "
                f"({hit['video_id']}) como '{hit['past_title']}' [{hit['reason']}]"
            )
        else:
            print(f"[OK NOVO] '{cand}'")

    print("-" * 78)
    print(f"Resumo: {len(candidates) - duplicates}/{len(candidates)} ineditos | {duplicates} repetido(s)")
    return 2 if duplicates > 0 else 0


def cmd_record(args: argparse.Namespace) -> int:
    topics: list[dict | str] = []
    if args.topics_json:
        topics = json.loads(Path(args.topics_json).read_text(encoding="utf-8"))
    elif args.topics:
        topics = [t.strip() for t in args.topics.split(",") if t.strip()]

    entry = record_published_video(
        video_id=args.video_id,
        title=args.title,
        url=args.url,
        topics=topics,
        file_path=args.file,
        published_at=args.published_at,
        style_name=args.style_name,
        style_family=args.style_family,
        engines=[s.strip() for s in args.engines.split(",") if s.strip()],
        materials=[s.strip() for s in args.materials.split(",") if s.strip()],
        opus5_refs=[s.strip() for s in args.opus5_refs.split(",") if s.strip()],
        lessons=args.lessons,
        history_path=Path(args.history),
    )
    print(f"[OK] Video {entry['video_id']} gravado com {len(entry['topics'])} topico(s) em {args.history}")
    return 0


def suggest_styles(history_path: Path = DEFAULT_HISTORY) -> dict:
    """Retorna familias visuais recentes a evitar e candidatos ineditos de Lemo/Opus/Blender."""
    data = load_history(history_path)
    recent_families = [
        v.get("visual_style", {}).get("family", "")
        for v in data.get("videos", [])[-3:]
        if v.get("visual_style", {}).get("family")
    ]
    lemo_count = len([p for p in LEMO_STYLES_DIR.iterdir() if p.is_dir()]) if LEMO_STYLES_DIR.exists() else 0
    opus_count = len(json.loads(OPUS_VIDEOS_JSON.read_text(encoding="utf-8"))) if OPUS_VIDEOS_JSON.exists() else 0

    catalog = [
        {
            "family": "blender-mirror-chrome-hdri",
            "title": "1. Espelho & Cromo Liquido (Blender HDRI Reflexivo)",
            "desc": "Chao espelhado obsidian/prata, esferas cromadas subdivididas Shade Smooth, luz 3-pontos + rim colorido",
            "opus": _load_opus_sample({"threejs", "shader"}, 3),
            "lemo": _list_lemo_styles(["dark-keynote", "dark-documentary", "double-exposure", "art-deco"]),
        },
        {
            "family": "optical-glass-refraction-3d",
            "title": "2. Vidro Optico & Refracao Macro (Glassmorphism 3D Real)",
            "desc": "Blocos e lentes de vidro com transmissao/IOR, causticos sutis, placas glassmorficas iluminadas por rim light",
            "opus": _load_opus_sample({"threejs", "webgl"}, 3),
            "lemo": _list_lemo_styles(["hologram-hud", "archive-lighttable", "desktop-flythrough", "bauhaus-shapes"]),
        },
        {
            "family": "blender-architectural-diorama",
            "title": "3. Diorama Arquitetonico 3D Volumetrico (Blender Studio + DoF)",
            "desc": "Mini-maquetes 3D de data centers/chips/robos com iluminacao cinematica, DoF controlado e movimento de grua",
            "opus": _load_opus_sample({"threejs", "particles", "physics"}, 3),
            "lemo": _list_lemo_styles(["blueprint", "data-physical", "circuit-board", "city-symphony"]),
        },
        {
            "family": "glsl-shader-kinetic-3d-reel",
            "title": "4. Showreel GLSL & Tipografia Cinetica 3D (Three.js PMREM + Shaders)",
            "desc": "Shaders procedural raymarched/noise com reflexo PMREM em metais lisos (zero geometria facetada) + tipo 3D",
            "opus": _load_opus_sample({"shader", "canvas", "gsap"}, 3),
            "lemo": _list_lemo_styles(["dataviz", "ascii-crt", "countdown", "dark-keynote"]),
        },
        {
            "family": "curated-hybrid-mix",
            "title": "5. Mix Curado Personalizado (Mescla sob medida por bloco)",
            "desc": "Combina vidro optico + espelho metalico no Blender + shaders GLSL + telas documentais sem repetir o layout anterior",
            "opus": _load_opus_sample({"threejs", "shader", "physics"}, 3),
            "lemo": _list_lemo_styles(["news-package", "hologram-hud", "dark-documentary", "data-physical"]),
        },
    ]

    fresh_candidates = [
        {
            "style_id": (opt["lemo"][0] if opt["lemo"] else opt["family"]),
            "family": opt["family"],
            "title": opt["title"],
            "lemo_styles": opt["lemo"],
            "opus_refs": opt["opus"],
            "lemo_count": lemo_count,
        }
        for opt in catalog
        if opt["family"] not in recent_families
    ]
    return {
        "opus_count": opus_count,
        "lemo_count": lemo_count,
        "openmontage_ok": OPENMONTAGE_GALLERY.exists(),
        "recent_styles_to_avoid": recent_families,
        "recommended_fresh_candidates": fresh_candidates,
        "catalog": catalog,
    }


def cmd_suggest_styles(args: argparse.Namespace) -> int:
    info = suggest_styles(Path(args.history))
    recent_families = info["recent_styles_to_avoid"]

    print(
        f"Biblioteca ativa: Opus 5.5={info['opus_count']} prompts | Lemo-Opuscar={info['lemo_count']} estilos | "
        f"OpenMontage={'OK' if info['openmontage_ok'] else 'N/A'}"
    )
    print(f"Familias usadas recentemente (evitar repetir identica): {recent_families}")
    print("-" * 78)

    for opt in info["catalog"]:
        used_tag = " [USADO RECENTEMENTE]" if opt["family"] in recent_families else " [INEDITO]"
        print(f"{opt['title']}{used_tag}")
        print(f"  Visual     : {opt['desc']}")
        if opt["opus"]:
            print(f"  Opus 5.5   : {', '.join(opt['opus'])}")
        if opt["lemo"]:
            print(f"  Lemo-Opus  : {', '.join(opt['lemo'])}")
    return 0


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Memoria editorial anti-repeticao e consultor visual do avatar-journal")
    ap.add_argument("--history", default=str(DEFAULT_HISTORY), help="Caminho para published_history.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="Lista videos publicados, estilos, licoes e todos os topicos bloqueados")

    p_check = sub.add_parser("check", help="Valida se temas candidatos repetem videos anteriores")
    p_check.add_argument("--topics", default="", help="Lista de temas separados por virgula")
    p_check.add_argument("--pauta", default="", help="Caminho opcional para pauta.json")

    p_rec = sub.add_parser("record", help="Registra ou atualiza uma publicacao no banco editorial")
    p_rec.add_argument("--video-id", required=True)
    p_rec.add_argument("--title", required=True)
    p_rec.add_argument("--url", required=True)
    p_rec.add_argument("--file", default="")
    p_rec.add_argument("--published-at", default="")
    p_rec.add_argument("--style-name", default="")
    p_rec.add_argument("--style-family", default="")
    p_rec.add_argument("--engines", default="")
    p_rec.add_argument("--materials", default="")
    p_rec.add_argument("--opus5-refs", default="")
    p_rec.add_argument("--topics-json", default="")
    p_rec.add_argument("--topics", default="")
    p_rec.add_argument("--lessons", default="")

    sub.add_parser("suggest-styles", help="Sugere opcoes visuais ineditas combinando Opus 5.5, Lemo-Opuscar e Blender")
    return ap.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    handlers = {
        "list": cmd_list,
        "check": cmd_check,
        "record": cmd_record,
        "suggest-styles": cmd_suggest_styles,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
