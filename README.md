# avatar-journal

Pipeline local de **boletim vertical 9:16 com avatar falante**, voz clonada e lip-sync de
qualidade preservada — rodando **100% offline, US$ 0,00**, em uma **GTX 1060 de 6 GB**.

Este repositório é o recorte de engenharia do projeto `teste-jornal-ia` do OpenMontage:
o código que faz o avatar falar, os artefatos que descrevem a coreografia, o vídeo final e a
documentação de **como e por quê** cada decisão foi tomada.

| | |
|---|---|
| Saída | 1080×1920, h264 + AAC 48 kHz, 18,000 s, ~11 MB (gerada localmente, **fora** do repo) |
| Voz | clone `Ale-empolgado` (VoiceStudio `:3900`, ponte VoiceCraft `:8090`), fallback Piper |
| Lip-sync | **Wav2Lip** (movimento) → **LivePortrait** (pixels) |
| Encerramento | *hold* neutro com boca fechada (17,36–18,00 s) |
| Custo | US$ 0,00 |
| VRAM de pico | ≈ 3,0 GB de 6,1 GB |

---

## O problema que este repositório resolve

A primeira versão usava **Wav2Lip como gerador final**. O resultado tinha dois defeitos que
pareciam um só:

1. **Qualidade**: o Wav2Lip gera a boca dentro de um recorte de **96 px** e o reescala para
   1080×1920. O rosto virava “plástico” exatamente durante a fala — e voltava a ficar nítido no
   trecho mudo (onde nenhum frame passou pelo Wav2Lip).
2. **Sensação de dessincronia**: com a boca borrada e sem detalhe de lábio, o movimento não
   “cola” na fala, mesmo quando o timing está certo.

A auditoria mediu o atraso boca↔áudio por correlação entre o envelope RMS da narração e a
variação do recorte da boca: nos blocos centrais o pico ficou em **0 a ±2 frames (≤ 66 ms)**,
ou seja, o *timing* estava dentro do aceitável — o que faltava era **pixel**. O trecho final
(quase todo silêncio) é um caso degenerado e não serve de medida.

Solução adotada (V2.3 do contrato): **separar movimento de aparência**.

```
voz clonada ──► voice_only_clean.wav ──► Wav2Lip (driving) ──► clipe mudo
                                                                    │
clipe fonte nítido (1080×1920 / 1080×864) ──► LivePortrait (animation_region=lip)
                                                                    │
                                                     clipe final (boca nítida, sincronizada)
```

O comparativo visual (LivePortrait com barba/poros preservados x Wav2Lip liso) é gerado pelo
próprio pipeline com `tools/audit_lipsync.py` + `ffmpeg`; ele **não** é versionado.

O **áudio não mudou** em nenhuma etapa: a voz já estava aprovada. O que mudou foi quem
desenha a boca.

---

## Como funciona (7 etapas)

1. **Voz** — `tools/voice_craft_tts.py` chama o VoiceStudio (`POST /v1/audio/speech`,
   compatível com OpenAI) direto na porta 3900, porque a ponte VoiceCraft corta em 90 s.
   Cai para Piper automaticamente se o clone estiver fora. `AudioMixer` exporta
   `voice_only_clean.wav` (sem música, duração exata) e `final_mix.wav` (trilha com ducking).
2. **Plano** — `project/artifacts/avatar_plan.json` é a única fonte de verdade: `segments`
   (`start`/`end`/`mode`/`clip`), `speech_blocks`, `lip_sync`, `fade_in`/`fade_out`, `zoom`.
3. **Montagem** — `tools/avatar_slot.py --plan` encoda/loop os clipes de catálogo em
   1080×1920 (`full_avatar`) e 1080×864 (`split`), respeita `media_override` e escreve os
   elementos `<video>` na composição HyperFrames.
4. **Movimento (Wav2Lip)** — `tools/avatar_lipsync.py` corta o slice do clipe fonte + o slice
   correspondente da narração e roda o Wav2Lip GAN **em processo novo por bloco** (CUDA é
   liberada entre blocos). Saída muda em `assets/avatar/lipsync/<seg>.mp4`.
   **Nunca vai para o vídeo final.**
5. **Pixels (LivePortrait)** — `tools/avatar_liveportrait.py` usa o slice nítido como `-s` e o
   clipe do Wav2Lip como `-d`, com `--animation_region lip --flag_relative_motion
   --flag_stitching`: só o movimento dos lábios é transferido; cabeça, piscadas, mãos e corpo
   continuam sendo os do material original. Saída em `assets/avatar/liveportrait/<seg>.mp4`.
