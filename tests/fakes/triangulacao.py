# -*- coding: utf-8 -*-
"""Dossiê sintético de teste (3 fontes sobre o mesmo programa) com extrações e alinhamento gravados.

- f1 e f2 são independentes e divergem: estimativa de custo (R$ 12 bilhões x R$ 15 bilhões) e posição sobre o
  risco fiscal (saldo positivo x piora o risco fiscal).
- f3 reproduz a nota de f1 (mesma origem): não conta como confirmação independente.
"""
from __future__ import annotations

import copy

F1 = (
    "O governo federal lançou nesta sexta-feira o programa Prospera MEI, voltado aos microempreendedores individuais. "
    "Segundo o Ministério da Fazenda, o programa prevê o perdão de dívidas com a União e a compra de dívidas privadas "
    "dos empreendedores por bancos públicos. A pasta estima que o custo total das medidas será de R$ 12 bilhões em três "
    "anos, com impacto de R$ 4 bilhões por ano no resultado primário. O ministério afirma que o programa tem saldo "
    "positivo para as contas públicas no médio prazo, porque a regularização das dívidas deve ampliar a arrecadação "
    "do Simples Nacional. O texto também eleva o limite de faturamento anual do MEI, o que, segundo a Fazenda, gera "
    "renúncia de receita de R$ 8,1 bilhões entre 2027 e 2029. A medida provisória precisa ser votada pelo Congresso em "
    "até 120 dias. Para o ministério, a inadimplência dos microempreendedores caiu nos últimos meses, mas o crédito "
    "segue caro, com juros elevados por causa da Selic em 10,50% ao ano. A expectativa do governo é que o programa "
    "alcance cerca de 1 milhão de empreendedores no primeiro ano. A Fazenda diz que o custo cabe no orçamento e que "
    "a meta fiscal de 2027 está mantida. O programa também cria uma linha de crédito com garantia do Tesouro para "
    "capital de giro, com taxa de juros abaixo da média do mercado, e prevê educação financeira para os inscritos. "
    "A adesão será feita pelo portal do empreendedor, e a renegociação poderá parcelar o saldo devedor em até 60 meses."
)

F2 = (
    "Economistas ouvidos pela reportagem avaliam que o programa Prospera MEI, lançado pelo governo federal, piora o "
    "risco fiscal em um ano eleitoral. Cálculos da consultoria Fiscal Data indicam que o custo das medidas pode chegar "
    "a R$ 15 bilhões em três anos, acima da estimativa oficial, porque a adesão ao perdão de dívidas tende a ser maior "
    "do que o governo prevê. Para os analistas, o aumento do limite de faturamento do MEI estimula a migração de "
    "empresas maiores para o regime simplificado, o que reduz a arrecadação. A renúncia de receita com o novo teto é "
    "estimada em R$ 8,1 bilhões entre 2027 e 2029, o mesmo valor informado pelo governo. Os economistas afirmam que a "
    "meta de resultado primário de 2027 fica mais difícil de cumprir e que o mercado pode reagir com alta dos juros "
    "futuros. A inadimplência dos microempreendedores segue elevada, segundo os dados de crédito do Banco Central, e o "
    "custo do crédito continua alto com a Selic em 10,50% ao ano. A consultoria lembra que a medida provisória ainda "
    "depende de votação no Congresso e que o desenho final pode mudar o custo do programa. Os analistas recomendam "
    "acompanhar a execução do perdão de dívidas e a evolução da arrecadação do Simples Nacional nos próximos meses, "
    "além do impacto das medidas sobre a dívida pública e sobre as expectativas de inflação do mercado."
)

F3 = (
    "O governo federal lançou nesta sexta-feira o programa Prospera MEI, voltado aos microempreendedores individuais. "
    "Segundo o Ministério da Fazenda, o programa prevê o perdão de dívidas com a União e a compra de dívidas privadas "
    "dos empreendedores por bancos públicos. A pasta estima que o custo total das medidas será de R$ 12 bilhões em três "
    "anos, com impacto de R$ 4 bilhões por ano no resultado primário. O ministério afirma que o programa tem saldo "
    "positivo para as contas públicas no médio prazo, porque a regularização das dívidas deve ampliar a arrecadação "
    "do Simples Nacional. " + F1.split("do Simples Nacional. ", 1)[1]
)

FONTES = [
    {"id": "f1", "nome": "Agência Gov", "tipo_fonte": "primaria", "titulo": "Governo lança Prospera MEI",
     "data": "2026-10-16", "url": "https://gov.example/prospera-mei", "conteudo": F1},
    {"id": "f2", "nome": "Jornal Econômico", "tipo_fonte": "secundaria", "titulo": "Prospera MEI piora risco fiscal, dizem economistas",
     "data": "2026-10-16", "url": "https://jornal.example/prospera", "conteudo": F2},
    {"id": "f3", "nome": "Portal Notícias", "tipo_fonte": "secundaria", "titulo": "Governo lança Prospera MEI",
     "data": "2026-10-16", "url": "https://portal.example/prospera", "conteudo": F3},
]


def _a(aid, text, span, kind="fato", role="nenhum"):
    return {"id": aid, "text": text, "type": kind, "role": role, "variation_declared": False, "source_span": {"text": span}}


def _n(nid, indicator, value, unit, period, span):
    return {"id": nid, "indicator": indicator, "value": value, "unit": unit, "reference_period": period,
            "source_span": {"text": span}}


