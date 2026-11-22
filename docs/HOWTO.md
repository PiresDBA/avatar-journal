# HOWTO — operar e diagnosticar

## Pré-requisitos

| Recurso | Caminho / porta | Observação |
|---|---|---|
| Wav2Lip | `D:\Utilitarios\Wav2Lip` | `checkpoints/wav2lip_gan.pth`, `inference.py` |
| Python p/ Wav2Lip | `D:\Comfy\ComfyUI\venv\Scripts\python.exe` | torch 2.6 + CUDA |
| LivePortrait | `D:\Utilitarios\LivePortrait` | `pretrained_weights/` completo (human + insightface) |
| ffmpeg | no `PATH` | o Wav2Lip chama `ffmpeg` para muxar |
| VoiceStudio | `http://127.0.0.1:3900` | opcional; `/health` deve reportar `cuda` |
| VoiceCraft (ponte) | `http://127.0.0.1:8090` | opcional |

Os caminhos podem ser trocados por flag (`--wav2lip-dir`, `--liveportrait-dir`,
`--lp-python`, `--python`, `--ffmpeg`) ou por variável de ambiente
(`WAV2LIP_DIR`, `LIVEPORTRAIT_DIR`).

## Ordem de execução

```bash
# 0) plano: copie o exemplo e edite
mkdir -p project/artifacts
cp project/avatar_plan.example.json project/artifacts/avatar_plan.json

# 1) voz clonada (VoiceStudio direto; cai para Piper se falhar)
python tools/voice_craft_tts.py --project ./project --scene 1 --voice Ale-empolgado

# 2) montagem dos segmentos declarados no plano
python tools/avatar_slot.py --project ./project \
    --avatar-dir "D:/PROJETOS-IA/AVATAR" --plan project/artifacts/avatar_plan.json

# 3) movimento (Wav2Lip) — 1 processo por bloco
python tools/avatar_lipsync.py --project ./project --apply

# 4) pixels (LivePortrait) — 1 processo por bloco
python tools/avatar_liveportrait.py --project ./project --apply

# 5) gates + render
cd project/hyperframes
npx hyperframes lint --json
npx hyperframes validate --json
npx hyperframes inspect --json
npx hyperframes render --strict
```

Reexecutar só um bloco:

```bash
python tools/avatar_liveportrait.py --project ./project \
    --only seg_2_headline_split --force --apply
```

Simular sem rodar GPU:

```bash
python tools/avatar_liveportrait.py --project ./project --dry-run
python tools/avatar_lipsync.py --project ./project --dry-run
```

## Catálogo de erros e o que fazer

### “O rosto fica liso/plástico quando fala e nítido quando cala”

O bloco ainda está usando `assets/avatar/lipsync/…`. Rode
`avatar_liveportrait.py --force --apply` para aquele bloco e re-renderize.
Confirme no `index.html` que o `<video>` aponta para `assets/avatar/liveportrait/…`.

### “A boca continua mexendo depois que ele para de falar”

Wav2Lip não fecha a boca em silêncio. O bloco precisa terminar junto da última palavra e dar
lugar a um segmento `lip_sync: false` com o hold neutro (`seg_8_closed_hold`). Ajuste `end` do
bloco de fala para o fim real da locução (medido com `silencedetect` ou pelos timestamps das
palavras em `captions_words.json`).

### “A boca abre demais / caretas”

`--driving-multiplier 0.8~0.9`. Não mexa na voz nem no texto para “corrigir” isso — o áudio
está certo, o exagero vem da transferência de expressão. `--animation-region lip` (padrão) já é
a opção mais conservadora; `exp` piora.

### “O vídeo ficou com ghost / rosto duplicado”

Acontece ao fazer crossfade entre **takes diferentes**. Use dissolve curto (≤ 0,12 s) ou corte
seco. O hold final evita ghost porque o frame é realinhado por pad/crop ao mesmo take.

### “LivePortrait falhou com UnicodeEncodeError / charmap”

Ambiente sem UTF-8. O driver já exporta `PYTHONIOENCODING=utf-8` e `PYTHONUTF8=1`; se rodar
manualmente, exporte antes.

### “Not enough free VRAM”

Feche o que estiver ocupando GPU ou derrube o modelo do VoiceStudio
(`POST /system/flush-memory?unload_model=true`). O guard aborta o bloco e o plano mantém o
clipe anterior (fallback determinístico) — nunca gera vídeo quebrado.

### “Wav2Lip falhou com FileNotFoundError (WinError 2)”

Ele chama `ffmpeg` no momento de muxar. Garanta `D:\Utilitarios\ffmpeg\bin` no `PATH` do
processo filho (o driver já injeta a pasta do ffmpeg resolvido).

## Como comparar motores (A/B)

```bash
# driving alternativo: qualquer clipe com movimento labial sincronizado
python tools/avatar_liveportrait.py --project ./project \
    --only seg_2_headline_split --animation-region exp --driving-multiplier 0.85 \
    --force --out-dir project/hyperframes/assets/avatar/lp_ab
```

Extraia frames e compare lado a lado (mesmo instante, mesma ROI):

```bash
ffmpeg -ss 1.2 -i <clipe>.mp4 -frames:v 1 frame.png
```

## Checklist antes de publicar

- [ ] `avatar_plan.json` com todos os blocos de fala dentro de `speech_blocks`
- [ ] `index.html` apontando para `assets/avatar/liveportrait/…`
- [ ] último frame com boca fechada (QA em ~0,05 s antes do fim)
- [ ] gates 0/0/0 e `render --strict` completo
- [ ] `ffprobe`: 1080×1920, h264, AAC 48 kHz, duração exata
- [ ] `render_report.json` e `final_review.json` atualizados com o md5/tamanho novos
- [ ] nada gerado foi adicionado ao Git (`git status` limpo de mídia/relatórios)

## Custos e tempo (GTX 1060)

| Etapa | Tempo aproximado |
|---|---|
| Wav2Lip por bloco (2–3,5 s) | 1,5–3 min |
| LivePortrait por bloco (2–3,5 s) | 2,5–3,2 min |
| Render HyperFrames 18 s | 5–7 min |

Tudo local: custo monetário **US$ 0,00**.
