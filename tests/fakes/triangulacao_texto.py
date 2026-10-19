# -*- coding: utf-8 -*-
"""Texto analítico triangulado (nível Iniciante) escrito à mão sobre o dossiê de tests/fakes/triangulacao.py.

Usa só o que as fontes dizem, atribui cada número, apresenta a divergência lado a lado e não dá veredito.
"""
from __future__ import annotations

INTRO = (
    "O governo federal lançou o programa Prospera MEI, voltado aos microempreendedores individuais, que são pessoas que "
    "trabalham por conta própria com um registro simples de empresa. Comparamos duas fontes independentes sobre o "
    "programa: a Agência Gov, que publica a nota oficial do governo, e o Jornal Econômico, que ouviu economistas. Uma "
    "terceira reportagem, do Portal Notícias, repete a nota oficial e por isso não conta como fonte separada. A "
    "pergunta central é simples: quanto o programa custa e o que ele faz com as contas do governo?"
)

DEV = (
    "Segundo a Agência Gov, o programa prevê o perdão de dívidas com a União e a compra de dívidas de bancos. "
    "Perdão de dívida quer dizer que parte do que o empreendedor deve deixa de ser cobrada. A Agência Gov informa que "
    "o Ministério da Fazenda estima o custo total em R$ 12 bilhões em três anos.\n\n"
    "O Jornal Econômico traz outra conta. Segundo o jornal, a consultoria Fiscal Data calcula que o custo pode chegar "
    "a R$ 15 bilhões em três anos. Para os analistas ouvidos pelo Jornal Econômico, a adesão ao perdão de dívidas "
    "tende a ser maior do que o governo prevê. As duas estimativas aparecem lado a lado no gráfico deste texto.\n\n"
    "Há um ponto em que as fontes concordam. A Agência Gov e o Jornal Econômico informam que o novo limite de "
    "faturamento do MEI gera renúncia de receita de R$ 8,1 bilhões entre 2027 e 2029. Renúncia de receita é o dinheiro "
    "de imposto que o governo deixa de arrecadar. Faturamento é tudo o que o negócio vende em um ano.\n\n"
    "As duas fontes também citam o custo do crédito. A Agência Gov e o Jornal Econômico lembram que a Selic, que é a "
    "taxa básica de juros do país, está em 10,50% ao ano. Segundo a Agência Gov, o crédito segue caro por causa dos "
    "juros elevados."
)

ANALYSIS = (
    "As fontes divergem sobre o efeito do programa nas contas públicas. Segundo a Agência Gov, o ministério afirma que "
    "o programa tem saldo positivo para as contas no médio prazo. A ideia, segundo a nota, é que as dívidas pagas em "
    "dia devem aumentar a arrecadação do Simples Nacional, que é o regime de impostos das pequenas empresas.\n\n"
    "O Jornal Econômico apresenta o lado oposto. Segundo o jornal, economistas avaliam que o programa piora o risco "
    "fiscal em um ano eleitoral. Risco fiscal é a chance de o governo gastar mais do que arrecada e ter dificuldade "
    "para pagar as contas. Para os analistas ouvidos pelo Jornal Econômico, a meta de resultado primário de 2027 fica "
    "mais difícil de cumprir. Resultado primário é a diferença entre o que o governo arrecada e o que gasta, sem contar "
    "os juros da dívida.\n\n"
    "Cada lado tem a sua explicação. A Agência Gov aposta na volta dos pagamentos. O Jornal Econômico aponta que o "
    "novo limite pode levar empresas maiores a mudar para o regime do MEI e reduzir a arrecadação. As duas posições "
    "estão no mapa de posições, ao lado dos trechos de cada fonte."
)

CONCLUSION = (
    "Em resumo, as duas fontes concordam sobre a renúncia com o novo limite, mas divergem sobre o custo total e sobre o "
    "efeito nas contas do governo. A Agência Gov fala em R$ 12 bilhões e em saldo positivo. O Jornal Econômico fala em "
    "até R$ 15 bilhões e em mais risco fiscal. Nenhuma das duas fontes diz qual conta vai se confirmar.\n\n"
    "Segundo a Agência Gov, a medida provisória precisa ser votada pelo Congresso em até 120 dias. Segundo o "
    "Jornal Econômico, o desenho final pode mudar o custo do programa. O que acompanhar, segundo as fontes, é a "
    "votação no Congresso, a adesão ao perdão de dívidas e a arrecadação do Simples Nacional nos próximos meses."
)


def good_triangulated_text() -> dict:
    def sec(title, content, lines):
        return {"title": title, "content": content, "ponto_ids": [l for l in lines if l in {"L1", "L2", "L3"}],
                "linha_ids": lines}
    return {
        "title": "Prospera MEI: quanto custa e o que muda nas contas",
        "subtitle": "Governo e economistas divergem sobre o custo e o risco fiscal",
        "introduction": sec("O programa e as fontes", INTRO, ["L1"]),
        "development": sec("O que as fontes informam", DEV, ["L1", "L3"]),
        "analysis": sec("Onde as fontes divergem", ANALYSIS, ["L2"]),
        "conclusion": sec("O que acompanhar", CONCLUSION, ["L1", "L2", "L3", "L4"]),
        "graficos_citados": ["mapa_posicoes", "valores_L1"],
        "aviso_fonte_insuficiente": None,
    }
