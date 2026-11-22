# DESIGN.md — Boletim IA Dev (Protótipo 18s · 9:16)

## Direção de Arte (Atelier)
Protótipo de telejornalismo tech brasileiro em ritmo ágil (`1080x1920`, `30fps`, `18.0s`), traduzindo **três receitas distintas** indexadas em `D:\Utilitarios\opus5-reference` via `tools/motion_router.py`, sem reutilização de templates stock.

## Mapeamento das Cenas e Receitas Opus 5.5
1. **Cena 1 (`0–6s`) — `scene-1-alerta.html` (`howdevelop-733090`, categoria `motion`)**:
   - **Tema**: Manchete de impacto ("2 viradas em IA mudam seu código").
   - **Gramática**: Canvas grafite escuro (`#090C12`), cursor de prompt piscante, rede SVG expansiva com nós luminosos e tipografia cinética escalonada (`Outfit 900`).
2. **Cena 2 (`6–12s`) — `scene-2-dados.html` (`verbove-268381`, categoria `explainer`)**:
   - **Tema**: Notícia 1 — Anthropic **Claude Fable 5.2** (`1M tokens`, `+30% velocidade`, `$8 / $40`).
   - **Gramática**: Fundo azul-ardósia (`#0B1324`), um único container morphing com indicador de abas elástico, cursor determinístico, contadores numéricos animados e barras comparativas via `scaleX`.
3. **Cena 3 (`12–18s`) — `scene-3-agentes.html` (`morse-369333`, categoria `3d`)**:
   - **Tema**: Notícia 2 — Microsoft **MAI Code 2** no GitHub Copilot (`96% performance`, `5% custo`) + fechamento.
   - **Gramática**: Inversão dramática para canvas light warm-gray (`#F3F1EC`), componentes preto/branco (`#111318`/`#FFFFFF`), acento laranja editorial (`#B8330A` / `#C83E12`), paleta `⌘K` → terminal autônomo → toast `14/14 PASS` e fechamento.

## Tipografia (Compatível com Compilador Determinístico HyperFrames)
- **Display / Manchetes**: `Outfit` (700, 800, 900)
- **UI / Legendas**: `Inter` (500, 600, 700, 800)
- **Código / Telemetria**: `JetBrains Mono` (500, 700)

## Zonas Seguras 9:16 — Diretor de Layout Dinâmico (1080x1920)
Orquestrado por [avatar_plan.json](file:///d:/Utilitarios/OpenMontage/projects/teste-jornal-ia/artifacts/avatar_plan.json) e `tools/avatar_slot.py` (`--avatar-dir`) sem moldura circular fixa, alternando 4 modos em 7 trechos (`18.0s`):
- **Barra Editorial Superior Compacta**: `top: 44px`, `left/right: 44px`, `height: 60px`.
- **`full_avatar` (`0.0–2.5s`, `16.5–18.0s`)**: Avatar `speaking_full.mp4` em `1080×1920` (`scale 1.00 → 1.05` / `1.02 → 1.08`), vinheta leve e lockup final em `top: 1280px`.
- **`split` (`2.5–6.0s`, `9.5–12.0s`, `14.5–16.5s`)**: Área superior `0–1056px` (`padding: 124px 52px 986px 52px`) com motion graphic + divisória `2px` verde-esmeralda/ciano em `top: 1055px` + área inferior `1056–1920px` (`1080×864`, `speaking_split` / `pointing_split` / `idle_split`).
- **`full_graphics` (`6.0–9.5s`)**: Motion graphic Cena 2 (`#s2-full-view`) ocupando `100%` da altura útil (`padding: 128px 52px 564px 52px`), zero espaço vazio na metade inferior.
- **`broll` (`12.0–14.5s`)**: `broll_laptop_full.mp4` (`1080×1920`, `scale 1.00 → 1.04`) com vinheta cinematográfica `#cinema-vignette`.
- **Legendas Dinâmicas na Zona Segura**: Centralizadas horizontalmente (`54px Outfit 900`), posicionadas por modo em `y = 950–1050px` (`split`) ou `y = 1390–1490px` (`full_avatar`, `full_graphics`, `broll`), mantendo os últimos `300px` (`y = 1620..1920px`) livres para UI de YouTube Shorts / Reels.
