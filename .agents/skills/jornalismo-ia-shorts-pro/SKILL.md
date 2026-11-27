---
name: jornalismo-ia-shorts-pro
description: >-
  Ponto de partida editorial e de producao do avatar-journal. Pesquisa 10 a 20
  noticias reais e verificadas de IA (diaria ou semanal), coleta ou gera 1 a 2
  ativos visuais por noticia, entrega Tabela Mestra + contrato pauta.json
  deterministico e aciona a producao dinamica de Shorts (18s-60s, 9:16) e cortes
  documentais (16:9) somando o melhor dos dois mundos: pipeline 100% local do
  avatar-journal (VoiceStudio/Piper + Avatar V17C (--segments) em faixa inferior +
  HyperFrames + earshot na GTX 1060) com suporte aditivo a Blender 5.3 (topo 3D Alpha), Reallusion
  (iClone/AccuLips) e Remotion/OpenMontage. Use sempre que o usuario pedir pauta
  diaria/semanal de IA, resumo jornalistico de tecnologia ou disparar a producao
  automatizada de videos a partir de noticias.
---

# jornalismo-ia-shorts-pro (Unificada ao `avatar-journal`)

Ponto de partida completo que une **jornalismo técnico verificado** (Fase 1) com **produção audiovisual local e modular** (Fase 2), somando o melhor de todos os mundos sem descartar nenhum motor:

- **Motor padrão (100% local, US$ 0,00, GTX 1060 6 GB):** `avatar-journal` + **`D:\Utilitarios\gerador-avatar` (V17C Segment-Aware)**
  - Voz clonada local (`tools/voice_craft_tts.py` → VoiceStudio `:3900`, fallback Piper) com roteiro fonético PT-BR quando necessário (ex.: `"sáiber-defesa"` no TTS mantendo `"ciberdefesa"` na tela)
  - Diretor Dinâmico de Avatar (`tools/pauta_to_plan.py` → `avatar_plan.json` → `tools/avatar_slot.py`) com corte seletivo (`--segments`)
  - **Avatar V17C (`D:\Utilitarios\gerador-avatar\generate_avatar.py`)**: S3FD + `203` landmarks (`out[2][0]`) ancorados quadro-a-quadro no `avatar_base_9x16_30fps.mp4` + Hysteresis VAD (`silence_chunk`) + MuseTalk 1.5 FP16 + BiSeNet Softmax GPU + Farneback Perioral Muscle Coupling com proteção de bigode (`inner_mouth` erodido) + GFPGAN 1.4 GPU com luz LAB quadro-a-quadro + faixa inferior `--bottom-bar-height 648` (laterais borradas sem zoom) + `verify_lip_sync_gate`
  - Encerramento neutro com boca fechada em faixa inferior sem zoom (`avatar_hold_bar.mp4`, `closed_hold`, `lip_sync: false`)
  - Composição determinística **HyperFrames** (`lint`, `validate`, `inspect`, `render --strict`) + auditoria auditiva (`earshot`, `read_file`) e visual (`audit_lipsync.py`, `audit_lip_signal.py`, `all_cuts_qa.png`, `final_short_XX_qa.png`)
- **Camadas aditivas / alternativas preservadas (somar, nunca subtrair):**
  - **Blender 4.x** (`blender_scene.py` → `blender_top.mov` com canal Alpha): pode alimentar a metade superior (`1080×1056`) em cenas `split` ou tela cheia (`1080×1920`) em `full_graphics`, combinado com o avatar local do `avatar-journal` na parte inferior.
  - **Reallusion iClone / AccuLips** (`reallusion_script.txt` → `avatar.mp4`): mantido como motor alternativo de avatar 3D (ou como vídeo de entrada/override no plano).
  - **Remotion / OpenMontage** (`montage_config.json`): mantidos como compositores alternativos ao HyperFrames.

---

## Regras de Ouro (Não Violáveis)

