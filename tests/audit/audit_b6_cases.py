# -*- coding: utf-8 -*-
"""Casos B6 escritos à mão: 3 saídas boas e saídas ruins derivadas (boa + um defeito).

Fonte: DOC_MEDIO de tests/audit/baseline/documents.py (ata sintética do Copom).
Cada caso ruim altera UM aspecto de uma saída boa, para isolar o que cada métrica detecta.
"""
from __future__ import annotations

MAIN_POINTS = [
    "Selic mantida em 10,50% ao ano",
    "IPCA acumulado acima da meta de inflação",
    "Disciplina fiscal e choques de oferta como riscos",
]

# Frase aprovada de impacto geral (o glossário real não tem esse campo; usada só aqui).
APPROVED_IMPACT = ["juros altos encarecem empréstimos e financiamentos"]

INI = {
    "introduction": (
        "O Banco Central decidiu manter a taxa Selic em 10,50% ao ano. A Selic é a taxa básica de juros do país, "
        "ou seja, a referência para o custo do dinheiro. A decisão saiu da reunião do Copom, o grupo do Banco "
        "Central que define essa taxa. A pergunta central é simples: por que os juros continuam altos?"
    ),
    "development": (
        "O Copom se reuniu nos dias 12 e 13 de outubro de 2026. A decisão foi unânime, isto é, todos os membros "
        "votaram da mesma forma. O motivo principal é a inflação. Inflação é a alta geral dos preços ao longo do "
        "tempo. O IPCA, que é o índice oficial de inflação do país, subiu 4,5% em 12 meses. A meta de inflação é de "
        "3%, com tolerância de 1,5 ponto para cima ou para baixo. Ou seja, a inflação está acima do centro da meta. "
        "O comitê também observou que a economia cresceu mais do que o esperado no terceiro trimestre. O desemprego "
        "caiu um pouco. Mesmo assim, muitas pessoas ainda trabalham sem carteira assinada. A renda média não "
        "acompanhou a alta dos preços, e isso reduz o que as famílias conseguem comprar."
    ),
    "analysis": (
        "Segundo a ata, a política de juros altos busca levar a inflação de volta para a meta. Em geral, juros altos "
        "encarecem empréstimos e financiamentos. O comitê aponta dois riscos. O primeiro é fiscal: a dívida pública, que é o "
        "total que o governo deve, segue elevada. O governo anunciou medidas para conter gastos, mas o Copom espera "
        "ver essas medidas na prática. O segundo risco são os choques de oferta, que são falhas ou quedas na "
        "produção de bens. Alimentos e energia podem ficar mais caros e pressionar a inflação no curto prazo. Lá "
        "fora, os países ricos mantêm juros altos, o que afeta o fluxo de dinheiro para países como o Brasil."
    ),
    "conclusion": (
        "Em resumo, o Banco Central manteve os juros altos porque a inflação ainda está acima da meta. Para o bolso, "
        "isso significa crédito mais caro por mais tempo. Segundo o boletim Focus, uma pesquisa do Banco Central com "
        "economistas, as expectativas de inflação para 2027 e 2028 estão próximas da meta. O que acompanhar, segundo a fonte, é a evolução dos preços de alimentos "
        "e energia e das contas do governo. O próximo encontro do Copom será daqui a 45 dias."
    ),
}

INTER = {
    "introduction": (
        "O Copom manteve a Selic em 10,50% ao ano, em decisão unânime na reunião de 12 e 13 de outubro de 2026. A ata "
        "reforça o caráter contracionista da política monetária. A questão para quem acompanha o mercado é entender o "
        "que sustenta essa postura e quais fatores, segundo a fonte, podem alterá-la."
    ),
    "development": (
        "O principal argumento do comitê é a inflação. O IPCA acumulado em 12 meses está em 4,5%, acima do centro da "
        "meta de 3%, que tem tolerância de 1,5 ponto percentual. No cenário doméstico, o PIB do terceiro trimestre "
        "superou as expectativas iniciais, o que indica atividade resiliente. O mercado de trabalho mostra sinais "
        "mistos: o desemprego recuou ligeiramente, mas a informalidade continua elevada e a renda média não acompanhou "
        "a inflação, o que reduz o poder de compra das famílias. No cenário externo, as economias avançadas mantêm "
        "juros altos, o que afeta o fluxo de capitais para emergentes como o Brasil. As commodities seguem voláteis, "
        "influenciadas por tensões geopolíticas, e a resiliência da economia americana pode manter o Federal Reserve "
        "com juros altos por mais tempo."
    ),
    "analysis": (
        "A ata liga o êxito da política monetária à disciplina fiscal. O governo anunciou contenção de gastos, mas o "
        "Copom aguarda a implementação efetiva dessas medidas antes de avaliar o efeito sobre a inflação, e a dívida "
        "pública segue em patamar elevado. Outro risco declarado são os choques de oferta em alimentos e energia, que "
        "podem pressionar o IPCA no curto prazo. Para a leitura de alocação, o relevante é a combinação descrita pela "
        "fonte: juros domésticos elevados, juros altos também nas economias avançadas e fluxo de capitais mais fraco "
        "para mercados emergentes. A fonte não indica data para mudança na Selic e afirma que qualquer alteração será "
        "comunicada por comunicados e atas."
    ),
    "conclusion": (
        "Em síntese, o Copom mantém a Selic em 10,50% enquanto o IPCA permanece acima da meta. Segundo o boletim Focus, "
        "as expectativas para 2027 e 2028 estão ancoradas próximas à meta. Os fatores a acompanhar, segundo a fonte, "
        "são a execução das medidas fiscais, os choques de oferta e os juros nas economias avançadas. A próxima "
        "reunião está prevista para daqui a 45 dias."
    ),
}

