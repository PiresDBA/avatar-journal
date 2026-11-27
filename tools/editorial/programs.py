"""Weekly editorial program definitions (Parte 4 — 7 Editorial Identities)."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class EditorialProgram:
    """Identity and discovery profile for one day of the week."""

    key: str
    weekday_index: int
    day_pt: str
    name: str
    category_label: str
    mission: str
    focus_signals: tuple[str, ...]
    preferred_sources: tuple[str, ...]
    github_queries: tuple[str, ...]
    arxiv_queries: tuple[str, ...]
    hn_queries: tuple[str, ...]
    hf_include_papers: bool
    hf_include_models: bool
    visual_affinity: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PROGRAMS: dict[str, EditorialProgram] = {
    "segunda": EditorialProgram(
        key="segunda",
        weekday_index=0,
        day_pt="Segunda-feira",
        name="Radar Open Source",
        category_label="Open Source & Labs",
        mission=(
            "Investigar o ecossistema aberto de IA: repositorios emergentes, "
            "novas capacidades locais, agentes, arquiteturas e ferramentas pouco conhecidas."
        ),
        focus_signals=(
            "crescimento organico acelerado",
            "ferramentas locais / privacidade / custo zero",
            "arquiteturas ou benchmarks reproduziveis",
        ),
        preferred_sources=("github", "huggingface_models", "hackernews"),
        github_queries=(
            "topic:ai-agent stars:>120 pushed:>=2026-10-01",
            "mcp server local llm agentic workflow stars:>80 pushed:>=2026-10-01",
        ),
        arxiv_queries=("cat:cs.AI OR cat:cs.SE open source agent",),
        hn_queries=("Show HN AI open source", "open source local LLM agent"),
        hf_include_papers=False,
        hf_include_models=True,
        visual_affinity=("holographic wireframe", "editorial blueprint", "circuit neon"),
    ),
    "terca": EditorialProgram(
        key="terca",
        weekday_index=1,
        day_pt="Terça-feira",
        name="Radar de Pesquisa e Futuro",
        category_label="Pesquisa & Ciência",
        mission=(
            "Descobertas cientificas, papers disruptivos, arquiteturas que superam escala bruta, "
            "robotica, raciocinio, eficiencia energetica e fronteiras de hardware."
        ),
        focus_signals=(
            "evidencia empirica / ablations",
            "reducao de custo computacional ou memoria",
            "ruptura de paradigma alem de escalar parametros",
        ),
        preferred_sources=("arxiv", "huggingface_papers", "hackernews"),
        github_queries=("transformer alternative OR world model OR inference speedup stars:>80 pushed:>=2026-10-01",),
        arxiv_queries=(
            "cat:cs.AI OR cat:cs.LG reasoning efficiency",
            "cat:cs.RO OR cat:cs.CV world model OR foundation model",
        ),
        hn_queries=("arXiv AI paper breakthrough", "reasoning LLM architecture efficiency"),
        hf_include_papers=True,
        hf_include_models=False,
        visual_affinity=("optical glass refraction", "scientific monolith 3D", "photonic lattice"),
    ),
    "quarta": EditorialProgram(
        key="quarta",
        weekday_index=2,
        day_pt="Quarta-feira",
        name="Batalha de IAs",
        category_label="Comparativos & Benchmarks",
        mission=(
            "Comparacoes reais entre modelos, ferramentas, stacks e abordagens: "
            "custo, latencia, VRAM, qualidade real em producao e casos onde a opcao menor vence."
        ),
        focus_signals=(
            "criterios verificaveis (latencia, tokens/s, VRAM, custo)",
            "cenarios onde ferramentas menos conhecidas superam gigantes",
            "trade-offs honestos sem hype de leaderboard sintetico",
        ),
        preferred_sources=("huggingface_models", "github", "hackernews", "arxiv"),
        github_queries=("llm benchmark OR eval OR inference engine vllm llamacpp stars:>100 pushed:>=2026-10-01",),
        arxiv_queries=("cat:cs.CL OR cat:cs.LG benchmark evaluation quantization",),
        hn_queries=("LLM benchmark comparison latency cost", "local model vs frontier benchmark"),
        hf_include_papers=True,
        hf_include_models=True,
        visual_affinity=("kinetic split prism", "chrome versus balance", "comparative telemetry 3D"),
    ),
    "quinta": EditorialProgram(
        key="quinta",
        weekday_index=3,
        day_pt="Quinta-feira",
        name="IA Que Faz",
        category_label="IA Que Faz",
        mission=(
            "Aplicacoes praticas que economizam tempo, reduzem custo ou criam fluxos reais "
            "de automacao, engenharia, video, codigo e operacoes no dia a dia."
        ),
        focus_signals=(
            "execucao comprovada ponta a ponta",
            "ganho concreto de tempo, custo ou autonomia",
            "fluxo reproduzivel em maquina real",
        ),
        preferred_sources=("github", "hackernews", "huggingface_models"),
        github_queries=(
            "automation agent OR browser-use OR document-parsing OR cli-tool llm stars:>120 pushed:>=2026-10-01",
            "workflow automation ai-agents mcp python stars:>90 pushed:>=2026-10-01",
        ),
        arxiv_queries=("cat:cs.AI autonomous workflow tool use",),
        hn_queries=("Show HN AI tool workflow automation", "Show HN agent CLI"),
        hf_include_papers=False,
        hf_include_models=True,
        visual_affinity=("tactile brushed titanium", "mechanical pipeline 3D", "architectural diorama"),
    ),
    "sexta": EditorialProgram(
        key="sexta",
        weekday_index=4,
        day_pt="Sexta-feira",
        name="Histórias e Mentes da IA",
        category_label="Histórias & Mentes",
        mission=(
            "Bastidores humanos e historicos: pesquisadores, criadores independentes, "
            "erros que mudaram rumos e decisoes tecnicas contra o consenso."
        ),
        focus_signals=(
            "decisao contraintuitiva documentada",
            "impacto duradouro ou virada inesperada",
            "fontes primarias ou retrospectivas verificaveis",
        ),
        preferred_sources=("hackernews", "arxiv", "github"),
        github_queries=("karpathy OR minimalist llm OR from-scratch transformer stars:>300 pushed:>=2026-09-01",),
        arxiv_queries=("cat:cs.CY OR cat:cs.AI history OR retrospective OR postmortem",),
        hn_queries=("AI researcher retrospective story lessons", "open source AI creator story"),
        hf_include_papers=True,
        hf_include_models=False,
        visual_affinity=("warm tungsten studio", "kinetic archival glass", "monolithic portrait frame"),
    ),
    "sabado": EditorialProgram(
        key="sabado",
        weekday_index=5,
        day_pt="Sábado",
        name="O Lado B da IA",
        category_label="Riscos, Falhas & Paradoxos",
        mission=(
            "Riscos reais, falhas de alinhamento ou seguranca, vieses estruturais, "
            "custo ambiental/energetico e vulnerabilidades de agentes em producao."
        ),
        focus_signals=(
            "incidente ou vulnerabilidade reproduzida",
            "implicacao pratica para quem usa agentes",
            "equilibrio tecnico sem alarmismo vazio",
        ),
        preferred_sources=("hackernews", "arxiv", "github"),
        github_queries=("prompt-injection OR ai-security OR red-teaming llm stars:>80 pushed:>=2026-09-01",),
        arxiv_queries=("cat:cs.CR OR cat:cs.AI adversarial prompt injection safety",),
        hn_queries=("AI security vulnerability prompt injection incident", "AI energy cost privacy flaw"),
        hf_include_papers=True,
        hf_include_models=False,
        visual_affinity=("obsidian liquid chrome", "high-contrast warning prism", "dark glass refraction"),
    ),
    "domingo": EditorialProgram(
        key="domingo",
        weekday_index=6,
        day_pt="Domingo",
        name="Visão do Futuro",
        category_label="Visão & Síntese",
        mission=(
            "Sinteses estrategicas conectando multiplos sinais da semana: para onde vao trabalho, "
            "computacao pessoal, agentes autonomos, soberania tecnologica e educacao."
        ),
        focus_signals=(
            "convergencia de pelo menos 2 frentes tecnologicas",
            "tese clara ancorada em evidencias reais",
            "visao acionavel para os proximos meses",
        ),
        preferred_sources=("huggingface_papers", "arxiv", "hackernews"),
        github_queries=("embodied ai OR world-model OR edge-ai stars:>120 pushed:>=2026-09-01",),
        arxiv_queries=("cat:cs.AI OR cat:cs.CY future compute agents edge",),
        hn_queries=("future of AI agents local computing", "AI hardware edge trend"),
        hf_include_papers=True,
        hf_include_models=True,
        visual_affinity=("iridescent orbital glass", "architectural skyline 3D", "volumetric amber horizon"),
    ),
}

VALID_PROGRAMS: tuple[str, ...] = tuple(PROGRAMS.keys())
_WEEKDAY_MAP = {p.weekday_index: p.key for p in PROGRAMS.values()}


def get_program(program_key: str | None = None) -> EditorialProgram:
    """Resolve a program key ('segunda'..'domingo' or 'auto' for current weekday)."""
    if not program_key or program_key.lower() in {"auto", "today", "hoje"}:
        key = _WEEKDAY_MAP[datetime.now().weekday()]
        return PROGRAMS[key]
    normalized = (
        program_key.strip()
        .lower()
        .replace("ç", "c")
        .replace("á", "a")
        .replace("-feira", "")
    )
    if normalized not in PROGRAMS:
        raise ValueError(
            f"Programa invalido '{program_key}'. Use um de: {', '.join(VALID_PROGRAMS)} (ou 'auto')."
        )
    return PROGRAMS[normalized]


def list_programs() -> list[dict[str, Any]]:
    """Return all 7 editorial programs ordered Monday -> Sunday."""
    return [PROGRAMS[k].to_dict() for k in VALID_PROGRAMS]