1. **Zero alucinação:** Nunca invente números, preços por 1M de tokens, VRAM/RAM, datas, benchmarks, nomes de modelos ou URLs. Se a busca estiver indisponível ou um dado não puder ser confirmado, marque `null` no JSON e sinalize explicitamente o que falta.
2. **Tom editorial:** Direto, técnico, crítico, sem bajulação e sem adjetivos vazios.
3. **Execução em fases (controle de tokens):** Nunca despeje 10+ roteiros completos e dezenas de scripts em uma única resposta truncada. Execute **Fase 1** (Pesquisa + Ativos + Tabela Mestra + `pauta.json`) e itere **um Short por vez** na **Fase 2**.
4. **Regra de 1 a 2 imagens ou vídeo por notícia (obrigatório):**
   - **Prioridade 1 (Mídia Real):** Busque e referencie a imagem real da notícia e/ou link direto do vídeo demo oficial (YouTube, X, blog oficial) para PiP ou recorte de tela.
   - **Prioridade 2 (Fallback Editorial):** Quando não houver foto real utilizável (ou para documentários 16:9), gere ou entregue prompt pronto para ComfyUI/gerador com 1 a 2 imagens editoriais limpas, sem texto distorcido e sem clichês de "cérebro azul brilhante", pensadas para receber gráficos/animações por cima.
5. **Diretor Dinâmico "Notícia Protagonista" (obrigatório):**
   - O avatar é coadjuvante: **nunca** aparece em tela cheia (`full_avatar` proibido) nem recebe zoom no rosto.
   - O vídeo alterna apenas entre tela cheia editorial e faixa inferior:
     - `full_graphics` ou `broll` (`1080×1920`, **≥ 60% do vídeo, sem avatar**) — notícia, gráficos animados, tabelas ou Blender 3D em tela cheia;
     - `bottom_bar_split` (notícia/gráfico em `0–1344 px` + divisória em `1342 px` + legendas em `1194 px` + avatar em `1344–1920 px`, `1080×576` via `--bottom-bar-height 576`) — padrão **70/30** com `avatar_base_1080x576_30fps.mp4` nativo sem zoom e sem blur lateral;
     - `closed_hold` (`avatar_hold_bar.mp4`, `lip_sync: false`) — também na faixa `1080×576`, com sobreposição/crossfade (`z-index: 20` sobre `19` iniciando `-0,08 s` antes do fim do último segmento) **sem zoom**.
6. **Orçamento GTX 1060 (6 GB) & `--segments`:** Blocos onde o avatar aparece são renderizados seletivamente via `--segments` (economizando ~60% de GPU nos trechos ocultos), após flush do VoiceStudio.
7. **Tags de voz sempre validadas:** Antes de sintetizar voz, valide o texto com `tools/voice_craft_tts.py --lint-tags` para garantir que nenhuma marcação não suportada (como `[breath]` sem CosyVoice 3) seja lida em voz alta.
8. **Contrato Obrigatório de Animação e Design (`docs/ANIMATION_CONTRACT.md`):** Antes de criar qualquer gráfico, animação ou desenho para cenas `split`/`full_graphics`/`broll`, **consulte primeiro** o catálogo local de **703 prompts do Opus 5.5** (`python tools/query_animation_catalog.py --category ... --tech ... --search ...`), a galeria/skills do `D:\Utilitarios\OpenMontage` (`threejs-animation`, `canvas-procedural-animation`, `manim-composer`, `hyperframes-animation`, `svg-character-animation`) e os harnesses `cli-anything-*` (`blender`, `inkscape`, `gimp`, `krita`). Cumpra contraste WCAG AAA (≥ 7:1, zero branco sobre cor clara), fonte limpa (`Segoe UI Bold`/`Inter`), movimento contínuo (zero gráfico estático final) e auditoria visual obrigatória via `read_file`.
9. **Gate Editorial Anti-Repetição (`data/published_history.json`):** Antes de pesquisar ou fechar a pauta, execute `python tools/editorial_memory.py list` e valide todos os candidatos com `python tools/editorial_memory.py check --topics "..."` (ou `--pauta ...`). É **proibido** repetir assunto/repositório/notícia já coberto nos vídeos anteriores sem pedido explícito do usuário. Após publicar, registre o novo vídeo e `lessons_learned` via `editorial_memory.py record` ou `youtube_publish.py --record-history`.
10. **Briefing Visual Interativo, Rotação de Estilos & Acabamento 3D Fino:** Rode `python tools/editorial_memory.py suggest-styles` antes de montar qualquer cena e **pergunte ao usuário** (via `ask_question`) qual direção visual/material deseja usar ou mesclar (**Espelho & Cromo HDRI**, **Vidro Óptico & Refração 3D**, **Diorama Blender 5.3**, **Showreel GLSL/Three.js** ou **Mix Curado**), evitando repetir o estilo recente. Exija acabamento 3D de estúdio: subdivisão alta + `Shade Smooth` (zero esfera/malha facetada), iluminação de 3 pontos (`Key` + `Rim` + `Fill`), reflexos HDRI/PMREM reais e emissão restrita a acentos.

