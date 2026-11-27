# Contrato Obrigatório de Animação, Design e Recursos Locais (`avatar-journal`)

> **REGRA INVIOLÁVEL:** Antes de criar, propor ou renderizar **qualquer animação, gráfico, cena 3D, diagrama ou ilustração** no `avatar-journal`, o agente/produtor **DEVE** consultar este contrato, verificar o histórico editorial anti-repetição e alinhar o estilo visual com o usuário.

---

## 0. Gate Editorial Anti-Repetição & Inteligência Editorial (`Editor-Chefe`)

1. **Orquestração obrigatória (`tools/editorial_chief.py` + `data/editorial_memory.db`):**
   - Execute todo o ciclo cognitivo da skill [`.agents/skills/ai-editorial-chief/SKILL.md`](../.agents/skills/ai-editorial-chief/SKILL.md) usando `C:\Docling\venv\Scripts\python.exe tools\editorial_chief.py` (`init`, `discover`, `check-dup`, `verify`, `brief`, `transition`, `export-pauta`, `insight`), mantendo sincronização bidirecional com [`tools/editorial_memory.py`](../tools/editorial_memory.py) e `data/published_history.json`.
   - **8 estados oficiais do ciclo editorial:** `pesquisado`, `selecionado`, `apresentado`, `aprovado`, `roteirizado`, `produzido`, `publicado` e `descartado`, com auditoria imutável em `state_transitions`. Nunca confunda assunto pesquisado com pauta aprovada ou vídeo publicado.
2. **Descoberta ao vivo em 4 fontes & 7 programas semanais (funciona sem `.env`):**
   - Coleta real em **GitHub Search**, **arXiv Atom XML**, **Hugging Face (Daily Papers + Trending Models)** e **Hacker News Algolia** conforme os 7 perfis semanais (`segunda` a `domingo` + `auto`).
   - Opera normalmente sem arquivo `.env` (`.env` com `GITHUB_TOKEN` é opcional apenas para ampliar o rate limit do GitHub de 60 para 5.000 req/h).
3. **Gate anti-repetição semântica em 3 camadas (`device="cpu"`, 0 VRAM):**
   - **Camada 1:** bloqueio exato de slug/repositório/entidades (`owner/repo`).
   - **Camada 2:** embeddings multilíngues em **CPU** (`transformers` `paraphrase-multilingual-MiniLM-L12-v2` com cache float32 no SQLite + fallback automático `sklearn` TF-IDF).
   - **Camada 3:** reabertura permitida somente com atualização substancial explícita (`--allow-update --supersedes-id <ID>`).
4. **Fact-checking HTTP, Proposta Parte 11 (A–F) & Brief Visual em 7 Campos:**
   - Rode `verify --item-id <ID>` (checagem HTTP real, licença e classe de maturidade) e `brief --program <dia>` para obter a proposta **Parte 11 (A–F)** e o **Brief Visual em 7 Campos**.
   - Execute `python tools/editorial_memory.py suggest-styles` e apresente ao usuário (uma decisão por vez, via `ask_question` ou diálogo direto) uma estética **inédita** combinando Blender 5.3, `opus5-reference` (703 prompts), `lemo-opuscar` (100 estilos) e `OpenMontage`, sem repetir a família visual dos vídeos recentes.
   - Após cada publicação, registre título, `video_id`, `visual_style.family`, lições (`insight` + `lessons_learned`) e tópicos via `tools/editorial_memory.py record` (ou `youtube_publish.py --record-history`).

## 1. Passo 0 Obrigatório — Consultar o Tesouro Local Antes de Criar

Antes de escrever código de animação do zero, execute a busca no catálogo local via [`tools/query_animation_catalog.py`](../tools/query_animation_catalog.py):

```powershell
python tools/query_animation_catalog.py --category motion --tech threejs --search chart --top 5
python tools/query_animation_catalog.py --category explainer --tech canvas --search data --top 5
```

### Inventário Oficial de Recursos Locais (100% no disco, US\$ 0,00)

