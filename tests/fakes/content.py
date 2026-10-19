# -*- coding: utf-8 -*-
"""Conteúdo de teste: documento (ata sintética do Copom), extração ancorada e saídas boas por nível/formato.

As saídas boas foram escritas à mão para passar nas métricas determinísticas do nível; as ruins derivam delas
com um defeito cada (ver tests/audit/audit_b6_cases.py).
"""
from __future__ import annotations

import copy

from tests.audit.audit_b6_cases import AVAN, INI, INTER
from tests.audit.baseline.documents import DOC_MEDIO

SOURCE = DOC_MEDIO.strip()
ORIGIN = {"instituicao": "Banco Central do Brasil", "titulo": "Ata do Copom", "data": "2026-10-13"}

EXTRACTION = {
    "main_points": [
        {"id": "p1", "order": 1, "title": "Copom mantém a Selic em 10,50% ao ano", "assertion_ids": ["a1"],
         "justification": "decisão principal da ata"},
        {"id": "p2", "order": 2, "title": "IPCA acumulado acima da meta de inflação", "assertion_ids": ["a2", "a3"],
         "justification": "motivo declarado"},
        {"id": "p3", "order": 3, "title": "Disciplina fiscal e choques de oferta como riscos", "assertion_ids": ["a4", "a5"],
         "justification": "riscos destacados"},
    ],
    "assertions": [
        {"id": "a1", "text": "O Copom manteve a Selic em 10,50% ao ano, por unanimidade.", "type": "fato", "role": "nenhum",
         "source_span": {"text": "decidiu, por unanimidade, manter a taxa básica de juros, a Selic, em 10,50% ao ano"},
         "variation_declared": False},
        {"id": "a2", "text": "O IPCA acumulado em 12 meses está em 4,5%, acima do centro da meta.", "type": "fato",
         "role": "causa", "source_span": {"text": "O IPCA acumulado em 12 meses encontra-se em 4,5%, acima do centro da meta"},
         "variation_declared": False},
        {"id": "a3", "text": "A meta de inflação é de 3%, com tolerância de 1,5 ponto percentual.", "type": "fato",
         "role": "nenhum", "source_span": {"text": "meta de 3%, com tolerância de 1,5 ponto percentual"},
         "variation_declared": False},
        {"id": "a4", "text": "O comitê destaca a importância da disciplina fiscal para o êxito da política monetária.",
         "type": "fato", "role": "risco",
         "source_span": {"text": "O Copom também destaca a importância da disciplina fiscal para o êxito da política monetária"},
         "variation_declared": False},
        {"id": "a5", "text": "Choques de oferta em alimentos e energia podem pressionar a inflação no curto prazo.",
         "type": "projecao", "role": "risco",
         "source_span": {"text": "choques de oferta, especialmente em alimentos e energia, podem pressionar a inflação no curto prazo"},
         "variation_declared": False},
        {"id": "a6", "text": "As expectativas de inflação para 2027 e 2028 estão ancoradas próximas à meta.",
         "type": "projecao", "role": "acompanhar",
         "source_span": {"text": "As expectativas de inflação para 2027 e 2028 estão ancoradas próximas à meta"},
         "variation_declared": False},
        {"id": "a9", "text": "Trecho inventado que não existe na ata.", "type": "fato", "role": "nenhum",
         "source_span": {"text": "o comitê decidiu cortar os juros pela metade"}, "variation_declared": False},
    ],
    "numeric_data": [
        {"id": "n1", "indicator": "Selic", "value": "10,50", "unit": "% ao ano", "reference_period": "outubro de 2026",
         "source_span": {"text": "10,50% ao ano"}},
        {"id": "n2", "indicator": "IPCA em 12 meses", "value": "4,5", "unit": "%", "reference_period": "12 meses",
         "source_span": {"text": "4,5%"}},
    ],
    "entities": [{"name": "Copom", "canonical_name": "Copom", "type": "instituicao"}],
    "events": [{"name": "Reunião do Copom", "canonical_name": "Reunião do Copom", "reference_date": "2026-10-13"}],
    "detected_terms": ["Selic", "IPCA"],
}


def _text(sections: dict, title: str) -> dict:
    out = {"title": title, "subtitle": "Ata de outubro de 2026 explica a decisão"}
    for name, content in sections.items():
        out[name] = {"title": name.capitalize(), "content": content, "ponto_ids": ["p1", "p2", "p3"],
                     "afirmacao_ids": ["a1", "a2", "a3", "a4", "a5"]}
    out["aviso_fonte_insuficiente"] = None
    return out


# Iniciante sem "Em geral," (o glossário real não tem explicação de impacto aprovada)
_INI_NO_MARKER = dict(INI)
_INI_NO_MARKER["analysis"] = INI["analysis"].replace(
    " Em geral, juros altos encarecem empréstimos e financiamentos.", "")

GOOD_TEXT = {
    "iniciante": _text(_INI_NO_MARKER, "Juros básicos seguem em 10,50% ao ano"),
    "intermediario": _text(INTER, "Copom mantém a Selic em 10,50%"),
    "avancado": _text(AVAN, "Copom mantém a Selic em 10,50%"),
}

