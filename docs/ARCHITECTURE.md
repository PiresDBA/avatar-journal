# Arquitetura e decisões

## 1. Objetivo

Produzir um boletim vertical 9:16 (1080×1920, 30 fps) de ~18 s com:

- voz clonada local, sem custo por caractere;
- avatar falando com sincronia e **nitidez constante** (falando e em silêncio);
- coreografia de layout declarativa (4 modos), nunca hardcoded na composição;
- encerramento neutro com boca fechada;
- orçamento de hardware fixo: **GTX 1060, 6144 MB de VRAM**.

## 2. Cadeia de execução

```
voice_craft_tts.py  ──►  assets/audio/voice_only_clean.wav  (sem música, 18,000 s)
        │                assets/audio/final_mix.wav         (trilha + ducking −12 dB)
        ▼
avatar_plan.json  (segments, speech_blocks, lip_sync, fade, zoom)
        │
        ├──► avatar_slot.py ──────────► <video> no index.html (1080×1920 | 1080×864)
        │
        ├──► avatar_lipsync.py ───────► assets/avatar/lipsync/<seg>.mp4      (movimento)
        │         source: clipe do catálogo, áudio: slice de voice_only_clean
        │
        └──► avatar_liveportrait.py ──► assets/avatar/liveportrait/<seg>.mp4 (pixels)
                  -s = slice nítido do clipe fonte
                  -d = clipe do Wav2Lip
                  --animation_region lip --flag_relative_motion --flag_stitching
```

`avatar_lipsync.py` e `avatar_liveportrait.py` aceitam `--apply`, que grava
`media_override` + `media_start: 0.0` (+ `lip_engine: liveportrait`) no plano. O
`avatar_slot.py` então monta exatamente esses arquivos.

## 3. Por que dois estágios

Wav2Lip gera a boca em um crop de 96×96 e faz *blend* de volta no frame. Em 1080×1920 isso
significa reconstruir a região perioral com ~1/11 da resolução, e o resultado é o clássico
rosto “de cera”: pele lisa, barba borrada, lábios sem contorno. O trecho final (sem lipsync)
continuava nítido — daí a impressão de que “a qualidade cai só quando ele fala”.

LivePortrait resolve isso porque ele **não sintetiza pixels do driving**: ele extrai
movimento (pose + expressão) do clipe de driving e o aplica ao *appearance feature* do frame
fonte, gerando a face em espaço de recorte de 512 px e fazendo paste-back no frame original.
Com `--animation_region lip` apenas a região dos lábios é animada, então cabeça, piscadas,
mãos e tatuagem permanecem do material original.

### Calibração obrigatória (o que a auditoria mostrou)

Usar LivePortrait no frame inteiro ainda amacia o rosto: a metade superior (olhos/testa, onde
nada se move) caiu de nitidez 207 para 92. Três correções entraram por padrão:

| Correção | Efeito medido |
|---|---|
| `composite_mouth` — fonte nítida em tudo, LivePortrait só numa elipse com feather na boca (+ unsharp 0.35) | metade superior volta a 204–218 (fonte 207) |
| `--driving-multiplier 0.7` (era 1.0) | abertura labial vs fonte: 0.95 → 0.73 (sem perder articulação) |
| `--drive-shift-frames 5` | o filtro temporal do LivePortrait adiciona ~4 frames; atraso por onsets de palavra: 206 ms → 73 ms |

Resultado: nitidez de barba/poros igual falando e em silêncio, boca sem exagero e sincronia na
faixa de 2 frames (66 ms).

### Alternativas avaliadas

| Opção | Resultado |
|---|---|
| Wav2Lip como output final | V1 entregue; rosto liso durante a fala (rejeitado) |
| LivePortrait `animation_region=exp` (expressão inteira) | Sobreactua quando o driving é Wav2Lip (olhos fechados, boca muito aberta) |
| LivePortrait `animation_region=lip` | **Escolhido**: boca animada, resto preservado |
| Crossfade para outro take `idle` | Dupla exposição (ghost) — rejeitado |
| Wav2Lip estendido sobre o silêncio final | Não fecha a boca (rejeitado) |

## 4. Encerramento

A última palavra (“até amanhã!”) termina em **17,32 s**. O bloco de avatar é cortado em
**17,36 s** e o segmento `seg_8_closed_hold` (17,36–18,00) mostra um *hold* neutro:

- fonte: frame do take `idle` (9,5–10,0 s) — boca fechada, olhos abertos;
- realinhamento: `pad=1096:1944:8:12` + `crop=1080:1920` (corrige +8/+12 px de deslocamento
  em relação ao take falado, medido por detecção de face);
- retiming 0,78× + `tpad` para cobrir 0,64 s;
- dissolve de 0,08 s (2–3 frames) e zoom 1,0→1,02 para não parecer congelado.

## 5. Orçamento de VRAM (GTX 1060, 6144 MB)

| Etapa | VRAM observada |
|---|---|
| LivePortrait (half precision) | ~1,3 GB de pico |
| Wav2Lip GAN (`resize_factor 2`, batch 8) | ~1,7 GB de pico |
| VoiceStudio (OmniVoice, CUDA) | ~3,0 GB residente |

Por isso cada bloco roda em **processo separado** (CUDA liberada ao final) e o driver checa
`torch.cuda.mem_get_info()` antes de começar (`--min-free-mb`, padrão 700 MB para
LivePortrait e 900 MB para Wav2Lip).

## 6. Gates de qualidade (não-regressão)

- `hyperframes lint` → 0 erros / 0 warnings
- `hyperframes validate` → `contrastFailures = 0`
- `hyperframes inspect` → `issues = 0`
- `hyperframes render --strict` → todos os frames (540 para 18 s @ 30 fps)
- `ffprobe` → 1080×1920, h264, AAC 48 kHz, duração exata
- QA visual em frames extraídos **do MP4** (não dos stills), incluindo 17,95 s

## 7. Decisões registradas

`project/artifacts/decision_log.json` (gerado em tempo de execução, não versionado) guarda cada escolha com opções, notas e motivo. As mais
relevantes para este repositório:

- **d-015** — encerramento neutro com boca fechada.
- **d-016** — Wav2Lip vira gerador de movimento; LivePortrait passa a gerar os pixels.
- **d-017** — composite só-da-boca + `driving_multiplier 0.7` + `drive_shift_frames 5`.

## 8. Estrutura dos artefatos

Tudo abaixo é **saída do pipeline** e fica fora do Git (ver `.gitignore`); apenas
`project/avatar_plan.example.json` é versionado como exemplo de entrada.

| Arquivo | Papel |
|---|---|
| `avatar_plan.json` | coreografia canônica (segmentos, janelas de fala) |
| `lipsync_report.json` | o que o Wav2Lip processou, VRAM e tempos por bloco |
| `liveportrait_report.json` | o que o LivePortrait processou, região, multiplicador e tempos |
| `captions_words.json` | legendas palavra-a-palavra alinhadas por ASR |
| `render_report.json` / `final_review.json` | evidência técnica e revisão final do render |
| `scene_plan.json` / `edit_decisions.json` | plano de cenas e decisões de edição |