| Recurso | Caminho Local | O que contém | Quando usar |
|---|---|---|---|
| **Catálogo Opus 5.5 (703 prompts)** | `D:\Utilitarios\opus5-reference\` (`videos.json`, `index-by-category.json`, `index-by-tech.json`, `prompts/*.md`) | **703 prompts validados**: `369 motion`, `117 3d`, `116 explainer`, `101 interactive` · tecnologias: `267 canvas`, `183 svg`, `131 threejs`, `92 shader`, `86 gsap`, `57 css`, `39 audio`, `17 particles`, `9 physics`, `9 webgl` | **SEMPRE primeiro** para escolher a linguagem visual, estrutura de cena, shaders, física, partículas ou storytelling animado |
| **OpenMontage Prompt Gallery & Skills** | `D:\Utilitarios\OpenMontage\PROMPT_GALLERY.md` e `D:\Utilitarios\OpenMontage\.agents\skills\` | Skills especializadas: `threejs-animation`, `canvas-procedural-animation`, `manim-composer`, `hyperframes-animation`, `svg-character-animation`, `motion-graphics`, `framer-motion`, `character-animation-qa` | Padrões de código determinístico, frame-accurate no HyperFrames/Remotion/Manim |
| **Lemo-Opuscar (98 estilos em código)** | `C:\Users\Pires\lemo-opuscar\styles\` (skill `lemo-opuscar`) | 98 estilos completos (`news-package`, `hologram-hud`, `circuit-board`, `dark-documentary`, `blueprint`, `dataviz`, etc.) com paletas, gramática de câmera, transições (`wipe-band`) e sound design | Referência de gramática visual, transições broadcast, HUDs e PCBs em código |
| **CLI-Anything (Desenho & 3D)** | Skill `cli-anything-windows` (`C:\Docling\venv`) | `cli-anything-blender` (Blender 5.3), `cli-anything-inkscape` (vetores/SVG), `cli-anything-gimp` (camadas/textos/compositing), `cli-anything-krita` (ilustração), `cli-anything-comfyui` (geração local), `cli-anything-mermaid` (diagramas) | Criação de ativos 3D, desenhos vetoriais, ícones, diagramas técnicos e acabamento gráfico sem GUI |

---

## 2. Matriz de Escolha do Motor de Animação

Nunca force tudo em um único motor — escolha (ou combine) o melhor motor para cada bloco do Diretor Dinâmico (`split`, `full_graphics`, `broll`):

1. **Gráficos de dados, contadores, comparativos de preço/benchmark, lower-thirds e tipografia cinética:**
   - **Prioridade 1:** **HTML/CSS + Canvas / GSAP / Three.js** dentro do **HyperFrames** (inspirado diretamente nos prompts de `D:\Utilitarios\opus5-reference\prompts\`), com render determinístico em 30 fps e tipografia vetorial perfeita.
   - **Prioridade 2:** **Manim** (`manim-composer`) para gráficos matemáticos, curvas de ações e diagramas explicativos.
2. **Objetos 3D físicos, hardware/GPUs, prismas, arquitetura volumétrica e iluminação de estúdio:**
   - **Caminho primário obrigatório (`cli-anything-blender` — economia máxima de tokens):** sempre crie, manipule e inspecione cenas Blender via **`cli-anything-blender`** (`C:\Docling\venv\Scripts\cli-anything-blender.exe` ou in-process `from cli_anything.blender.blender_cli import cli` em `C:\Docling\venv\Scripts\python.exe`, com `D:\Blender` no `$env:PATH`, sem `repl` em shells headless): `scene`, `object`, `material`, `modifier`, `camera`, `light`, `animation`, `preview capture --recipe quick --force` e `render script`.
   - Use ajustes diretos de `bpy` **apenas** como pós-ganchos enxutos injetados na saída do `render script` (ex.: World HDRI procedural, `poly.use_smooth = True` ou export MP4 nativo `media_type = 'VIDEO'` / `MPEG4` / `H264`) em vez de escrever scripts `bpy` extensos do zero.
3. **Ilustrações vetoriais, ícones de marcas/tecnologia, compositing e diagramas de arquitetura:**
   - **`cli-anything-inkscape`** (SVG vetorial limpo), **`cli-anything-gimp`** (compositing em camadas, thumbnails e badges), **`cli-anything-mermaid`** (diagramas técnicos) e **`cli-anything-krita`** quando precisar de ilustração digital.

---

## 3. Regras Invioláveis de Tipografia, Cor e Contraste (Design System)

1. **Contraste mínimo obrigatório (WCAG AAA ≥ 7:1):**
   - **PROIBIDO** texto branco ou claro sobre barras/fundos claros ou pastéis estourados.
   - **PROIBIDO** texto na mesma cor da barra/objeto que ele rotula quando houver risco de baixa leitura.
2. **Hierarquia tipográfica limpa:**
   - **PROIBIDO** usar a fonte padrão `Bfont` do Blender. Use fontes geométricas/sans-serif nítidas (`Segoe UI Bold`, `Bahnschrift`, `Inter`, `Arial Bold`).
   - Rótulos de eixo/categoria devem ficar em **trilho/base escura fosca dedicada** (nunca encostados ou sobrepostos às barras brilhantes).
   - Valores numéricos no topo devem flutuar com folga limpa acima da barra sobre fundo escuro.
3. **Saturação controlada em 3D e Acabamento Fino de Estúdio (Anti-3D "Cru"):**
   - **Malha lisa obrigatória:** use subdivisão alta + `Shade Smooth` no Blender (`subdivisions >= 4`, modificadores Bevel/Subdivision sem facetas visíveis) e geometrias densas no Three.js (`SphereGeometry(r, 64, 64)`, `TorusGeometry(..., 32, 128)`). Proibido esfera facetada ou silhueta poligonal visível.
   - **Iluminação de 3 pontos + Reflexo de Ambiente (HDRI/PMREM):** nenhuma cena 3D pode depender apenas de cor emissiva chapada. Aplique `Key` (luz principal modelando volume), `Rim` (recorte de contorno colorido) e `Fill` suave, combinados com shader de ambiente/HDRI no World do Blender (ou mapa `PMREM`/speculares Fresnel no Three.js) para gerar reflexos reais em superfícies de **vidro óptico** (`Transmission`, `IOR ~1.5`, `Roughness 0.04–0.12`), **espelho/cromo** (`Metallic 0.95–1.0`, `Roughness 0.03–0.12`) e metais escovados (`Coat Weight`).
   - Em cenas Blender sob `AgX`, mantenha `Emission Strength` dos corpos estruturais contida (`0.35–0.55` em dados; `0.0` em vidros/espelhos puros), reservando emissão alta apenas para filamentos e acentos finos.
   - Registre o que funcionou e o que deve evoluir no próximo episódio em `lessons_learned` dentro de `data/published_history.json` — cada vídeo deve superar o acabamento do anterior.
4. **Movimento obrigatório (zero gráfico estático):**
   - Todo bloco gráfico deve ser **animado** (entrada com *easing*, câmera/paralaxe suave, partículas/luzes sutis, contadores dinâmicos). Previews estáticos (`--still-only`) servem **apenas** para auditoria rápida de 5 s antes do render animado completo.
5. **Zero espaço morto (`Full-Stage Flex` + gate `audit_layout_fill.py`):**
   - Toda cena `full_graphics` deve preencher continuamente a zona editorial `y = 152..1484 px` com `#stage { height: 1920px; padding: 152px 52px 436px 52px; display: flex; flex-direction: column; justify-content: space-between; }` e elemento visual animado em `flex: 1`.
   - Rode `python tools/audit_layout_fill.py --mp4 <saida.mp4>` antes da entrega; qualquer faixa de `333 px` com `< 4.0%` de área ativa e `< 0.45%` de densidade de bordas reprova o render.
6. **Auditoria visual obrigatória:**
   - Nenhuma animação ou gráfico pode ser entregue ao usuário sem antes inspecionar visualmente (via `read_file`) o preview (`cli-anything-blender preview capture --recipe quick --force` ou `--still-only`) e os frames finais do vídeo.
7. **Padrão Oficial de Entradas do Avatar V17C ("Abertura + Fechamento 70/30" — Referência `short_github_10_v2` / `8vCg2RN5Ucg`):**
   - **Janelas de entrada:** o avatar entra **apenas na abertura** (`~0.0–3.0 s`) e no **fechamento** (`~últimos 4–5 s`), mantendo `≥ 80–85%` do vídeo com a notícia/visual em tela cheia (`full_graphics` / `broll`, piso rígido `≥ 60%`).
   - **Geometria nativa sem zoom:** faixa inferior nativa `1080×576` (`position:absolute; left:0; top:1344px; width:1080px; height:576px; z-index:27`) combinada com visual protagonista de `1080×1344` no topo (`70/30`). É proibido `full_avatar` (`1080×1920`) ou zoom no rosto.
   - **Continuidade sem blink preto (`av-hold`):** todo segmento de fala do avatar (`av-seg-01`, `av-seg-02`) deve encerrar com sobreposição de `-0.08 s` usando `avatar_hold_bar.mp4` em `z-index: 28` acima do `z-index: 27` (`av-hold-01` na abertura e `av-hold` no encerramento).
   - **Divisor & Legendas Dinâmicas (`#av-divider` + `#captions`):** exiba `#av-divider` (`top: 1341px; height: 4px; z-index: 30`) somente quando `avActive` estiver ativo (`opacity: 1`; `opacity: 0` nas cenas tela cheia); reposicione `#captions` para `top: 1188px` com o avatar ativo e `top: 1512px` nas cenas em tela cheia.

---

## 4. Integração no Fluxo do `avatar-journal` & Graphify

Em cada episódio (`output/YYYY-MM-DD/pauta.json`), o campo `visual_concept` e os blocos `split` / `full_graphics` devem registrar:
1. Qual(is) referência(s) do **`opus5-reference`** ou **`OpenMontage`** foram consultadas (`slug` do prompt);
2. Qual motor de animação será usado (`hyperframes-threejs`, `hyperframes-canvas`, `blender-5.3`, `manim`, `inkscape-svg`);
3. Quais ativos locais (`cli-anything-*` ou `img_01/02`) compõem a cena;
4. **Atualização do grafo de conhecimento (`graphify-out/`):** sempre que novas ferramentas, scripts, skills ou alterações contratuais entrarem no repositório, execute `C:\Users\Pires\.local\bin\graphify.exe update .` na raiz do projeto para manter o grafo atualizado.