EXTRACTION_F1 = {
    "main_points": [{"id": "p1", "order": 1, "title": "Governo lança o Prospera MEI", "assertion_ids": ["a1"]},
                    {"id": "p2", "order": 2, "title": "Custo estimado de R$ 12 bilhões em três anos", "assertion_ids": ["a2"]},
                    {"id": "p3", "order": 3, "title": "Fazenda vê saldo positivo para as contas", "assertion_ids": ["a3"]}],
    "assertions": [
        _a("a1", "O governo lançou o Prospera MEI, com perdão de dívidas com a União.",
           "o programa prevê o perdão de dívidas com a União"),
        _a("a2", "A Fazenda estima custo de R$ 12 bilhões em três anos.",
           "A pasta estima que o custo total das medidas será de R$ 12 bilhões em três anos", "projecao"),
        _a("a3", "O ministério afirma que o programa tem saldo positivo para as contas públicas no médio prazo.",
           "O ministério afirma que o programa tem saldo positivo para as contas públicas no médio prazo", "projecao", "impacto"),
        _a("a4", "A elevação do limite do MEI gera renúncia de R$ 8,1 bilhões entre 2027 e 2029.",
           "gera renúncia de receita de R$ 8,1 bilhões entre 2027 e 2029", "projecao", "impacto"),
        _a("a5", "A medida provisória precisa ser votada pelo Congresso em até 120 dias.",
           "A medida provisória precisa ser votada pelo Congresso em até 120 dias", "evento_futuro", "acompanhar"),
    ],
    "numeric_data": [
        _n("n1", "custo total do programa", "12", "R$ bilhões", "três anos", "R$ 12 bilhões em três anos"),
        _n("n2", "renúncia com o novo teto do MEI", "8,1", "R$ bilhões", "2027 a 2029", "R$ 8,1 bilhões entre 2027 e 2029"),
    ],
    "entities": [{"name": "Ministério da Fazenda", "canonical_name": "Ministério da Fazenda"}],
    "events": [], "detected_terms": ["Selic"],
}

EXTRACTION_F2 = {
    "main_points": [{"id": "p1", "order": 1, "title": "Programa piora o risco fiscal", "assertion_ids": ["a1"]},
                    {"id": "p2", "order": 2, "title": "Custo pode chegar a R$ 15 bilhões", "assertion_ids": ["a2"]},
                    {"id": "p3", "order": 3, "title": "Meta de 2027 fica mais difícil", "assertion_ids": ["a4"]}],
    "assertions": [
        _a("a1", "Economistas avaliam que o programa piora o risco fiscal em ano eleitoral.",
           "avaliam que o programa Prospera MEI, lançado pelo governo federal, piora o risco fiscal em um ano eleitoral",
           "projecao", "risco"),
        _a("a2", "A consultoria Fiscal Data calcula que o custo pode chegar a R$ 15 bilhões em três anos.",
           "o custo das medidas pode chegar a R$ 15 bilhões em três anos", "projecao"),
        _a("a3", "A renúncia com o novo teto é estimada em R$ 8,1 bilhões entre 2027 e 2029.",
           "A renúncia de receita com o novo teto é estimada em R$ 8,1 bilhões entre 2027 e 2029", "projecao", "impacto"),
        _a("a4", "Os economistas afirmam que a meta de resultado primário de 2027 fica mais difícil de cumprir.",
           "a meta de resultado primário de 2027 fica mais difícil de cumprir", "projecao", "risco"),
    ],
    "numeric_data": [
        _n("n1", "custo do programa", "15", "R$ bilhões", "três anos", "R$ 15 bilhões em três anos"),
        _n("n2", "renúncia com o novo teto", "8,1", "R$ bilhões", "2027 a 2029", "R$ 8,1 bilhões entre 2027 e 2029"),
    ],
    "entities": [{"name": "Fiscal Data", "canonical_name": "Fiscal Data"}], "events": [], "detected_terms": [],
}

EXTRACTION_F3 = copy.deepcopy(EXTRACTION_F1)

ALINHAMENTO = {
    "assunto": "Programa Prospera MEI",
    "topicos": [
        {"id": "t1", "titulo": "Custo total do programa em três anos", "tipo": "numerico", "referencia": None,
         "itens": [{"fonte": "f1", "ids": ["f1:n1"], "posicao": "neutra", "resumo": "A Fazenda estima R$ 12 bilhões."},
                   {"fonte": "f2", "ids": ["f2:n1"], "posicao": "neutra", "resumo": "A Fiscal Data calcula até R$ 15 bilhões."},
                   {"fonte": "f3", "ids": ["f3:n1"], "posicao": "neutra", "resumo": "Reproduz a estimativa da Fazenda."}]},
        {"id": "t2", "titulo": "Efeito do programa sobre o risco fiscal", "tipo": "qualitativo",
         "referencia": "O programa tem saldo positivo para as contas públicas.",
         "itens": [{"fonte": "f1", "ids": ["f1:a3"], "posicao": "apoia", "resumo": "A Fazenda vê saldo positivo."},
                   {"fonte": "f2", "ids": ["f2:a1"], "posicao": "contesta", "resumo": "Economistas veem piora do risco fiscal."}]},
        {"id": "t3", "titulo": "Renúncia com o novo teto do MEI", "tipo": "numerico", "referencia": None,
         "itens": [{"fonte": "f1", "ids": ["f1:n2"], "posicao": "neutra", "resumo": "R$ 8,1 bilhões entre 2027 e 2029."},
                   {"fonte": "f2", "ids": ["f2:n2"], "posicao": "neutra", "resumo": "R$ 8,1 bilhões entre 2027 e 2029."}]},
        {"id": "t4", "titulo": "Votação da medida provisória", "tipo": "qualitativo",
         "referencia": "A medida provisória depende de votação no Congresso.",
         "itens": [{"fonte": "f1", "ids": ["f1:a5"], "posicao": "apoia", "resumo": "Precisa ser votada em até 120 dias."},
                   {"fonte": "f9", "ids": ["f9:a1"], "posicao": "apoia", "resumo": "id inexistente"}]},
    ],
}