---

## Estrutura de Pastas Determinística

### Camada editorial (saída da Fase 1 — fora do Git)
`output/{YYYY-MM-DD}/`
- `pauta.json` — contrato mestre de dados
- `short_{NN}/`
  - `img_01.png` e `img_02.png` — imagens reais baixadas ou editoriais geradas
  - `ref_video.mp4` — opcional, demo oficial
  - `blender_scene.py` e `blender_top.mov` — opcional (Blender 4.x, metade superior com Alpha)
  - `reallusion_script.txt` e `avatar.mp4` — opcional (Reallusion iClone/AccuLips)
  - `montage_config.json` — opcional (OpenMontage / Remotion)
  - `final_short_{NN}.mp4` — entrega final

### Camada de produção local (`avatar-journal` — fora do Git)
`project/artifacts/` (gerado por `tools/pauta_to_plan.py`):
- `avatar_plan.json` — coreografia canônica (4 modos + `speech_blocks` + `closed_hold`)
- `voiceover.txt` — texto final da locução para `voice_craft_tts.py`
- `short_brief.json` — metadados completos do Short (fatos, fontes, ativos, hooks opcionais de Blender/Reallusion/Remotion e relatório de lint de tags)

---

## Fase 1: Pesquisa, Tabela Mestra e Contrato `pauta.json`

1. Consulte `python tools/editorial_memory.py list` e pesquise de **10 a 20 fatos densos e verificados** do período (últimas 24h para diária; últimos 7 dias para semanal), descartando qualquer tema bloqueado por `python tools/editorial_memory.py check --topics "..."`.
2. Consulte `python tools/editorial_memory.py suggest-styles` (703 prompts Opus 5.5 + 98 estilos Lemo-Opuscar + Blender 5.3 + OpenMontage) e alinhe com o usuário qual estética/material será usada neste episódio.
2. Priorize fontes confiáveis: blogs oficiais (Google, OpenAI, Anthropic, Meta, NVIDIA, xAI, Alibaba, Hugging Face), imprensa (Reuters, BBC, Financial Times, TechCrunch, The Verge, 9to5Google), arXiv, GitHub, X (Twitter), Reddit e YouTube.
3. Entregue a **Tabela Mestra Jornalística** em Markdown com as colunas:
   - `# / Categoria` (`Modelos Frontier`, `Open-Weight/Local`, `Agentes`, `Hardware/GPUs`, `Mercado/Bolsas`, `Regulação`, `Cibersegurança`, `Tendências X/Reddit`)
   - `Manchete / Fato`
   - `Detalhes Técnicos e de Mercado` (preços/1M tokens, VRAM/RAM, quantização, parâmetros, benchmarks, datas)
   - `Ativos Visuais (1-2 Imagens / Vídeo PiP)`
   - `Fonte Verificada`
4. Exporte o bloco **`pauta.json`** no esquema abaixo (100% retrocompatível com a versão original e estendido para o `avatar-journal`):