6. **Encerramento** — a fala termina em 17,32 s; o bloco de avatar é cortado em 17,36 s e um
   *hold* neutro (`seg_8_closed_hold` → `neutral_hold_full.mp4`, frame de `idle` realinhado por
   pad/crop e retimado 0,78×) segura boca fechada e olhos abertos até 18,00 s, com dissolve de
   0,08 s e zoom 1,0→1,02. **Wav2Lip sobre silêncio não fecha a boca** — por isso o hold existe.
7. **Gates** — `hyperframes lint/validate/inspect` e `render --strict`; os frames de QA saem do
   **MP4 renderizado**, não dos stills.

---

## Uso rápido

```bash
# 0) dependências externas (fora deste repo):
#    Wav2Lip ................ D:\Utilitarios\Wav2Lip       (checkpoints/wav2lip_gan.pth)
#    LivePortrait ........... D:\Utilitarios\LivePortrait  (pretrained_weights completos)
#    ffmpeg ................. no PATH
#    VoiceStudio ............ http://127.0.0.1:3900  (opcional; senão Piper)

# 1) voz
python tools/voice_craft_tts.py --project ./project --scene 1 --voice Ale-empolgado

# 2) planejar + montar segmentos
python tools/avatar_slot.py --project ./project --avatar-dir "D:/PROJETOS-IA/AVATAR" \
    --plan project/artifacts/avatar_plan.json

# 3) movimento
python tools/avatar_lipsync.py --project ./project --apply

# 4) pixels
python tools/avatar_liveportrait.py --project ./project --apply

# 5) gates + render (workspace HyperFrames dentro de project/hyperframes)
cd project/hyperframes
npx hyperframes lint --json && npx hyperframes validate --json && \
npx hyperframes inspect --json && npx hyperframes render --strict
```

Ajuste fino útil: `--driving-multiplier 0.85` suaviza a boca se ela ficar exagerada;
`--animation-region exp` transfere a expressão inteira (pode exagerar no olhar).

### Auditar (sincronia + nitidez, com números)

```bash
python tools/audit_lipsync.py --project ./project
# grava project/artifacts/quality_audit.json
```

Resultado desta entrega: Wav2Lip entrega 23–41 % da nitidez do material original; o LivePortrait
sobe para 39–83 % (quase o dobro), com lag de 0–3 frames nos blocos centrais. O relatório JSON
é gerado localmente (não versionado).
Tabela completa e limitações da métrica: **[docs/SYNC-AUDIT.md](docs/SYNC-AUDIT.md)**.

Detalhes, diagnóstico e comparação de motores: **[docs/HOWTO.md](docs/HOWTO.md)**.
Arquitetura, orçamento de VRAM e decisões: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.
Manual em português, sem jargão: **[docs/MANUAL_PT.md](docs/MANUAL_PT.md)**.

---

## Estrutura

```
tools/                        programa: slot · lipsync · liveportrait · tts · auditoria
project/avatar_plan.example.json   configuracao de exemplo (copie para project/artifacts/)
project/hyperframes/          template da composicao (index.html + compositions)
docs/                         arquitetura, how-to, auditoria, manual
```

### O que **não** é versionado (e por quê)

O repositório carrega **apenas o programa**. Tudo que o pipeline gera ou consome fica na
máquina e está bloqueado pelo `.gitignore`:

- vídeo renderizado, clipes de avatar, clipes de lipsync/LivePortrait;
- voz clonada, trilha, legendas queimadas (`.mp4 .wav .mp3 .srt .vtt`);
- imagens e posters (`.jpg .png .webp`), logs de inferência;
- relatórios gerados em `project/artifacts/` e `project/hyperframes/assets/`;
- segredos e ambiente: `.env*`, `*.key`, `*.pem`, `credentials.json`, `secrets.json`, etc.

Se precisar compartilhar o resultado, publique o MP4 fora do Git (release, Drive) e mantenha
o repositório limpo.

## Limites conhecidos

- LivePortrait re-renderiza a face em espaço de recorte de 512 px: é muito superior ao Wav2Lip,
  mas não é 4K. Em `full_avatar` o rosto fica nítido; em `split` também.
- O Wav2Lip é usado como *dithering de movimento*: se ele errar a forma da boca, o LivePortrait
  repete o erro (com pixels melhores). Para trocar de motor de movimento, basta alimentar
  `avatar_liveportrait.py` com outro driving.
- LivePortrait é **video-driven**, não audio-driven: a sincronia vem do clipe de driving.
- Blocos longos (>6 s) custam ~3 min por bloco nesta GPU.

## Licença

Código deste repositório: MIT (ver `LICENSE`). Os clipes de avatar, a voz clonada e o vídeo
final pertencem ao autor do material original e **não** estão licenciados para reuso.