AVAN = {
    "introduction": (
        "O Copom manteve a Selic em 10,50% a.a. por unanimidade na reunião de 12 e 13 de outubro de 2026, preservando "
        "a política monetária contracionista. A questão é como a ata articula IPCA acima da meta, atividade "
        "resiliente e risco fiscal na manutenção do aperto monetário."
    ),
    "development": (
        "O IPCA acumulado em 12 meses, de 4,5%, segue acima do centro da meta de 3%, com banda de tolerância de 1,5 "
        "p.p., o que justifica, segundo a ata, a manutenção da taxa básica em nível restritivo. O PIB do terceiro "
        "trimestre surpreendeu para cima, sinalizando demanda agregada resiliente. No mercado de trabalho, a queda "
        "marginal do desemprego convive com informalidade elevada e renda real média que não acompanhou a inflação. "
        "No cenário externo, juros elevados nas economias avançadas afetam o fluxo de capitais para mercados "
        "emergentes, e a resiliência da economia dos Estados Unidos pode manter o Federal Reserve com juros altos por "
        "mais tempo. A "
        "volatilidade das commodities, ligada a tensões geopolíticas, adiciona incerteza ao balanço de riscos."
    ),
    "analysis": (
        "A ata condiciona a eficácia da política monetária à disciplina fiscal: a contenção de gastos anunciada ainda "
        "depende de implementação, e a trajetória da dívida pública permanece elevada, o que mantém o risco fiscal no "
        "balanço de riscos. Do lado da oferta, choques em alimentos e energia podem pressionar a inflação corrente no "
        "curto prazo, ainda que as expectativas do boletim Focus para 2027 e 2028 sigam ancoradas próximas à meta. A "
        "combinação de expectativas ancoradas com IPCA acima da meta sustenta, segundo a ata, a manutenção da "
        "política monetária contracionista com juros elevados. A ata reafirma o compromisso com a estabilidade de "
        "preços e condiciona a avaliação do impacto fiscal à efetiva implementação das medidas de contenção de gastos "
        "anunciadas pelo governo federal, com a dívida pública em patamar elevado."
    ),
    "conclusion": (
        "Em síntese, o Copom mantém a Selic em 10,50% e a política monetária contracionista diante do IPCA acima da "
        "meta, do risco fiscal e dos choques de oferta. Os vetores a monitorar, conforme a ata, são a execução fiscal, "
        "os choques de oferta em alimentos e energia e a política monetária nas economias avançadas. A próxima reunião "
        "ocorre em 45 dias, e eventuais mudanças serão comunicadas por comunicados e atas."
    ),
}


def make_text(sections: dict, level: str, *, caixa: bool | None = None) -> dict:
    wc = {k: len(v.split()) for k, v in sections.items()}
    out = {
        "title": "Juros básicos seguem em 10,50% ao ano" if level == "iniciante" else "Copom mantém a Selic em 10,50%",
        "subtitle": "Ata de outubro de 2026 explica a decisão",
        **{k: {"title": k, "content": v, "ponto_ids": ["mp1", "mp2", "mp3"]} for k, v in sections.items()},
        "covered_main_points": ["mp1", "mp2", "mp3"],
        "word_count_total": sum(wc.values()),
        "word_count_by_section": wc,
        "fonte_bloco": "Fonte: Banco Central do Brasil, Ata do Copom, outubro de 2026.",
        "caixa_entenda_os_termos": None,
    }
    if caixa if caixa is not None else level == "iniciante":
        out["caixa_entenda_os_termos"] = "Selic: taxa básica de juros. IPCA: índice oficial de inflação."
    return out