GOOD_CAROUSEL_INICIANTE = {
    "slides": [
        {"order": 1, "role": "gancho", "title": "Juros básicos seguem em 10,50% ao ano",
         "body": "O Banco Central manteve a Selic, que é a taxa básica de juros do país, em 10,50% ao ano.",
         "highlight_data": "10,50%", "ponto_id": None, "afirmacao_ids": ["a1"]},
        {"order": 2, "role": "corpo", "title": "Uma decisão de todos",
         "body": "Os membros do comitê do Banco Central votaram da mesma forma e mantiveram a taxa básica de juros.",
         "highlight_data": None, "ponto_id": "p1", "afirmacao_ids": ["a1"]},
        {"order": 3, "role": "corpo", "title": "Preços acima da meta",
         "body": "O IPCA, que é o índice oficial de inflação, chegou a 4,5% em 12 meses. A meta é de 3%.",
         "highlight_data": "4,5%", "ponto_id": "p2", "afirmacao_ids": ["a2", "a3"]},
        {"order": 4, "role": "corpo", "title": "Dois riscos no caminho",
         "body": "A dívida do governo segue alta. Alimentos e energia podem pressionar a inflação no curto prazo.",
         "highlight_data": None, "ponto_id": "p3", "afirmacao_ids": ["a4", "a5"]},
        {"order": 5, "role": "conclusao", "title": "Em resumo",
         "body": "Os juros seguem altos porque a inflação ainda está acima do centro da meta.",
         "highlight_data": None, "ponto_id": None, "afirmacao_ids": ["a2"]},
    ],
    "caption": {"opening": "O Banco Central manteve os juros básicos em 10,50% ao ano.",
                "short_context": "Segundo a ata, a inflação ainda está acima do centro da meta.",
                "cta_verb": "salvar", "cta_sentence": "Salve este post para entender a próxima decisão sobre os juros."},
}

GOOD_SCRIPT_INICIANTE = {
    "scenes": [
        {"order": 1, "role": "gancho", "start_sec": 0, "end_sec": 10,
         "fala_escrita": "O Banco Central manteve a Selic, que é a taxa básica de juros, em 10,50% ao ano.",
         "texto_na_tela": "Selic em 10,50% ao ano", "visual": "Número em destaque sobre fundo branco com detalhe vermelho",
         "enquadramento": "close", "direcao": "Fale olhando para a câmera", "ponto_id": None, "afirmacao_ids": ["a1"]},
        {"order": 2, "role": "corpo", "start_sec": 10, "end_sec": 22,
         "fala_escrita": "A decisão foi unânime. Todos os membros do comitê votaram da mesma forma.",
         "texto_na_tela": "Decisão unânime", "visual": "Texto curto na tela", "enquadramento": "plano_medio",
         "direcao": None, "ponto_id": "p1", "afirmacao_ids": ["a1"]},
        {"order": 3, "role": "corpo", "start_sec": 22, "end_sec": 34,
         "fala_escrita": "O IPCA, que é o índice oficial de inflação, chegou a 4,5% em 12 meses. A meta é de 3%.",
         "texto_na_tela": "IPCA: 4,5% em 12 meses", "visual": "Barra simples comparando 4,5% e 3%",
         "enquadramento": "plano_medio", "direcao": None, "ponto_id": "p2", "afirmacao_ids": ["a2", "a3"]},
        {"order": 4, "role": "corpo", "start_sec": 34, "end_sec": 46,
         "fala_escrita": "A dívida do governo segue alta. Alimentos e energia podem pressionar a inflação no curto prazo.",
         "texto_na_tela": "Riscos: contas do governo e alimentos", "visual": "Ícones de prato e de energia",
         "enquadramento": "plano_aberto", "direcao": None, "ponto_id": "p3", "afirmacao_ids": ["a4", "a5"]},
        {"order": 5, "role": "conclusao", "start_sec": 46, "end_sec": 55,
         "fala_escrita": "Em resumo, os juros seguem altos porque a inflação está acima da meta.",
         "texto_na_tela": "Inflação acima da meta", "visual": "Resumo em uma linha", "enquadramento": "close",
         "direcao": None, "ponto_id": None, "afirmacao_ids": ["a2"]},
    ],
    "total_duration_sec": 55,
}


def good_output(fmt: str, level: str) -> dict:
    if fmt == "texto_analitico":
        return copy.deepcopy(GOOD_TEXT[level])
    if fmt == "carrossel":
        return copy.deepcopy(GOOD_CAROUSEL_INICIANTE)
    return copy.deepcopy(GOOD_SCRIPT_INICIANTE)


def judge_output(score: float = 8.5, low: dict[str, float] | None = None,
                 rubric_path: str = "src/evaluation/rubric.yaml") -> dict:
    import yaml
    from pathlib import Path

    rubric = yaml.safe_load(Path(rubric_path).read_text(encoding="utf-8"))
    low = low or {}
    return {"criterios": [{"nome": c["nome"], "nota": low.get(c["nome"], score),
                           "justificativa": "Sustentado pelas afirmações a1 e a2.", "evidencias": ["a1"]}
                          for c in rubric["criterios"]], "resumo": "ok"}
