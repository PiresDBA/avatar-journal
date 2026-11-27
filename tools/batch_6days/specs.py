"""Authoritative 6-day Shorts specification (verified provenance, PT-BR phonetics, 6 distinct visual styles)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SHORTS_6DAYS: list[dict[str, Any]] = [
    {
        "slug": "short_01_seg_ltx25",
        "day_key": "segunda",
        "day_short": "SEG",
        "db_id": 27,
        "program": "RADAR OPEN SOURCE · SEGUNDA",
        "hud_brand": "RADAR OPEN SOURCE · SEG",
        "title": "LTX-2.5: Vídeo e Áudio Sincronizados em 1 Modelo Aberto #Shorts",
        "topic_summary": "Lightricks/LTX-2.5 (13.546 likes, 3,04M downloads HF, DiT áudio+vídeo sincronizados)",
        "style": {
            "family": "optical-glass-refraction-3d",
            "lemo": "hologram-hud",
            "name": "Vidro Óptico & Refração 3D",
            "bg": "#060911",
            "accent": "#38BDF8",
            "accent2": "#F59E0B",
            "card_bg": "rgba(8, 14, 28, 0.88)",
            "pill_fg": "#060911",
            "hz1": 58.27,
            "hz2": 116.54,
        },
        "blocks": [
            ("seg_01_abertura", "Um modelo aberto com mais de três milhões de downloads tá gerando vídeo e som juntos de uma vez só!"),
            (
                "seg_02_bloco_a",
                "A Láit triks liberou o Éle Tê Xis dois ponto cinco no Râguing Fêice e no Guíti Râbi. "
                "Em vez de criar vídeo mudo para tentar encaixar efeito sonoro depois, essa arquitetura Difiújan Transfórmer gera imagem e áudio sincronizados na mesma passada.",
            ),
            (
                "seg_03_bloco_b",
                "Ele aceita texto, imagem de referência e até áudio para guiar a cena, rodando o código oficial em Linux, Windows e Mac. "
                "Só atenção a um detalhe: apesar dos pesos abertos, ele usa licença comunitária própria, não é licença Ême Í Tê irrestrita.",
            ),
            ("seg_04_fechamento", "O código e o modelo oficial estão na descrição. Qual cena você testaria nele hoje?"),
        ],
        "scenes": [
            {
                "lbl": "01 · GANCHO",
                "col": "#38BDF8",
                "kicker": "SEG · RADAR OPEN SOURCE",
                "headline": "Vídeo e Som Nascendo Juntos em 1 Passada",
                "sub": "Lightricks/LTX-2.5 · DiT Fundacional Áudio-Visual",
                "cards": [
                    {"lbl": "HUGGING FACE", "val": "3,04M Downloads", "tone": "accent"},
                    {"lbl": "ARQUITETURA", "val": "DiT Áudio + Vídeo", "tone": "light"},
                    {"lbl": "ACESSO", "val": "Pesos Abertos", "tone": "accent2"},
                ],
                "stage_mode": "waveform_optical",
            },
            {
                "lbl": "LTX-2.5 · DiT",
                "col": "#38BDF8",
                "kicker": "02 · SINCRONIA NATIVA · Lightricks/LTX-2",
                "headline": "Imagem e Áudio no Mesmo Fluxo DiT",
                "sub": "Sem dublagem ou foley colado por fora depois do render",
                "cards": [
                    {"lbl": "CURTIDAS HF", "val": "13.546 likes", "tone": "accent"},
                    {"lbl": "ENTRADAS", "val": "Texto · Img · Áudio", "tone": "light"},
                    {"lbl": "PIPELINES", "val": "Linux · Win · Mac", "tone": "accent2"},
                ],
                "stage_mode": "ltx_pipeline",
            },
            {
                "lbl": "LICENÇA & CÓDIGO",
                "col": "#F59E0B",
                "kicker": "03 · CHECAGEM DE PROCEDÊNCIA · github.com/Lightricks/LTX-2",
                "headline": "Pesos Abertos, Mas Licença Comunitária",
                "sub": "Não é MIT irrestrito: leia LTX-2.x Community License antes de escalar",
                "cards": [
                    {"lbl": "LICENÇA", "val": "LTX Community", "tone": "accent2"},
                    {"lbl": "BACKEND", "val": "natten / Triton", "tone": "light"},
                    {"lbl": "PAPER BASE", "val": "arXiv:2601.03233", "tone": "accent"},
                ],
                "stage_mode": "ltx_license",
            },
            {
                "lbl": "04 · RESUMO",
                "col": "#38BDF8",
                "kicker": "LINK OFICIAL NA DESCRIÇÃO",
                "headline": "Qual Cena Você Testaria no LTX-2.5?",
                "sub": "Modelo no Hugging Face + GitHub oficial verificados",
                "cards": [
                    {"lbl": "MODELO", "val": "LTX-2.5", "tone": "accent"},
                    {"lbl": "DOWNLOADS", "val": "3.041.405", "tone": "accent2"},
                ],
                "stage_mode": "closing_optical",
            },
        ],
        "captions": [
            [("Um modelo aberto com ", False), ("+3 milhões de downloads", True), (" gera vídeo e som juntos", False)],
            [
                ("A ", False), ("Lightricks", True), (" liberou o ", False), ("LTX-2.5", True), (" no Hugging Face e GitHub", False),
                ("Arquitetura ", False), ("DiT", True), (" gera imagem e áudio sincronizados de uma vez", False),
            ],
            [
                ("Aceita ", False), ("texto, imagem ou áudio", True), (" e roda em Linux, Windows e Mac", False),
                ("Atenção: usa ", False), ("licença comunitária própria", True), (", não é MIT livre", False),
            ],
            [("Código e modelo oficial na descrição. ", False), ("Qual cena você testaria?", True)],
        ],
        "youtube": {
            "title": "LTX-2.5: IA aberta que gera vídeo e áudio juntos (+3M downloads) #Shorts",
            "description": (
                "O Lightricks LTX-2.5 já soma mais de 3 milhões de downloads e 13,5 mil curtidas no Hugging Face "
                "trazendo geração conjunta de vídeo e áudio sincronizados em uma arquitetura Diffusion Transformer (DiT).\n\n"
                "Neste vídeo mostramos o que muda no pipeline oficial multi-plataforma e o cuidado essencial "
                "com a licença comunitária (LTX-2.x Community License) antes de usar comercialmente.\n\n"
                "Links oficiais verificados:\n"
                "- Modelo no Hugging Face: https://huggingface.co/Lightricks/LTX-2.5\n"
                "- Repositório oficial no GitHub: https://github.com/Lightricks/LTX-2\n"
                "- Paper base no arXiv: https://arxiv.org/abs/2601.03233\n"
                "- Site oficial: https://ltx.io\n\n"
                "#IA #InteligenciaArtificial #LTX25 #OpenSource #VideoIA #Shorts"
            ),
            "tags": ["IA", "LTX-2.5", "Lightricks", "Open Source", "Video IA", "Shorts"],
        },
        "official_links": [
            "https://huggingface.co/Lightricks/LTX-2.5",
            "https://github.com/Lightricks/LTX-2",
            "https://arxiv.org/abs/2601.03233",
            "https://ltx.io",
        ],
    },
    {
        "slug": "short_02_ter_visual_reasoning",
        "day_key": "terca",
        "day_short": "TER",
        "db_id": 33,
        "program": "RADAR DE PESQUISA · TERÇA",
        "hud_brand": "RADAR DE PESQUISA · TER",
        "title": "Estudo da Meta e Princeton: Pedir Para IA Desenhar Piorou o Raciocínio #Shorts",
        "topic_summary": "arXiv:2611.34935v1 (13 pares VLM+gerador: -3,7 p.p. média, -10,47 VSTAR, +3 ERQA)",
        "style": {
            "family": "blender-architectural-diorama",
            "lemo": "data-physical",
            "name": "Diorama Científico Porcelana & Cobre",
            "bg": "#14161D",
            "accent": "#F59E0B",
            "accent2": "#EF4444",
            "accent3": "#10B981",
            "card_bg": "rgba(22, 25, 34, 0.90)",
            "pill_fg": "#111318",
            "hz1": 65.41,
            "hz2": 130.81,
        },
        "blocks": [
            ("seg_01_abertura", "Pedir para a IA gerar uma imagem de rascunho antes de responder parece genial, mas um novo estudo mostrou o oposto."),
            (
                "seg_02_bloco_a",
                "Pesquisadores de Princeton e da Meta publicaram agora no ar-káiv um teste com treze pares de modelos de visão e geradores de imagem. "
                "A ideia era testar se pensar em imagens ajuda o raciocínio, mas a média caiu três vírgula sete pontos percentuais em nove de dez tarefas.",
            ),
            (
                "seg_03_bloco_b",
                "No benchmark Vê-Star, a queda foi de dez vírgula quarenta e sete pontos, e modelos unificados como Béigol e Jânus Pró também perderam desempenho. "
                "A única exceção citada foi o Ê Érre Quê Á, subindo três pontos após dez edições seguidas.",
            ),
            ("seg_04_fechamento", "O link desse preprint tá na descrição. Você já usou rascunho visual com modelos de visão?"),
        ],
        "scenes": [
            {
                "lbl": "01 · GANCHO",
                "col": "#F59E0B",
                "kicker": "TER · RADAR DE PESQUISA · arXiv:2611.34935",
                "headline": "Gerar Imagem Ajudou a IA a Pensar?",
                "sub": "Preprint 25/11/2026 · Princeton University & Meta AI",
                "cards": [
                    {"lbl": "PARES TESTADOS", "val": "13 VLM+Gen", "tone": "accent"},
                    {"lbl": "TAREFAS EM QUEDA", "val": "9 de 10", "tone": "accent2"},
                    {"lbl": "IMPACTO MÉDIO", "val": "-3,7 p.p.", "tone": "accent2"},
                ],
                "stage_mode": "sci_intro",
            },
            {
                "lbl": "IMPACTO NOS DADOS",
                "col": "#EF4444",
                "kicker": "02 · RESULTADOS EMPÍRICOS · 13 PARES AVALIADOS",
                "headline": "Rascunho Gerado Derrubou a Acurácia",
                "sub": "Diferente de pensar em texto, pixels gerados introduzem ruído no VLM",
                "cards": [
                    {"lbl": "MÉDIA GERAL", "val": "-3,7 p.p.", "tone": "accent2"},
                    {"lbl": "VSTAR", "val": "-10,47 pts", "tone": "accent2"},
                    {"lbl": "BAGEL / JANUS", "val": "-8 de 10", "tone": "light"},
                ],
                "stage_mode": "sci_bars",
            },
            {
                "lbl": "EXCEÇÃO ERQA",
                "col": "#10B981",
                "kicker": "03 · ONDE HOUVE GANHO vs. ONDE FALHOU",
                "headline": "Só Melhorou Após 10 Edições no ERQA",
                "sub": "ChartQAPro e MathVista continuaram abaixo da base sem geração",
                "cards": [
                    {"lbl": "ERQA (10 ED.)", "val": "+3,0 pts", "tone": "accent3"},
                    {"lbl": "CHARTQAPRO", "val": "Abaixo Base", "tone": "accent2"},
                    {"lbl": "ESTÁGIO", "val": "Preprint Nov/26", "tone": "accent"},
                ],
                "stage_mode": "sci_compare",
            },
            {
                "lbl": "04 · RESUMO",
                "col": "#F59E0B",
                "kicker": "PREPRINT OFICIAL NA DESCRIÇÃO",
                "headline": "Pensar em Imagens Ainda Precisa Alinhamento",
                "sub": "Menos distração visual, mais precisão em benchmarks espaciais",
                "cards": [
                    {"lbl": "ARXIV ID", "val": "2611.34935v1", "tone": "accent"},
                    {"lbl": "VEREDICTO", "val": "-3,7 p.p.", "tone": "accent2"},
                ],
                "stage_mode": "closing_sci",
            },
        ],
        "captions": [
            [("Pedir para a IA ", False), ("desenhar antes de pensar", True), (" piorou o raciocínio visual", False)],
            [
                ("Estudo de ", False), ("Princeton e Meta", True), (" testou 13 pares de VLM + gerador", False),
                ("Acurácia média caiu ", False), ("3,7 pontos percentuais", True), (" em 9 de 10 tarefas", False),
            ],
            [
                ("No ", False), ("VSTAR caiu 10,47 pts", True), ("; BAGEL e Janus-Pro caíram em 8 tarefas", False),
                ("Exceção: ", False), ("ERQA ganhou +3 pts", True), (" após 10 edições iterativas", False),
            ],
            [("Link do estudo original no arXiv na descrição. ", False), ("Já testou isso?", True)],
        ],
        "youtube": {
            "title": "Estudo da Meta e Princeton: gerar imagem de apoio PIOROU o raciocínio da IA #Shorts",
            "description": (
                "Será que modelos multimodais acertam mais quando geram uma imagem auxiliar antes de responder? "
                "Um novo estudo empírico (preprint de 25/11/2026 no arXiv) com pesquisadores de Princeton e da Meta AI "
                "avaliou 13 combinações de VLM + gerador de imagens e encontrou queda média de 3,7 pontos percentuais "
                "(piora em 9 de 10 tarefas, incluindo -10,47 no VSTAR; exceção no ERQA com +3 pontos após 10 edições).\n\n"
                "Link oficial verificado:\n"
                "- Artigo original no arXiv: https://arxiv.org/abs/2611.34935\n\n"
                "#IA #PesquisaIA #MetaAI #Princeton #Multimodal #arXiv #Shorts"
            ),
            "tags": ["IA", "arXiv", "Meta AI", "Princeton", "Multimodal", "Raciocinio Visual", "Shorts"],
        },
        "official_links": ["https://arxiv.org/abs/2611.34935"],
    },
    {
        "slug": "short_03_qua_batalha_local",
        "day_key": "quarta",
        "day_short": "QUA",
        "db_id": 28,
        "program": "BATALHA DE IAS · QUARTA",
        "hud_brand": "BATALHA DE IAS · QUA",
        "title": "Batalha Local 27B: Ternary-Bonsai 1,76-bit (5,93 GB) vs Inkling-2-Mini MoE #Shorts",
        "topic_summary": "Ternary-Bonsai 2.5 27B (1,76-bit, 5,93 GB, Apache-2.0) vs Inkling-2-Mini (24 camadas MoE looped, ~20 GB)",
        "style": {
            "family": "glsl-shader-kinetic-3d-reel",
            "lemo": "dataviz",
            "name": "Arena Split GLSL & Titânio",
            "bg": "#050814",
            "accent": "#10B981",
            "accent2": "#6366F1",
            "card_bg": "rgba(9, 13, 28, 0.90)",
            "pill_fg": "#050814",
            "hz1": 73.42,
            "hz2": 146.83,
        },
        "blocks": [
            ("seg_01_abertura", "Como espremer vinte e sete bilhões de parâmetros em casa? Duas receitas opostas acabaram de explodir!"),
            (
                "seg_02_bloco_a",
                "De um lado, o Têrneri Bónsai dois ponto cinco da Prízm Ême Éle. Ele comprime vinte e sete bilhões de parâmetros para um ponto sete seis bits, "
                "caindo para cinco vírgula nove três gigabytes, mantendo setenta e sete ponto dois, contra setenta e sete ponto sete, do modelo completo em ferramentas.",
            ),
            (
                "seg_03_bloco_b",
                "Do outro lado, o Ínkling dois Míni da Fínking Machínes aposta em vinte e quatro camadas M ó É multimodais, onde as doze do meio rodam três vezes em loop, "
                "em vinte gigas nativos ou dezesseis vírgula seis no Gê Gê Ú Éfe da Ãnslóf.",
            ),
            ("seg_04_fechamento", "Ambos são Apátche dois ponto zero e todos os links estão na descrição. Qual você rodaria no seu Pê Cê?"),
        ],
        "scenes": [
            {
                "lbl": "01 · GANCHO",
                "col": "#10B981",
                "kicker": "QUA · BATALHA DE IAS LOCAIS",
                "headline": "Bonsai 1,76-bit vs. Inkling MoE Looped",
                "sub": "2 modelos abertos Apache-2.0 na faixa ~26B–27B rodando local",
                "cards": [
                    {"lbl": "BONSAI 2.5", "val": "5,93 GB", "tone": "accent"},
                    {"lbl": "INKLING 2 MINI", "val": "~20 GB / Loop", "tone": "accent2"},
                    {"lbl": "LICENÇA", "val": "Apache-2.0", "tone": "light"},
                ],
                "stage_mode": "battle_intro",
            },
            {
                "lbl": "TERNARY-BONSAI",
                "col": "#10B981",
                "kicker": "02 · LADO A · prism-ml/Ternary-Bonsai-2.5-27B",
                "headline": "27B Espremido em Apenas 5,93 GB",
                "sub": "1,76 bit/peso sobre Qwen3.8-27B rodando no llama.cpp (Q2_0)",
                "cards": [
                    {"lbl": "PESO DISCO", "val": "5,93 GB (-9x)", "tone": "accent"},
                    {"lbl": "TOOL CALLING", "val": "77,2 vs 77,7", "tone": "light"},
                    {"lbl": "SWE-BENCH", "val": "75,6 pts", "tone": "accent"},
                ],
                "stage_mode": "battle_bonsai",
            },
            {
                "lbl": "INKLING-2-MINI",
                "col": "#6366F1",
                "kicker": "03 · LADO B · thinkingmachines/Inkling-2-Mini",
                "headline": "MoE Multimodal que Repete Camadas 3x",
                "sub": "24 camadas -> 48 passagens por token (Texto + Visão, 2,44M GGUF)",
                "cards": [
                    {"lbl": "NATIVO MIX", "val": "~20 GB", "tone": "accent2"},
                    {"lbl": "UNSLOTH Q4_K_M", "val": "16,61 GB (97,9%)", "tone": "light"},
                    {"lbl": "MODALIDADE", "val": "Texto + Imagem", "tone": "accent"},
                ],
                "stage_mode": "battle_inkling",
            },
            {
                "lbl": "04 · VEREDITO",
                "col": "#10B981",
                "kicker": "LINKS OFICIAIS NA DESCRIÇÃO",
                "headline": "Pouca VRAM? Bonsai. Visão 32GB? Inkling.",
                "sub": "Dois caminhos reais de eficiência além da força bruta",
                "cards": [
                    {"lbl": "BONSAI 2.5", "val": "5,93 GB", "tone": "accent"},
                    {"lbl": "INKLING MINI", "val": "MoE 3x Loop", "tone": "accent2"},
                ],
                "stage_mode": "closing_battle",
            },
        ],
        "captions": [
            [("Como rodar ", False), ("~27B parâmetros em casa?", True), (" Duas receitas opostas", False)],
            [
                ("Ternary-Bonsai 2.5", True), (": 1,76-bit cai de 53,8 GB para ", False), ("5,93 GB", True),
                ("Mantém ", False), ("77,2 vs 77,7", True), (" (FP16) em benchmarks de tool-calling", False),
            ],
            [
                ("Inkling-2-Mini", True), (": MoE de 24 camadas onde 12 rodam ", False), ("3x em loop", True),
                ("Checkpoint ~20 GB nativo ou ", False), ("16,61 GB", True), (" em GGUF Q4_K_M Unsloth", False),
            ],
            [("Ambos ", False), ("Apache-2.0", True), (" com links na descrição. Qual você rodaria?", False)],
        ],
        "youtube": {
            "title": "Batalha Local 27B: Ternary-Bonsai (5,93 GB) vs Inkling-2-Mini MoE (Apache-2.0) #Shorts",
            "description": (
                "Duas arquiteturas abertas (ambas Apache-2.0) mostrando caminhos diferentes para rodar modelos da faixa ~26B–27B fora da nuvem:\n"
                "- Ternary Bonsai 2.5 27B (PrismML): 1,76 bit/peso, 5,93 GB em disco (~9x menor que 53,8 GB FP16), 77,2 vs 77,7 em tool-calling.\n"
                "- Inkling 2 Mini (Thinking Machines Lab): MoE multimodal (texto + imagem) com 24 camadas onde 12 repetem 3x (48 passagens/token), ~20 GB nativo e 16,61 GB no GGUF Q4_K_M da Unsloth.\n\n"
                "Links oficiais verificados:\n"
                "- Ternary Bonsai 2.5 27B (HF): https://huggingface.co/prism-ml/Ternary-Bonsai-2.5-27B-GGUF\n"
                "- PrismML Site & Demo GitHub: https://prismml.com | https://github.com/PrismML-Eng/Bonsai-demo\n"
                "- Inkling 2 Mini (HF): https://huggingface.co/thinkingmachines/Inkling-2-Mini\n"
                "- Inkling 2 Mini GGUF (Unsloth): https://huggingface.co/unsloth/Inkling-2-Mini-GGUF\n"
                "- Thinking Machines Cookbook: https://github.com/thinking-machines-lab/tinker-cookbook\n\n"
                "#IA #LLM #LlamaCpp #Bonsai #Inkling #Quantizacao #OpenSource #Shorts"
            ),
            "tags": ["IA", "LLM Local", "Ternary-Bonsai", "Inkling-2-Mini", "Unsloth", "GGUF", "Shorts"],
        },
        "official_links": [
            "https://huggingface.co/prism-ml/Ternary-Bonsai-2.5-27B-GGUF",
            "https://prismml.com",
            "https://github.com/PrismML-Eng/Bonsai-demo",
            "https://huggingface.co/thinkingmachines/Inkling-2-Mini",
            "https://huggingface.co/unsloth/Inkling-2-Mini-GGUF",
        ],
    },
    {
        "slug": "short_04_sex_anthropic_scion",
        "day_key": "sexta",
        "day_short": "SEX",
        "db_id": 45,
        "program": "HISTÓRIAS & MENTES · SEXTA",
        "hud_brand": "HISTÓRIAS & MENTES · SEX",
        "title": "Quando Agentes Quebraram o Git: Por Que a Anthropic Criou o Scion #Shorts",
        "topic_summary": "Anthropic Redesigning Source Control (2.500 -> >30.000 merges/dia, 100GB main, Scion em 5 meses)",
        "style": {
            "family": "archive-lighttable",
            "lemo": "warm-tungsten",
            "name": "Mesa de Luz & Tungstênio Editorial",
            "bg": "#11100E",
            "accent": "#F59E0B",
            "accent2": "#F5EFE6",
            "card_bg": "rgba(24, 21, 17, 0.90)",
            "pill_fg": "#11100E",
            "hz1": 55.0,
            "hz2": 82.41,
        },
        "blocks": [
            ("seg_01_abertura", "Um problema raro bateu na Antrópik: os agentes escreveram código rápido demais e o Guít não deu conta."),
            (
                "seg_02_bloco_a",
                "Nos bastidores publicados pela empresa, entre maio e setembro de dois mil e vinte e seis, os merges diários saltaram de dois mil e quinhentos para mais de trinta mil por dia. "
                "Só a história do branch principal encostou em cem gigas, com vinte e cinco milhões de tchéck áuts diários.",
            ),
            (
                "seg_03_bloco_b",
                "Em cinco meses eles criaram o Sáion, um controle de versão no servidor feito para máquinas sempre online, usando o próprio Claude no desenvolvimento. "
                "Depois do debate de engenheiros citando o sistema Mononóke da Meta, a Antrópik atualizou as referências.",
            ),
            ("seg_04_fechamento", "Os dois artigos oficiais da Antrópik estão na descrição. Seu time já sentiu esse gargalo com I Á?"),
        ],
        "scenes": [
            {
                "lbl": "01 · GANCHO",
                "col": "#F59E0B",
                "kicker": "SEX · HISTÓRIAS & MENTES · ANTHROPIC ENG.",
                "headline": "Quando Agentes Quebram Ferramentas Humanas",
                "sub": "Publicado Out/2026 · Monorepo de IA acima da escala do Git",
                "cards": [
                    {"lbl": "MAI -> SET/26", "val": "2,5k -> 30k+/dia", "tone": "accent"},
                    {"lbl": "HISTÓRICO MAIN", "val": "~100 GB", "tone": "light"},
                    {"lbl": "CHECKOUTS CI", "val": "25M / dia", "tone": "accent2"},
                ],
                "stage_mode": "archive_intro",
            },
            {
                "lbl": "ESCALA EXTREMA",
                "col": "#F59E0B",
                "kicker": "02 · O GARGALO · anthropic.com/engineering",
                "headline": "12x Mais Merges em Apenas Quatro Meses",
                "sub": "Sem otimizações, 25M de checkouts exigiriam >600 PB/dia em Git",
                "cards": [
                    {"lbl": "MERGES/DIA", "val": "30.000+", "tone": "accent"},
                    {"lbl": "CÓPIA COMPACT.", "val": ">25 GB", "tone": "light"},
                    {"lbl": "MIGRAÇÃO", "val": "5 Meses", "tone": "accent2"},
                ],
                "stage_mode": "archive_curve",
            },
            {
                "lbl": "SCION & DEBATE",
                "col": "#FB923C",
                "kicker": "03 · BASTIDORES · Scion + Antique + Caso C Compiler",
                "headline": "Scion no Servidor & Crítica no Hacker News",
                "sub": "Git segue ideal para humanos; debate com Mononoke gerou créditos extras",
                "cards": [
                    {"lbl": "NOVO VCS", "val": "Scion (Server)", "tone": "accent"},
                    {"lbl": "REVISÃO", "val": "Antique", "tone": "light"},
                    {"lbl": "PARALELO 02/26", "val": "16 Claudes C/Rust", "tone": "accent2"},
                ],
                "stage_mode": "archive_debate",
            },
            {
                "lbl": "04 · FECHO",
                "col": "#F59E0B",
                "kicker": "ARTIGOS OFICIAIS NA DESCRIÇÃO",
                "headline": "Qual Gargalo Quebra Primeiro Quando IA Escala?",
                "sub": "Não falta código — o novo gargalo é revisão, build e confiança",
                "cards": [
                    {"lbl": "SISTEMA", "val": "Anthropic Scion", "tone": "accent"},
                    {"lbl": "ESCALA", "val": "30k+ merges/dia", "tone": "light"},
                ],
                "stage_mode": "closing_archive",
            },
        ],
        "captions": [
            [("Na ", False), ("Anthropic", True), (", agentes escreveram tanto código que o Git não deu conta", False)],
            [
                ("De ", False), ("2.500 para 30.000+ merges/dia", True), (" entre maio e setembro de 2026", False),
                ("Histórico main chegou a ", False), ("~100 GB", True), (" com 25 milhões de checkouts/dia", False),
            ],
            [
                ("Em 5 meses criaram o ", False), ("Scion", True), (" centralizado no servidor para agentes", False),
                ("Debate sobre ", False), ("Mononoke (Meta)", True), (" levou a Anthropic a atualizar créditos", False),
            ],
            [("Os dois artigos oficiais estão na descrição. ", False), ("Já sentiu esse gargalo?", True)],
        ],
        "youtube": {
            "title": "Quando a IA escreveu código demais e a Anthropic precisou trocar o Git pelo Scion #Shorts",
            "description": (
                "Bastidores reais da Anthropic Engineering (outubro/2026): quando agentes autônomos elevaram as integrações diárias "
                "de ~2.500 para mais de 30.000 por dia (~100 GB só no branch main e 25M checkouts/dia em CI), "
                "a empresa criou o Scion e o revisor Antique para migrar seu monorepo do Git em 5 meses.\n\n"
                "Links oficiais verificados:\n"
                "- Redesigning source control at Anthropic: https://www.anthropic.com/engineering/redesigning-source-control\n"
                "- Building a C compiler with parallel Claudes: https://www.anthropic.com/engineering/building-c-compiler\n\n"
                "#Anthropic #Claude #Git #Scion #EngenhariaDeSoftware #IA #Shorts"
            ),
            "tags": ["Anthropic", "Scion", "Git", "Claude Code", "Engenharia de Software", "IA", "Shorts"],
        },
        "official_links": [
            "https://www.anthropic.com/engineering/redesigning-source-control",
            "https://www.anthropic.com/engineering/building-c-compiler",
        ],
    },
    {
        "slug": "short_05_sab_lado_b_mcp",
        "day_key": "sabado",
        "day_short": "SÁB",
        "db_id": 46,
        "program": "O LADO B DA IA · SÁBADO",
        "hud_brand": "O LADO B DA IA · SÁB",
        "title": "Falhas Reais em Servidores MCP Furaram Modo Somente Leitura (CVSS 8.2) #Shorts",
        "topic_summary": "CVE-2026-130008 (sqlite-mcp CVSS 8.2, v0.1.2) e CVE-2026-45609 (mcp-security SSRF CVSS 7.2, v0.1.9)",
        "style": {
            "family": "curated-hybrid-mix",
            "lemo": "circuit-board",
            "name": "Circuito Perfurado Âmbar & Obsidiana",
            "bg": "#070709",
            "accent": "#F59E0B",
            "accent2": "#EF4444",
            "accent3": "#22C55E",
            "card_bg": "rgba(14, 14, 18, 0.92)",
            "pill_fg": "#070709",
            "hz1": 49.0,
            "hz2": 98.0,
        },
        "blocks": [
            ("seg_01_abertura", "Você confia quando um plugin de agente diz que está em modo somente leitura? Duas falhas reais no Ême Cê Pê acenderam o alerta."),
            (
                "seg_02_bloco_a",
                "Nos boletins oficiais do Guíti Râbi Security, a Cê Vê É treze mil e oito, nota oito ponto dois, atingiu o servidor ésse quê éle lite ême cê pê. "
                "Ele só checava se a consulta começava com seléct, permitindo encadear um ponto e vírgula ou injetar comando para gravar em bancos protegidos.",
            ),
            (
                "seg_03_bloco_b",
                "Já na falha quarenta e cinco seiscentos e nove do Spríng Êi Ái ême cê pê security, nota sete vírgula dois, links de login sem validação abriam brecha Ésse Ésse Érre Éfe na rede interna. "
                "Ambas já têm correção: atualize e nunca dê permissão aberta só confiando no rótulo.",
            ),
            ("seg_04_fechamento", "Os dois avisos oficiais estão na descrição. Você audita as permissões dos seus plugins Ême Cê Pê?"),
        ],
        "scenes": [
            {
                "lbl": "01 · ALERTA MCP",
                "col": "#EF4444",
                "kicker": "SÁB · O LADO B DA IA · GITHUB ADVISORIES",
                "headline": "Modo 'Somente Leitura' Furado por 1 Ponto e Vírgula",
                "sub": "2 CVEs reais de severidade High já documentados e corrigidos em 2026",
                "cards": [
                    {"lbl": "CVE-2026-130008", "val": "CVSS 8.2 HIGH", "tone": "accent2"},
                    {"lbl": "CVE-2026-45609", "val": "CVSS 7.2 HIGH", "tone": "accent"},
                    {"lbl": "STATUS PATCH", "val": "v0.1.2 / v0.1.9", "tone": "accent3"},
                ],
                "stage_mode": "sec_intro",
            },
            {
                "lbl": "BYPASS SQLITE",
                "col": "#EF4444",
                "kicker": "02 · GHSA-q433-mp6c-8v4f · StacklokLabs/sqlite-mcp",
                "headline": "SELECT 1; ATTACH DATABASE Burlou Read-Only",
                "sub": "Driver rodava múltiplos comandos após ';' + SQL injection em describe_table",
                "cards": [
                    {"lbl": "SEVERIDADE", "val": "8.2 High", "tone": "accent2"},
                    {"lbl": "VETOR", "val": "ATTACH DATABASE", "tone": "accent"},
                    {"lbl": "CORREÇÃO", "val": "Patch >= 0.1.2", "tone": "accent3"},
                ],
                "stage_mode": "sec_sqlite",
            },
            {
                "lbl": "SSRF & DEFESA",
                "col": "#22C55E",
                "kicker": "03 · GHSA-qjp4-4jvr-xqg3 · Blindagem Prática",
                "headline": "SSRF no Fluxo OAuth DCR + 3 Regras de Defesa",
                "sub": "spring-ai-community/mcp-security < 0.1.9 aceitava URL interna sem filtro",
                "cards": [
                    {"lbl": "SPRING AI", "val": "v0.1.9 Fix", "tone": "accent3"},
                    {"lbl": "REGRA 1", "val": "Menor Privilégio", "tone": "accent"},
                    {"lbl": "REGRA 2", "val": "Aprovação Humana", "tone": "light"},
                ],
                "stage_mode": "sec_shield",
            },
            {
                "lbl": "04 · CHECKLIST",
                "col": "#F59E0B",
                "kicker": "BOLETINS OFICIAIS NA DESCRIÇÃO",
                "headline": "Atualize Plugins MCP e Isole Acessos Locais",
                "sub": "Rótulo 'read-only' sem sandbox real no SO não protege seus dados",
                "cards": [
                    {"lbl": "SQLITE-MCP", "val": "Atualizar 0.1.2+", "tone": "accent3"},
                    {"lbl": "MCP-SECURITY", "val": "Atualizar 0.1.9+", "tone": "accent3"},
                ],
                "stage_mode": "closing_sec",
            },
        ],
        "captions": [
            [("Plugin MCP em ", False), ("modo somente leitura", True), (" pode ser burlado sem sandbox", False)],
            [
                ("CVE-2026-130008 (CVSS 8.2)", True), (": sqlite-mcp só checava se começava com SELECT", False),
                ("Com ", False), ("';' ou describe_table", True), (", executava ATTACH e gravava no banco", False),
            ],
            [
                ("CVE-2026-45609 (CVSS 7.2)", True), (": SSRF na descoberta OAuth DCR do Spring AI", False),
                ("Ambos têm ", False), ("patch oficial (0.1.2 e 0.1.9)", True), (": atualize e isole acessos", False),
            ],
            [("Os dois boletins oficiais estão na descrição. ", False), ("Você revisa seus MCPs?", True)],
        ],
        "youtube": {
            "title": "O perigo oculto em plugins MCP: 2 falhas reais furaram o 'somente leitura' #Shorts",
            "description": (
                "O Lado B da IA: analisamos duas vulnerabilidades reais de severidade alta documentadas nos boletins do GitHub Security "
                "(já corrigidas em versão nova):\n"
                "- CVE-2026-130008 (CVSS 8.2 High, StacklokLabs/sqlite-mcp < 0.1.2): statement chaining após SELECT e SQL injection em describe_table furavam o read-only.\n"
                "- CVE-2026-45609 (CVSS 7.2 High, spring-ai-community/mcp-security < 0.1.9): SSRF por URL não validada em OAuth DCR.\n\n"
                "Links oficiais verificados:\n"
                "- GitHub Advisory CVE-2026-130008: https://github.com/advisories/GHSA-q433-mp6c-8v4f\n"
                "- NVD CVE-2026-130008: https://nvd.nist.gov/vuln/detail/CVE-2026-130008\n"
                "- Repositório sqlite-mcp: https://github.com/StacklokLabs/sqlite-mcp\n"
                "- GitHub Advisory CVE-2026-45609: https://github.com/advisories/GHSA-qjp4-4jvr-xqg3\n"
                "- Repositório mcp-security: https://github.com/spring-ai-community/mcp-security\n\n"
                "#SegurancaIA #MCP #CyberSecurity #CVE #AgentesIA #Shorts"
            ),
            "tags": ["MCP", "Seguranca IA", "CVE-2026-130008", "CyberSecurity", "Agentes IA", "Shorts"],
        },
        "official_links": [
            "https://github.com/advisories/GHSA-q433-mp6c-8v4f",
            "https://nvd.nist.gov/vuln/detail/CVE-2026-130008",
            "https://github.com/StacklokLabs/sqlite-mcp",
            "https://github.com/advisories/GHSA-qjp4-4jvr-xqg3",
            "https://github.com/spring-ai-community/mcp-security",
        ],
    },
    {
        "slug": "short_06_dom_world_models",
        "day_key": "domingo",
        "day_short": "DOM",
        "db_id": 47,
        "program": "VISÃO DO FUTURO · DOMINGO",
        "hud_brand": "VISÃO DO FUTURO · DOM",
        "title": "Depois dos Chats: Modelos de Mundo Que Entendem Física, 3D e Risco Real #Shorts",
        "topic_summary": "World Models (arXiv:2609.16697 Plausible->Controllable->Actionable) + MEMO (2611.34939) + Security (2607.28226)",
        "style": {
            "family": "curated-hybrid-mix",
            "lemo": "blueprint",
            "name": "Horizonte Blueprint -> Malha 3D",
            "bg": "#0B132B",
            "accent": "#38BDF8",
            "accent2": "#FBBF24",
            "accent3": "#FB7185",
            "card_bg": "rgba(11, 19, 43, 0.90)",
            "pill_fg": "#0B132B",
            "hz1": 61.74,
            "hz2": 123.47,
        },
        "blocks": [
            ("seg_01_abertura", "Depois da corrida por chats e vídeos, para onde a pesquisa de Inteligência Artificial está convergindo agora?"),
            (
                "seg_02_bloco_a",
                "Três estudos recentes mostram a virada para os Modelos de Mundo no espaço físico. "
                "Um novo levantamento propõe ir além de vídeo bonito, cobrando três degraus: plausível na física, controlável por ação e acionável na prática.",
            ),
            (
                "seg_03_bloco_b",
                "Já o sistema Mêmo, publicado em vinte e cinco de novembro, extrai malhas três D dinâmicas quadro a quadro em cenas velozes, testado inclusive em cenários do Blênder. "
                "Só que um terceiro artigo alerta: sensores enganados podem gerar ilusões preditivas de segurança.",
            ),
            ("seg_04_fechamento", "Os três artigos no ar-káiv e a página do Mêmo estão na descrição. Em qual setor isso chega primeiro?"),
        ],
        "scenes": [
            {
                "lbl": "01 · CONVERGÊNCIA",
                "col": "#38BDF8",
                "kicker": "DOM · VISÃO DO FUTURO · 3 ARTIGOS CONVERGENTES",
                "headline": "Da IA de Texto Para a IA Que Simula Física 3D",
                "sub": "World Models + Malhas Dinâmicas + Segurança no Mundo Físico",
                "cards": [
                    {"lbl": "ARXIV 2609", "val": "3 Níveis Ação", "tone": "accent"},
                    {"lbl": "MEMO 25/11", "val": "Malha 3D / Frame", "tone": "accent2"},
                    {"lbl": "RISCO 2607", "val": "Ilusão Segura", "tone": "accent3"},
                ],
                "stage_mode": "world_intro",
            },
            {
                "lbl": "3 DEGRAUS",
                "col": "#FBBF24",
                "kicker": "02 · CAPABILITY LADDER · arXiv:2609.16697",
                "headline": "Não Basta Vídeo Bonito: Tem Que Prever Ação",
                "sub": "Matriz 3x4 cruza geometria, física e ação para navegação e robótica",
                "cards": [
                    {"lbl": "NÍVEL 1", "val": "Plausible", "tone": "light"},
                    {"lbl": "NÍVEL 2", "val": "Controllable", "tone": "accent"},
                    {"lbl": "NÍVEL 3", "val": "Actionable", "tone": "accent2"},
                ],
                "stage_mode": "world_ladder",
            },
            {
                "lbl": "MEMO & RISCO",
                "col": "#FB7185",
                "kicker": "03 · arXiv:2611.34939 (MEMO) & arXiv:2607.28226",
                "headline": "Malha Dinâmica em Movimento vs. Ilusão Preditiva",
                "sub": "MEMO supera grade fixa (Blender-Moments); Security mapeia ataque físico",
                "cards": [
                    {"lbl": "MEMO 4D", "val": "Gaussian -> Mesh", "tone": "accent"},
                    {"lbl": "BENCHMARK", "val": "Blender-Moments", "tone": "accent2"},
                    {"lbl": "ALERTA", "val": "Safety Illusion", "tone": "accent3"},
                ],
                "stage_mode": "world_memo",
            },
            {
                "lbl": "04 · FUTURO",
                "col": "#38BDF8",
                "kicker": "ARTIGOS OFICIAIS NA DESCRIÇÃO",
                "headline": "Onde os Modelos de Mundo Entram Primeiro?",
                "sub": "Fábricas, veículos autônomos, simulações 3D ou assistência robótica",
                "cards": [
                    {"lbl": "ESCALA", "val": "Actionable 3D", "tone": "accent"},
                    {"lbl": "BASE", "val": "3 Papers arXiv", "tone": "accent2"},
                ],
                "stage_mode": "closing_world",
            },
        ],
        "captions": [
            [("Depois dos chats, a IA agora converge para ", False), ("Modelos de Mundo físicos", True)],
            [
                ("Survey ", False), ("arXiv:2609.16697", True), (" propõe 3 degraus além de vídeo bonito:", False),
                ("Plausible", True), (" na física, ", False), ("Controllable", True), (" por intervenção e ", False), ("Actionable", True),
            ],
            [
                ("MEMO (25/11)", True), (" extrai malha 3D real em cada quadro (testado no Blender)", False),
                ("Mas ", False), ("arXiv:2607.28226", True), (" alerta: sensor enganado gera ", False), ("ilusão de segurança", True),
            ],
            [("Os 3 links no arXiv + MEMO estão na descrição. ", False), ("Onde isso chega primeiro?", True)],
        ],
        "youtube": {
            "title": "A nova fronteira depois dos chats: Modelos de Mundo que entendem física 3D #Shorts",
            "description": (
                "Visão do Futuro: conectamos três trabalhos científicos que explicam a passagem dos chatbots para Modelos de Mundo no espaço físico:\n"
                "- Escada Plausible -> Controllable -> Actionable na robótica (arXiv:2609.16697)\n"
                "- MEMO: extração de malhas 3D dinâmicas quadro a quadro de cenas em movimento (arXiv:2611.34939, 25/11/2026)\n"
                "- Segurança física e o risco de 'ilusões preditivas de segurança' (arXiv:2607.28226)\n\n"
                "Links oficiais verificados:\n"
                "- Survey World Models: https://arxiv.org/abs/2609.16697\n"
                "- Paper MEMO (arXiv): https://arxiv.org/abs/2611.34939\n"
                "- Página oficial MEMO: https://memo-4d.github.io\n"
                "- Security of World-Model-Based Embodied AI: https://arxiv.org/abs/2607.28226\n\n"
                "#WorldModels #Robotica #IA #EmbodiedAI #3D #VisaoDoFuturo #Shorts"
            ),
            "tags": ["World Models", "Embodied AI", "Robotica", "MEMO", "arXiv", "IA", "Shorts"],
        },
        "official_links": [
            "https://arxiv.org/abs/2609.16697",
            "https://arxiv.org/abs/2611.34939",
            "https://memo-4d.github.io",
            "https://arxiv.org/abs/2607.28226",
        ],
    },
]
