"""Juiz LLM (seção 4.7): rubrica versionada, entrada estruturada, saída validada e aprovação calculada pelo código."""
from __future__ import annotations

import pytest
import yaml

from src.evaluation.judge import LLMJudge
from src.shared.llm_client import InvalidLLMOutput
from tests.fakes import content
from tests.fakes.llm import FakeLLMClient

RUBRIC = yaml.safe_load(open("src/evaluation/rubric.yaml", encoding="utf-8"))


def _judge(response):
    client = FakeLLMClient(responses={"judge": [response]})
    return LLMJudge(llm_client=client), client


def test_rubric_is_versioned_and_covers_what_metrics_do_not_measure():
    names = {c["nome"] for c in RUBRIC["criterios"]}
    assert RUBRIC["versao"] == "2.0"
    assert {"fidelidade_semantica", "nuance_e_grau_de_certeza", "adequacao_ao_nivel", "tom_e_guia_de_estilo"} <= names
    # critérios de triangulação ficam em rubrica própria
    assert not names & {"fidelidade_atribuicao", "neutralidade", "representacao_justa"}
    assert all(c.get("ancoras") for c in RUBRIC["criterios"])


def test_prompt_sends_criteria_descriptions_assertions_and_metrics_not_whole_document():
    judge, client = _judge(content.judge_output())
    judge.evaluate("Texto avaliado.", level="iniciante", formato="texto_analitico",
                   assertions_block="- a1 (fato): O Copom manteve a Selic.", metrics={"flesch": 70.1})
    prompt = client.prompts[0]["prompt"]
    assert "Não premie tamanho" in prompt
    assert RUBRIC["criterios"][0]["descricao"][:40] in prompt
    assert "- a1 (fato): O Copom manteve a Selic." in prompt and "flesch: 70.1" in prompt
    assert content.SOURCE[:200] not in prompt
    assert client.calls[0]["role"] == "judge" and client.calls[0]["model_id"] == client.judge_model


def test_approval_is_weighted_mean_computed_by_code():
    result, _ = _judge(content.judge_output(score=8.0))
    r = result.evaluate("Um texto curto de teste.", level="iniciante")
    assert r.aprovado is True and r.media_ponderada == 8.0
    assert r.text_length == 5  # medido pelo código, não informado pelo juiz
    assert r.judge_model_id == "judge-model-x"
    assert all(c.evidencias for c in r.criterios)


def test_one_criterion_below_minimum_rejects_even_with_high_mean():
    response = content.judge_output(score=9.5, low={"nuance_e_grau_de_certeza": 4.0})
    r = _judge(response)[0].evaluate("Texto.", level="avancado")
    assert r.media_ponderada > 7
    assert r.aprovado is False
    assert r.criterios_abaixo_do_minimo == ["nuance_e_grau_de_certeza"]
    feedback = r.feedback(7.0, 5.0)
    assert "nuance_e_grau_de_certeza: nota=4.0 | mínimo=5.0" in feedback


def test_missing_criterion_is_invalid_output():
    response = content.judge_output()
    response["criterios"] = response["criterios"][1:]
    with pytest.raises(InvalidLLMOutput):
        _judge(response)[0].evaluate("Texto.")


def test_criterion_without_evidence_is_invalid_output():
    response = content.judge_output()
    response["criterios"][0]["evidencias"] = []
    with pytest.raises(InvalidLLMOutput):
        _judge(response)[0].evaluate("Texto.")


def test_score_out_of_range_is_invalid_output():
    response = content.judge_output()
    response["criterios"][0]["nota"] = 11
    with pytest.raises(InvalidLLMOutput):
        _judge(response)[0].evaluate("Texto.")


def test_self_reported_approval_from_llm_is_ignored():
    response = content.judge_output(score=3.0)
    response["aprovado"] = True  # o juiz não decide a aprovação
    r = _judge(response)[0].evaluate("Texto.")
    assert r.aprovado is False