def _mut(base: dict, section: str, fn) -> dict:
    s = dict(base)
    s[section] = fn(s[section])
    return s


JARGAO_SEM_EXPLICACAO = (
    "Segundo a ata, a política monetária contracionista busca a desinflação com expectativas ancoradas. O hiato do "
    "produto e a resiliência da demanda agregada mantêm o balanço de riscos assimétrico. O risco fiscal e a trajetória "
    "da dívida pública elevam o prêmio de risco. Choques de oferta em alimentos e energia podem pressionar a "
    "inflação corrente no curto prazo. Juros elevados nas economias avançadas restringem o fluxo de capitais. "
    "Em geral, juros altos encarecem empréstimos e financiamentos."
)

EXTRA_FIEL = (
    " No cenário internacional, a ata registra que as economias avançadas mantêm juros elevados, que os preços das "
    "commodities seguem voláteis por causa de tensões geopolíticas e da demanda global, e que a economia dos Estados "
    "Unidos mostra sinais de resiliência. O texto do comitê também lembra que o governo federal anunciou medidas de "
    "contenção de gastos e que o comitê aguarda a efetiva implementação dessas medidas para avaliar o impacto na "
    "inflação. Sobre o mercado de trabalho, a ata diz que a taxa de desemprego recuou ligeiramente, que a "
    "informalidade permanece elevada e que a renda média do trabalhador não acompanhou a inflação, o que afeta o "
    "poder de compra das famílias. A ata reafirma o compromisso com a estabilidade de preços e diz que qualquer "
    "mudança na política monetária será informada por comunicados e atas publicados no site oficial. O documento "
    "também destaca a importância da disciplina fiscal para o êxito da política monetária e registra que a dívida "
    "pública segue em patamar elevado, o que exige atenção constante. Por fim, o comitê lembra que o boletim Focus "
    "mostra expectativas de inflação ancoradas próximas à meta para os anos seguintes."
)


