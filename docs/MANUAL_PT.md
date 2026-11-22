# Manual — boletim com avatar falante (PT-BR)

Este manual explica, sem jargão, **o que foi construído**, **como funciona** e **o que fazer**
quando alguma coisa sai errada. O vídeo de referência é renderizado pelo próprio pipeline
(18 s, vertical) e fica apenas na sua máquina — o repositório guarda só o programa.

---

## 1. O que é

Um boletim de notícias de IA em formato vertical (Shorts/Reels) com um apresentador virtual:

- ele aparece em tela cheia, em painel dividido com gráficos, e em cenas só de gráfico;
- a voz é um **clone local** da voz do apresentador (perfil `Ale-empolgado`);
- a boca é animada para acompanhar exatamente a fala;
- no fim, ele **para de falar e fecha a boca** — nada de ficar mexendo os lábios no vazio;
- legenda aparece palavra por palavra, dentro da área segura de Shorts;
- tudo roda no seu PC, sem pagar API.

---

## 2. Por que a primeira versão ficou ruim (e o que mudou)

A primeira versão usava um programa chamado **Wav2Lip** para animar a boca. Ele funciona, mas
tem um defeito de fábrica: ele trabalha a boca numa imagem **muito pequena (96 pixels)** e
depois estica para o tamanho do vídeo. Resultado:

- enquanto ele fala, o rosto fica **liso, sem poros, sem detalhe de barba** (“de plástico”);
- quando ele fica quieto, o rosto volta a ser nítido — porque esse trecho não passou pelo
  Wav2Lip;
- e a boca borrada dá a impressão de que **não está sincronizada**, mesmo com o tempo certo.

A correção foi separar as duas coisas:

| Quem faz | O que faz |
|---|---|
| **Wav2Lip** | só calcula **o movimento** da boca, quadro a quadro |
| **LivePortrait** | desenha essa boca **no vídeo original nítido**, preservando pele, barba, tatuagem |

É como usar um “esboço” para animar um desenho de alta qualidade: o esboço não aparece no
resultado. O comparativo é gerado na sua máquina pelo `audit_lipsync.py` + `ffmpeg`: em cima o resultado
novo, embaixo o antigo.

O **áudio não mudou** — a voz já estava boa. Mudou só quem desenha a boca.

---

## 3. Como o vídeo é montado, passo a passo

1. **Voz** — o texto de cada cena vai para o VoiceStudio (programa local de clonagem de voz),
   que devolve um WAV. Se ele estiver desligado, o sistema usa a voz Piper (mais robótica) para
   não travar o trabalho. Depois, a narração é limpa (sem música) e a trilha é mixada por baixo,
   baixando o volume quando alguém fala (*ducking*).
2. **Plano** — um arquivo, `project/artifacts/avatar_plan.json`, descreve quem aparece, onde e
   quando. Exemplo: “de 0 a 2,5 s, apresentador em tela cheia; de 2,5 a 6 s, painel dividido com
   gráfico”. Nada é decidido escondido dentro do HTML.
3. **Montagem** — o programa corta os clipes do apresentador, ajusta para 1080×1920 (tela cheia)
   ou 1080×864 (painel inferior) e coloca nos lugares certos da composição.
4. **Movimento da boca** — o Wav2Lip recebe o trecho do clipe + o trecho correspondente do áudio
   e gera um vídeo **mudo** com a boca se movendo. Cada trecho roda em um processo separado para
   liberar a memória da placa de vídeo.
5. **Boca em alta qualidade** — o LivePortrait pega o trecho **original nítido** e o vídeo do
   Wav2Lip como “referência de movimento”, e redesenha apenas a região dos lábios. O resto do
   rosto, as mãos e o cenário continuam sendo o material original.
6. **Fim do vídeo** — a última frase (“até amanhã!”) termina em 17,32 s. O trecho falado é
   cortado em 17,36 s e entra um “retrato neutro” (boca fechada, olhos abertos) até 18,00 s, com
   uma transição de 0,08 s. Isso é o que faz o vídeo terminar com naturalidade.
7. **Conferência** — antes de exportar, quatro verificações automáticas precisam passar
   (nenhum erro de composição, nenhum texto com contraste ruim, nenhum problema de layout,
   todos os quadros renderizados). Só então o MP4 final é gerado.

---

## 4. O que você pode ajustar

| Vontade | Como |
|---|---|
| Boca menos exagerada | `--driving-multiplier 0.85` no `avatar_liveportrait.py` |
| Trocar a voz | `--voice <perfil>` no `voice_craft_tts.py` |
| Mudar quando o avatar aparece | editar `avatar_plan.json` (start/end/mode) |
| Mais tempo no fim | mover `end` do bloco de fala e do hold, mantendo o hold |
| Sem zoom no fim | remover `zoom` do `seg_8_closed_hold` |

---

## 5. Problemas comuns

**“A boca voltou a ficar de plástico.”**
O trecho está usando o arquivo antigo do Wav2Lip. Rode o LivePortrait de novo para aquele
trecho (`--force --apply`) e renderize.

**“Ele continua falando depois do fim.”**
O trecho de fala está indo até o fim do vídeo. Corte no fim da locução e mantenha o “hold”
neutro — o Wav2Lip não fecha a boca sozinho no silêncio.

**“Apareceu um rosto fantasma na transição.”**
Duas imagens de takes diferentes foram misturadas. Use transição curta (até 0,12 s) ou corte
seco.

**“Deu erro de memória na placa de vídeo.”**
Feche outros programas que usam GPU ou descarregue o modelo do VoiceStudio. O sistema avisa e
mantém o clipe anterior em vez de gerar um vídeo quebrado.

---

## 6. Números da entrega

| Item | Valor |
|---|---|
| Resolução / fps | 1080×1920 / 30 |
| Duração | 18,000 s |
| Vídeo / áudio | h264 / AAC 48 kHz estéreo |
| Volume médio / pico | −17,4 dB / −1,3 dB |
| Custo | US$ 0,00 |
| Memória de pico | ≈ 3,0 GB (de 6,1 GB) |
| Blocos com boca animada | 5 (0–2,5 s · 2,5–6 s · 9,5–12 s · 14,5–16,5 s · 16,5–17,36 s) |
| Encerramento neutro | 17,36–18,00 s |