```json
{
  "date": "YYYY-MM-DD",
  "mode": "daily | weekly",
  "avatar_engine_default": "avatar-journal | reallusion | blender-hybrid",
  "compositor_default": "hyperframes | openmontage | remotion",
  "shorts": [
    {
      "id": "short_01",
      "category": "Modelos Frontier",
      "headline": "Título curto de impacto",
      "duration_seconds": 36.0,
      "visual_concept": "Conceito único de animação (ex: paralaxe 3D sobre foto + escala de custo)",
      "facts": [
        {
          "claim": "Fato verificado com número exato",
          "metrics": "US$ X/1M in, Y GB VRAM, etc.",
          "source_name": "Nome do Veículo",
          "source_url": "https://..."
        }
      ],
      "assets": {
        "img_01": { "type": "real | generated", "url_or_prompt": "...", "local_path": "short_01/img_01.png" },
        "img_02": { "type": "real | generated", "url_or_prompt": "...", "local_path": "short_01/img_02.png" },
        "ref_video_url": null
      },
      "optional_engines": {
        "blender_top": null,
        "reallusion_avatar": null,
        "remotion_props": null
      },
      "voiceover": {
        "text": "Roteiro completo (45-55 palavras para ~18s, 90-100 para ~36s, 135-150 para ~60s)...",
        "word_count": 95,
        "blocks": [
          { "time": "00:00-00:05", "role": "gancho", "mode": "bottom_bar_split", "visual_cue": "img_01 + manchete + selo_fonte" },
          { "time": "00:05-00:15", "role": "dado_1", "mode": "full_graphics", "visual_cue": "animacao_sobre_img_01_tela_cheia" },
          { "time": "00:15-00:21", "role": "respiro_visual", "mode": "bottom_bar_split", "visual_cue": "grafico_ou_blender_top + selo_fonte" },
          { "time": "00:21-00:30", "role": "dado_2_tradeoff", "mode": "full_graphics", "visual_cue": "transicao_img_02 + comparativo_tela_cheia" },
          { "time": "00:30-00:35", "role": "fechamento", "mode": "bottom_bar_split", "visual_cue": "resumo_2_linhas + hold_neutro_1080x648" }
        ]
      }
    }
  ]
}
```

> **Nota de compatibilidade:** o campo `mode` dentro de `voiceover.blocks`, `duration_seconds` e `optional_engines` são opcionais. Se o `pauta.json` vier no formato original (apenas `time`, `role`, `visual_cue`), o conversor `tools/pauta_to_plan.py` deduz a coreografia dinâmica automaticamente.

---

## Fase 2: Produção por Short (O Melhor de Todos os Mundos)

Ao avançar para um Short específico (`short_01`, `short_02`, ...), escolha ou combine os caminhos abaixo conforme a necessidade do episódio:

### Caminho A — Padrão Local (`avatar-journal`, US$ 0,00, GTX 1060)

1. **Converter `pauta.json` em plano de produção + validar tags TTS:**
   ```bash
   python tools/pauta_to_plan.py \
     --pauta output/YYYY-MM-DD/pauta.json \
     --short short_01 \
     --project ./project
   ```
   O script gera `project/artifacts/avatar_plan.json` (já fatiado em blocos ≤ 6 s com alternância dinâmica `full_avatar`/`split`/`full_graphics` e `closed_hold` final), `project/artifacts/voiceover.txt` e `project/artifacts/short_brief.json`.