def build_cases() -> list[dict]:
    """Lista de casos: id, tipo, nível, formato, conteúdo, falha esperada (descrição)."""
    c = []
    add = lambda cid, kind, lvl, content, expected, fmt="texto_analitico": c.append(  # noqa: E731
        {"id": cid, "tipo": kind, "nivel": lvl, "formato": fmt, "conteudo": content, "esperado": expected})

    # Boas
    add("g1_iniciante", "boa", "iniciante", make_text(INI, "iniciante"), "passar")
    add("g2_intermediario", "boa", "intermediario", make_text(INTER, "intermediario"), "passar")
    add("g3_avancado", "boa", "avancado", make_text(AVAN, "avancado"), "passar")

    rep = " ".join(["Os juros altos servem para frear a alta dos preços."] * 6)
    add("b01_padding_repetido", "ruim", "iniciante",
        make_text(_mut(INI, "analysis", lambda s: s + " " + rep), "iniciante"),
        "reprovar: redundância (mesma frase 6x, total ainda < 500 palavras)")
    add("b02_numero_inventado", "ruim", "iniciante",
        make_text(_mut(INI, "development", lambda s: s.replace("4,5%", "5,8%")), "iniciante"),
        "reprovar: número 5,8% não existe na fonte")
    add("b03_data_inventada", "ruim", "iniciante",
        make_text(_mut(INI, "development", lambda s: s.replace("12 e 13 de outubro", "18 e 19 de setembro")),
                  "iniciante"),
        "reprovar: data 18 e 19 de setembro não existe na fonte")
    add("b04_comparacao_entre_documentos", "ruim", "iniciante",
        make_text(_mut(INI, "development", lambda s: s.replace(
            "Ou seja, a inflação está acima do centro da meta.",
            "A inflação subiu em relação ao mês passado, quando estava bem menor.")), "iniciante"),
        "reprovar: variação não declarada pela fonte")
    add("b05_recomendacao_de_compra", "ruim", "iniciante",
        make_text(_mut(INI, "conclusion", lambda s: s + " Por isso, vale a pena investir agora em títulos atrelados "
                       "à Selic e vender ações."), "iniciante"),
        "reprovar: recomendação de compra e venda")
    add("b06a_emoji_coberto", "ruim", "iniciante",
        make_text(_mut(INI, "introduction", lambda s: s + " 📉"), "iniciante"), "reprovar: emoji")
    add("b06b_emoji_fora_da_regex", "ruim", "iniciante",
        make_text(_mut(INI, "introduction", lambda s: s + " 🤑 ✅"), "iniciante"), "reprovar: emoji")
    add("b07_termo_proibido", "ruim", "iniciante",
        make_text(_mut(INI, "conclusion", lambda s: s + " Não há garantia de lucro em nenhuma aplicação."),
                  "iniciante"),
        "reprovar: termo proibido 'garantia de lucro'")
    add("b08_iniciante_jargao_sem_explicacao", "ruim", "iniciante",
        make_text(_mut(INI, "analysis", lambda s: JARGAO_SEM_EXPLICACAO), "iniciante"),
        "reprovar: jargão sem explicação no Iniciante")
    add("b09_avancado_sem_jargao", "ruim", "avancado", make_text(INI, "avancado", caixa=False),
        "reprovar: texto Iniciante entregue como Avançado")
    add("b10_ponto_central_ausente", "ruim", "iniciante",
        make_text(_mut(_mut(INI, "analysis", lambda s: (
            "Segundo a ata, os juros altos servem para frear a alta dos preços. Quando os juros ficam altos, pegar "
            "dinheiro emprestado fica mais caro, e as pessoas tendem a gastar menos. Em geral, juros altos encarecem "
            "empréstimos e financiamentos. Lá fora, os juros altos nos países ricos também pesam, porque atraem "
            "dinheiro que poderia vir para o Brasil. A ata não traz outros detalhes sobre esse ponto. O comitê "
            "segue atento à evolução dos preços e à atividade econômica do país nos próximos meses."
        )), "conclusion", lambda s: s.replace(" e energia e das contas do governo", "")), "iniciante"),
        "reprovar: ponto 3 (fiscal e choques de oferta) ausente")
    add("b11_excesso_de_palavras", "ruim", "iniciante",
        make_text(_mut(INI, "development", lambda s: s + EXTRA_FIEL), "iniciante"),
        "reprovar: mais de 500 palavras")
    add("b13_em_geral_fora_do_glossario", "ruim", "iniciante",
        make_text(_mut(INI, "analysis", lambda s: s.replace(
            "Em geral, juros altos encarecem empréstimos e financiamentos.",
            "Em geral, os bancos aumentam as tarifas quando a Selic fica alta.")), "iniciante"),
        "reprovar: frase com 'Em geral,' que não está no glossário")

    # Texto "jogado" contra os gates: frases curtas e repetidas, sem conteúdo, contagem por seção declarada
    # (o gate de proporção usa word_count_by_section informado pelo próprio gerador).
    filler = ["O juro é alto.", "O BC vê a alta.", "A taxa não mudou.", "O preço sobe.", "A meta é de 3%.",
              "O Copom fala.", "A Selic é de 10,50%.", "O IPCA está acima da meta.", "Há risco fiscal.",
              "Há choques de oferta."]
    def _pad(n):
        return " ".join((filler * 20)[:n])
    gamed = {"introduction": _pad(15), "development": _pad(35), "analysis": _pad(30), "conclusion": _pad(20)}
    gamed_out = make_text(gamed, "iniciante")
    gamed_out["word_count_total"] = 400
    gamed_out["word_count_by_section"] = {"introduction": 60, "development": 140, "analysis": 120, "conclusion": 80}
    add("b14_padding_contra_os_gates", "ruim", "iniciante", gamed_out,
        "reprovar: 10 frases curtas repetidas 10x, sem análise")

    # Carrossel com slides de corpo repetidos
    corpo = {"order": 2, "role": "corpo", "title": "Selic em 10,50%", "body": "O Copom manteve a Selic em 10,50% ao ano."}
    slides = [{"order": 1, "role": "gancho", "title": "Selic em 10,50%", "body": "O Copom manteve a Selic em 10,50% ao ano."}]
    slides += [dict(corpo, order=i) for i in (2, 3, 4)]
    slides += [{"order": 5, "role": "conclusao", "title": "Em resumo", "body": "O Copom manteve a Selic em 10,50% ao ano."}]
    add("b12_slides_repetidos", "ruim", "iniciante",
        {"carousel": {"slides": slides, "linha_vermelha_nivel": "em cima"},
         "caption": {"opening": "Selic em 10,50%.", "short_context": "O Copom manteve a Selic.",
                     "source_block": "Fonte: BCB", "cta_verb": "salvar", "cta_sentence": "Salve para consultar."}},
        "reprovar: 4 de 5 slides idênticos", fmt="carrossel")
    return c
