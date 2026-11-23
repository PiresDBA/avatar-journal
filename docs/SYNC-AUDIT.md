# Auditoria de sincronia e nitidez

Relatório executável: `python tools/audit_lipsync.py --project ./project`
→ grava `project/artifacts/quality_audit.json` (gerado localmente, não versionado).

## Método

| Pergunta | Medida |
|---|---|
| A boca está atrasada/adiantada? | correlação cruzada normalizada entre o envelope RMS do áudio (30 Hz) e a diferença entre frames na região da boca (30 Hz). `lag` positivo = boca reage **depois** do áudio. |
| O rosto perdeu nitidez? | variância do Laplaciano dentro da caixa do rosto, média por frame (“sharpness”). |

Limite conhecido: blocos com muito silêncio dão correlação fraca e lag instável — o número de
`seg_7` (0,86 s, quase toda pausa) não deve ser lido como sincronia real.

## Resultado de referência (18 s, 5 blocos com boca animada)

Números da entrega que originou este repositório (o relatório completo é regerado a cada run):

| Bloco | Fonte (sharpness) | Wav2Lip | LivePortrait | Lag Wav2Lip | Lag LivePortrait |
|---|---|---|---|---|---|
| `seg_1` 0,0–2,5 s | 28,2 | 11,5 (0,41×) | **21,8 (0,77×)** | +6 f (0,20 s) | +6 f |
| `seg_2` 2,5–6,0 s | 265,0 | 64,9 (0,24×) | **114,0 (0,43×)** | 0 f (0,00 s) | −10 f |
| `seg_4` 9,5–12,0 s | 261,2 | 71,7 (0,27×) | **111,7 (0,43×)** | +13 f (0,43 s) | +7 f |
| `seg_6` 14,5–16,5 s | 293,6 | 68,7 (0,23×) | **113,7 (0,39×)** | −3 f (−0,10 s) | −3 f |
| `seg_7` 16,5–17,36 s | 28,2 | 11,4 (0,40×) | **23,5 (0,83×)** | (silêncio: não confiável) | — |

Leitura:

- **Nitidez**: o Wav2Lip entrega 23–41 % da nitidez do material original; o LivePortrait sobe
  para 39–83 % — praticamente o dobro, e nos blocos em tela cheia chega a 0,83× (o resto é a
  diferença de escala do paste-back). É a explicação numérica do “rosto de plástico”.
- **Sincronia**: nos blocos centrais o pico fica entre **0 e ±3 frames** (≤ 100 ms), o que é
  aceitável para fala. Os extremos (`+6` em `seg_1`, `+13` em `seg_4`) aparecem onde a métrica
  se confunde com o movimento da cabeça/mão; o `seg_4` é um clipe de “pointing”, com bastante
  movimento global. A correlação baixa (0,2–0,4) mostra que a métrica é ruidosa por natureza —
  ela serve para **detectar desalinhamento grosseiro**, não para calibrar milissegundos.

Por construção, o alinhamento do Wav2Lip é exato: o frame `i` consome a janela de mel em
`i × 80/fps`, e o clipe de driving e o slice de áudio começam no mesmo instante (`seg.start`).
Não há offset acumulado entre blocos; o que existia era **perda de detalhe** na região da boca,
que o olho interpreta como falta de sincronia.

## O que ainda pode ser melhorado

1. **Métrica de boca com landmarks** (mediapipe/insightface) em vez de diferença de pixels —
   separaria abertura de lábio de movimento de cabeça e daria lag confiável também em pausas.
2. **Driving mais expressivo**: o Wav2Lip segue sendo o teto de forma de boca. Um modelo
   audio→expressão (JoyVASA, MuseTalk) como gerador de driving melhoraria as vogais, mantendo
   o LivePortrait como camada de pixels.
3. **Calibração fina** (`--driving-multiplier`, offset de ±1 frame) só faz sentido depois de (1).

---

## Protocolo de sincronia (o orçamento de erro)

Atraso não é um erro único; é a soma de cinco, cada um com tamanho em ms:

| Etapa | Contribuição | Natureza |
|---|---|---|
| Filtro temporal do LivePortrait | +133 ms (~4 quadros) | estrutural, compensável |
| Enquadramento de mel do Wav2Lip | +70 ms | estrutural, compensável |
| Compensação por corte de quadros (`--drive-shift-frames`) | −167 ms | compensa, mas quebra o movimento |
| Granularidade de 1 quadro | ±33 ms | quantização |
| Limite do plano fora da grade de 30 fps | ≤33 ms | geometria do plano |

Medido após `--drive-shift-frames 5`: **73 ms** de atraso residual (faixa "visível").
Meta prática: **|atraso| ≤ 33 ms** (1 quadro), que é o limiar de detecção (~40–45 ms).

### Por que o shift por quadros é o elo fraco

`-ss` descarta os primeiros N quadros do driving e `tpad=clone` repete o último N.
Efeitos colaterais:

- o primeiro fonema do bloco perde a forma da boca (movimento real jogado fora);
- o fim do bloco fica congelado por N/fps (167 ms = 19 % de um bloco de 0,86 s);
- a compensação só existe em múltiplos de 33 ms.

### O que substitui

Compensar **antes** do filtro, em milissegundos, com material real:

- renderizar o driving na janela `[t0 − 203 ms, t1]`, usando a mesma faixa de voz
  e o mesmo clipe-fonte (não um clone do último quadro);
- consumir o driving a partir de `t0`.

Assim não há quadro descartado nem congelado, e o atraso residual vai a ~0.

### Cinco regras de aceitação

1. Uma única faixa de áudio, fatiada em PCM. Nenhum reencode de AAC entre os cortes
   (cada corte adiciona ~21 ms de padding invisível).
2. Compensação em ms com janela real (acima). Nenhum quadro duplicado no fim do bloco.
3. Terminar a fala ~200 ms antes do corte: RMS < −50 dB nos últimos 150 ms do bloco.
4. Medir com envelope de energia **contra abertura de boca**, em trechos vozeados,
   por correlação cruzada no bloco inteiro. Onset isolado oscilou −120…+173 ms entre
   blocos vizinhos: é ruído do sensor, não do vídeo.
5. Só depois julgar a forma da boca — e aceitar que forma é o limite do hardware.

### O que continua fora de alcance

Timing se resolve por engenharia. **Visema** (lábios colados em "pá", abertos em "pé")
exige modelo maior; Wav2Lip em 6 GB entrega forma *plausível*, não *correta*.