2. **Executar o pipeline completo (ou simular com `--dry-run`):**
   ```bash
   # Simular todo o fluxo sem gastar GPU
   python tools/run_short.py \
     --pauta output/YYYY-MM-DD/pauta.json \
     --short short_01 \
     --project ./project \
     --avatar-dir "D:/PROJETOS-IA/AVATAR" \
     --dry-run

   # Rodar de ponta a ponta (voz -> slot -> Wav2Lip -> LivePortrait -> gates -> render)
   python tools/run_short.py \
     --pauta output/YYYY-MM-DD/pauta.json \
     --short short_01 \
     --project ./project \
     --avatar-dir "D:/PROJETOS-IA/AVATAR" \
     --voice Ale-empolgado \
     --audit
   ```
   Parâmetros de produção preservados por padrão:
   - LivePortrait: `--animation-region lip --driving-multiplier 0.7 --drive-shift-frames 5` + colagem só-da-boca (`mouth_composite` ligado).
   - Gates obrigatórios antes de aprovar: `hyperframes lint`, `validate`, `inspect` (0/0/0) e `render --strict`.
   - Auditoria opcional (`--audit`): `audit_lipsync.py` (nitidez) + `audit_lip_signal.py` (landmarks 203 pts).

### Caminho B — Híbrido (Blender 4.x no topo + `avatar-journal` embaixo)

Quando a notícia pede visualização 3D exclusiva (gráfico volumétrico, hardware/GPU em 3D, paralaxe sobre foto real):
1. Gere `output/{YYYY-MM-DD}/short_{NN}/blender_scene.py` (Blender 4.x) renderizando `blender_top.mov` (ProRes 4444 / PNG Alpha) na área superior (`1080×1056` para `split` ou `1080×1920` para `full_graphics`).
2. Referencie `optional_engines.blender_top` no `pauta.json` e passe `--engine blender-hybrid` no `pauta_to_plan.py`: os segmentos `split` e `full_graphics` registram o asset do Blender no `short_brief.json` e no `avatar_plan.json`, enquanto o avatar real no painel inferior continua sendo animado pelo `avatar-journal` (Wav2Lip → LivePortrait).

### Caminho C — Alternativos (Reallusion iClone/AccuLips e Remotion/OpenMontage)

Quando o projeto exigir avatar 3D estilizado ou outro compositor:
- **Reallusion:** gere `reallusion_script.txt` com marcações de gestos/emoção para AccuLips; o `avatar.mp4` resultante pode ser usado como `media_override` no `avatar_plan.json` ou até como vídeo *driving* de entrada para o LivePortrait.
- **Remotion / OpenMontage:** gere `montage_config.json` espelhando os mesmos `segments` e `speech_blocks` de `avatar_plan.json` (mantendo a regra do Diretor Dinâmico e das zonas seguras 9:16 com 300 px livres no rodapé).

---

## Checklist Final Antes de Publicar

- [ ] Todos os números, preços, VRAM e URLs do `pauta.json` são verificados (ou `null` explícito).
- [ ] Avatar **nunca** em tela cheia e **sem zoom**; apenas `full_graphics`/`broll` (≥ 60% do vídeo) e `bottom_bar_split` (`1080×648`, `--bottom-bar-height 648`), renderizado via `--segments`.
- [ ] Pronúncia PT-BR ajustada foneticamente no TTS (ex.: `"sáiber-defesa"` mantendo `"ciberdefesa"` na tela), áudio validado com `earshot` + escuta (`read_file`) e `assets/` re-vinculados via hardlink após qualquer regeração.
- [ ] `--lint-tags` sem tags não suportadas no motor de voz ativo e `verify_lip_sync_gate` aprovado.
- [ ] Portões HyperFrames 0/0/0 (`lint`, `validate`, `inspect`, `render --strict`), zero frames vazios/blinks pretos em `all_cuts_qa.png`, sem reset em `blender_top.mp4` (`data-media-start="2.0"`) e QA completo via `final_short_XX_qa.png` + últimos quadros (`read_file`).
- [ ] Nenhum tema repetiu vídeo anterior (`editorial_memory.py check` exit `0`) e o vídeo novo + `lessons_learned` foram gravados em `data/published_history.json` após o upload.
- [ ] Estilo visual rotacionado em consenso prévio com o usuário e cenas 3D com `Shade Smooth`, luz 3-pontos e reflexos HDRI/PMREM (zero objeto facetado ou emissivo chapado).
- [ ] Nenhum arquivo de mídia ou relatório foi adicionado ao Git (`git status` limpo).
