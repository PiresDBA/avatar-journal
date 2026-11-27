# Graph Report - avatar-journal  (2026-11-26)

## Corpus Check
- 38 files · ~52,415 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: (none) 2, .db 1)

## Summary
- 532 nodes · 1220 edges · 24 communities (20 shown, 4 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 28 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b25767b2`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- voice_craft_tts.py
- calibrate_lipsync.py
- BaseTool
- avatar_lipsync.py
- Auditoria de sincronia e nitidez
- avatar_slot.py
- discover.py
- pauta_to_plan.py
- HOWTO — operar e diagnosticar
- jornalismo-ia-shorts-pro (Unificada ao `avatar-journal`)
- Arquitetura e decisões
- json
- Guardrails de Produção — `avatar-journal` (Windows · GTX 1060 6 GB)
- DESIGN.md — Boletim IA Dev (Protótipo 18s · 9:16)
- Contrato Obrigatório de Animação, Design e Recursos Locais (`avatar-journal`)
- EditorialMemoryStore
- youtube_publish.py
- avatar-journal
- Catálogo de erros e o que fazer
- Manual — boletim com avatar falante (PT-BR)

## God Nodes (most connected - your core abstractions)
1. `EditorialMemoryStore` - 37 edges
2. `main()` - 21 edges
3. `BaseTool` - 16 edges
4. `record_published_video()` - 16 edges
5. `lip_sync_project()` - 15 edges
6. `discover_candidates()` - 15 edges
7. `configure_avatar_dir()` - 14 edges
8. `slugify()` - 14 edges
9. `build_plan_from_pauta()` - 13 edges
10. `calibrate()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `Calibração obrigatória (o que a auditoria mostrou)` --references--> `composite_mouth()`  [INFERRED]
  docs/ARCHITECTURE.md → tools/avatar_liveportrait.py
- `SemanticDeduplicator` --uses--> `EditorialMemoryStore`  [INFERRED]
  tools/editorial/semantic_dedup.py → tools/editorial/memory_store.py
- `build_plan_from_pauta()` --calls--> `analyze_expression()`  [EXTRACTED]
  tools/pauta_to_plan.py → tools/voicestudio_tts.py
- `VoiceStudioTTS` --inherits--> `BaseTool`  [EXTRACTED]
  tools/voicestudio_tts.py → tools/base_tool.py
- `build_creative_brief()` --calls--> `EditorialMemoryStore`  [EXTRACTED]
  tools/editorial/creative_brief.py → tools/editorial/memory_store.py

## Import Cycles
- None detected.

## Communities (24 total, 4 thin omitted)

### Community 0 - "voice_craft_tts.py"
Cohesion: 0.07
Nodes (27): Determinism, ExecutionMode, _hash_file(), _load_dotenv(), ResourceProfile, ResumeSupport, RetryPolicy, ToolResult (+19 more)

### Community 1 - "calibrate_lipsync.py"
Cohesion: 0.09
Nodes (23): check_video(), main(), _audio_envelope(), audit(), _FaceDetector, _lag(), _landmark_session(), _landmarks() (+15 more)

### Community 2 - "BaseTool"
Cohesion: 0.06
Nodes (10): BaseTool, _cache_execute(), wrapper(), DependencyError, _fingerprint_value(), _instrument_execute(), wrapper(), _is_cacheable() (+2 more)

### Community 3 - "avatar_lipsync.py"
Cohesion: 0.11
Nodes (24): build_parser(), conform_clip(), _find_ffmpeg(), _find_python(), lip_sync_project(), main(), _overlaps(), prepare_block() (+16 more)

### Community 4 - "Auditoria de sincronia e nitidez"
Cohesion: 0.20
Nodes (9): Auditoria de sincronia e nitidez, Cinco regras de aceitação, Método, O que ainda pode ser melhorado, O que continua fora de alcance, O que substitui, Por que o shift por quadros é o elo fraco, Protocolo de sincronia (o orçamento de erro) (+1 more)

### Community 5 - "avatar_slot.py"
Cohesion: 0.18
Nodes (10): _clear_single_slot_assets(), configure_avatar_dir(), configure_avatar_slot(), _encode_clip_variant(), _find_ffmpeg(), _format_num(), main(), _replace_media_slot() (+2 more)

### Community 6 - "discover.py"
Cohesion: 0.06
Nodes (25): build_creative_brief(), _query_opus5_references(), discover_candidates(), _fetch_arxiv(), _fetch_github(), _fetch_hackernews(), _fetch_huggingface(), _github_headers() (+17 more)

### Community 7 - "pauta_to_plan.py"
Cohesion: 0.17
Nodes (11): _audit_facts(), build_parser(), build_plan_from_pauta(), _expand_dynamic_block(), _infer_block_mode(), main(), _merge_intervals(), parse_time_range() (+3 more)

### Community 8 - "HOWTO — operar e diagnosticar"
Cohesion: 0.20
Nodes (10): Calibração (diagnóstico, não auto-tuner), Checklist antes de publicar, Como comparar motores (A/B), Custos e tempo (GTX 1060), Expressividade da voz (tags), HOWTO — operar e diagnosticar, Modo rápido a partir do `pauta.json` (skill `jornalismo-ia-shorts-pro`), Ordem de execução (+2 more)

### Community 9 - "jornalismo-ia-shorts-pro (Unificada ao `avatar-journal`)"
Cohesion: 0.17
Nodes (11): Camada de produção local (`avatar-journal` — fora do Git), Camada editorial (saída da Fase 1 — fora do Git), Caminho A — Padrão Local (`avatar-journal`, US$ 0,00, GTX 1060), Caminho B — Híbrido (Blender 4.x no topo + `avatar-journal` embaixo), Caminho C — Alternativos (Reallusion iClone/AccuLips e Remotion/OpenMontage), Checklist Final Antes de Publicar, Estrutura de Pastas Determinística, Fase 1: Pesquisa, Tabela Mestra e Contrato `pauta.json` (+3 more)

### Community 10 - "Arquitetura e decisões"
Cohesion: 0.17
Nodes (12): 1. Objetivo, 2. Cadeia de execução, 3. Por que dois estágios, 4. Encerramento, 5. Orçamento de VRAM (GTX 1060, 6144 MB), 6. Gates de qualidade (não-regressão), 7. Decisões registradas, 8. Estrutura dos artefatos (+4 more)

### Community 11 - "json"
Cohesion: 0.10
Nodes (25): 1. Principio Fundamental: Pensar Antes de Executar (Partes 1 e 2), 2. Programacao Editorial Semanal (Parte 4), 3. Fluxo CLI Deterministico (`C:\Docling\venv\Scripts\python.exe`), 4. Regras de Integridade Editorial (Partes 5, 6, 8, 9 e 11), AI Editorial Chief (`Editor-Chefe`) — Protocolo Cognitivo e Operacional, check_candidate(), cmd_check(), cmd_list() (+17 more)

### Community 12 - "Guardrails de Produção — `avatar-journal` (Windows · GTX 1060 6 GB)"
Cohesion: 0.29
Nodes (6): 1. Ambiente GPU & Segurança de Processos, 2. Contrato Obrigatório de Animação e Design (`docs/ANIMATION_CONTRACT.md`), 3. Higiene do HyperFrames (`--strict`), 4. Direção de Avatar V17C ("Notícia Protagonista — Padrão `short_github_10_v2`") & Áudio PT-BR, 5. Inteligência Editorial (`Editor-Chefe`), Memória Anti-Repetição, Briefing Visual & Acabamento 3D Fino, Guardrails de Produção — `avatar-journal` (Windows · GTX 1060 6 GB)

### Community 13 - "DESIGN.md — Boletim IA Dev (Protótipo 18s · 9:16)"
Cohesion: 0.33
Nodes (5): DESIGN.md — Boletim IA Dev (Protótipo 18s · 9:16), Direção de Arte (Atelier), Mapeamento das Cenas e Receitas Opus 5.5, Tipografia (Compatível com Compilador Determinístico HyperFrames), Zonas Seguras 9:16 — Diretor de Layout Dinâmico (1080x1920)

### Community 14 - "Contrato Obrigatório de Animação, Design e Recursos Locais (`avatar-journal`)"
Cohesion: 0.29
Nodes (7): 0. Gate Editorial Anti-Repetição & Inteligência Editorial (`Editor-Chefe`), 1. Passo 0 Obrigatório — Consultar o Tesouro Local Antes de Criar, 2. Matriz de Escolha do Motor de Animação, 3. Regras Invioláveis de Tipografia, Cor e Contraste (Design System), 4. Integração no Fluxo do `avatar-journal` & Graphify, Contrato Obrigatório de Animação, Design e Recursos Locais (`avatar-journal`), Inventário Oficial de Recursos Locais (100% no disco, US\$ 0,00)

### Community 15 - "EditorialMemoryStore"
Cohesion: 0.19
Nodes (5): main(), _print(), EditorialMemoryStore, _json_loads(), _utc_now()

### Community 16 - "youtube_publish.py"
Cohesion: 0.13
Nodes (7): authenticate(), main(), _norm_handle(), _norm_title(), parse_args(), upload_video(), verify_channel()

### Community 18 - "avatar-journal"
Cohesion: 0.20
Nodes (10): Auditar (sincronia + nitidez, com números), avatar-journal, Como funciona (7 etapas), Estrutura, Licença, Limites conhecidos, O problema que este repositório resolve, O que **não** é versionado (e por quê) (+2 more)

### Community 19 - "Catálogo de erros e o que fazer"
Cohesion: 0.25
Nodes (8): “A boca abre demais / caretas”, “A boca continua mexendo depois que ele para de falar”, Catálogo de erros e o que fazer, “LivePortrait falhou com UnicodeEncodeError / charmap”, “Not enough free VRAM”, “O rosto fica liso/plástico quando fala e nítido quando cala”, “O vídeo ficou com ghost / rosto duplicado”, “Wav2Lip falhou com FileNotFoundError (WinError 2)”

### Community 20 - "Manual — boletim com avatar falante (PT-BR)"
Cohesion: 0.25
Nodes (8): 1. O que é, 2. Por que a primeira versão ficou ruim (e o que mudou), 3. Como o vídeo é montado, passo a passo, 4.1 Deixar a fala mais natural (pausas, risada, suspiro), 4. O que você pode ajustar, 5. Problemas comuns, 6. Números da entrega, Manual — boletim com avatar falante (PT-BR)

## Knowledge Gaps
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `composite_mouth()` connect `avatar_lipsync.py` to `Arquitetura e decisões`?**
  _High betweenness centrality (0.233) - this node is a cross-community bridge._
- **Should `voice_craft_tts.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06586538461538462 - nodes in this community are weakly interconnected._
- **Why does `Calibração obrigatória (o que a auditoria mostrou)` connect `Arquitetura e decisões` to `avatar_lipsync.py`?**
  _High betweenness centrality (0.229) - this node is a cross-community bridge._
- **Should `calibrate_lipsync.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08665269042627533 - nodes in this community are weakly interconnected._
- **Should `BaseTool` be split into smaller, more focused modules?**
  _Cohesion score 0.057624113475177305 - nodes in this community are weakly interconnected._
- **Should `avatar_lipsync.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10549645390070922 - nodes in this community are weakly interconnected._
- **Should `discover.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05660945498343872 - nodes in this community are weakly interconnected._