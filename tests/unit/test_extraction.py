"""Extração e âncora (seções 4.3 e 4.4): trecho exato, descarte, ids por parte, agregação e termos detectados."""
from __future__ import annotations

import copy

from src.extraction.extractor import Extractor, locate_span
from src.extraction.models import ExtractionResult
from tests.fakes import content
from tests.fakes.llm import FakeLLMClient


def test_extraction_keeps_only_assertions_with_exact_span_in_source():
    result = Extractor(llm_client=FakeLLMClient()).extract(content.SOURCE)
    assert isinstance(result, ExtractionResult)
    ids = [a.id for a in result.assertions]
    assert "a9" not in ids  # trecho inexistente na fonte: descartado
    assert any("descartada" in w for w in result.warnings)
    for assertion in result.assertions:
        span = assertion.source_span
        assert content.SOURCE[span.start:span.end] == span.text


def test_span_tolerates_whitespace_but_not_paraphrase():
    source = "O Copom decidiu,  por unanimidade,\nmanter a Selic."
    assert locate_span(source, "decidiu, por unanimidade, manter a Selic") is not None
    assert locate_span(source, "decidiu cortar a Selic") is None


def test_detected_terms_include_glossary_matches_and_source_complexity():
    result = Extractor(llm_client=FakeLLMClient()).extract(content.SOURCE)
    assert {"Selic", "IPCA", "Copom"} <= set(result.detected_terms)
    assert result.source_complexity.flesch is not None and result.source_complexity.term_density is not None


def test_long_document_gets_prefixed_ids_and_aggregation_pass():
    long_text = (content.SOURCE + "\n\n") * 3  # > 3000 caracteres: mais de uma parte
    chunk = copy.deepcopy(content.EXTRACTION)
    aggregation = {"main_points": [
        {"id": "x", "order": 1, "title": "Selic mantida em 10,50%", "assertion_ids": ["c1_a1", "c2_a1"]},
        {"id": "y", "order": 2, "title": "IPCA acima da meta", "assertion_ids": ["c1_a2"]},
        {"id": "z", "order": 3, "title": "Riscos fiscais e de oferta", "assertion_ids": ["c1_a5", "inexistente"]},
    ]}
    client = FakeLLMClient(responses={"extraction": [chunk], "extraction_aggregate": [aggregation]})
    result = Extractor(llm_client=client).extract(long_text)
    schemas = [c["schema"] for c in client.calls]
    assert schemas.count("extraction") >= 2 and schemas[-1] == "extraction_aggregate"
    assert len({a.id for a in result.assertions}) == len(result.assertions)  # ids únicos entre partes
    assert [p.id for p in result.main_points] == ["p1", "p2", "p3"]
    assert result.main_points[2].assertion_ids == ["c1_a5"]  # id inexistente removido


def test_malformed_lists_from_the_model_are_normalized():
    """Formato observado ao vivo com gpt-oss-20b: strings soltas intercaladas na lista ("a2", ":", {...})."""
    first, second, third = (copy.deepcopy(a) for a in content.EXTRACTION["assertions"][:3])
    second.pop("id")
    third.pop("id")
    response = copy.deepcopy(content.EXTRACTION)
    response["assertions"] = [first, "a2", ":", second, "a3", ":", third]
    response["numeric_data"] = {"n1": {k: v for k, v in content.EXTRACTION["numeric_data"][0].items() if k != "id"}}
    result = Extractor(llm_client=FakeLLMClient(responses={"extraction": [response]})).extract(content.SOURCE)
    assert [a.id for a in result.assertions] == ["a1", "a2", "a3"]
    assert [n.id for n in result.numeric_data] == ["n1"]


def test_invalid_extraction_gets_one_retry_with_error_feedback():
    client = FakeLLMClient(responses={"extraction": [{"assertions": "isto não é lista de objetos", "main_points": 3},
                                                     copy.deepcopy(content.EXTRACTION)]})
    result = Extractor(llm_client=client).extract(content.SOURCE)
    assert len(result.main_points) == 3
    assert len(client.prompts) == 2 and "A resposta anterior foi inválida" in client.prompts[1]["prompt"]


def test_extraction_fails_after_two_invalid_answers():
    import pytest
    from src.shared.llm_client import InvalidLLMOutput

    client = FakeLLMClient(responses={"extraction": [{"main_points": "x"}]})
    with pytest.raises(InvalidLLMOutput):
        Extractor(llm_client=client).extract(content.SOURCE)
    assert len(client.prompts) == 2


def test_chunk_prompt_treats_content_as_data():
    client = FakeLLMClient()
    Extractor(llm_client=client).extract(content.SOURCE)
    assert "<documento>" in client.prompts[0]["prompt"]
    assert "nunca instrução" in client.prompts[0]["system"]
