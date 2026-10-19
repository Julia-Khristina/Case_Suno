"""Interface sem template, card com documento completo, glossário validado e edição humana por formato."""
from __future__ import annotations

import json

import pytest

from src.admission.models import AdmissionResult, OriginMetadata
from src.glossary.reader import Glossary, GlossaryEntry, load_glossary
from src.pipeline.nodes.human_validation import parse_edited_content
from tests.fakes import content


def _admission(text: str, status: str = "admitido") -> AdmissionResult:
    return AdmissionResult(is_partial=False, partial_reasons=[], is_financial=True, financial_rule_passed=True,
                           distinct_glossary_terms=5, word_count=len(text.split()), structured_type="ata", language="pt",
                           origin=OriginMetadata(), status=status, text=text)


def test_card_uses_full_document_from_link_never_the_description(monkeypatch):
    from src.app.components import news_cards

    monkeypatch.setattr("src.admission.service.admit_url", lambda url: _admission(content.SOURCE))
    card = {"id_card": None, "titulo": "Copom mantém Selic", "descricao": "Resumo de duas linhas.",
            "url_fonte": "https://www.bcb.gov.br/ata"}
    text, admission, error = news_cards.card_document(card)
    assert error is None and text == content.SOURCE and admission["status"] == "admitido"


def test_card_without_link_reports_error_instead_of_using_description():
    from src.app.components import news_cards

    text, _admission_result, error = news_cards.card_document({"titulo": "X", "descricao": "Resumo curto."})
    assert text == "" and "não tem link" in error


def test_card_with_paywall_is_blocked(monkeypatch):
    from src.app.components import news_cards

    monkeypatch.setattr("src.admission.service.admit_url", lambda url: _admission("Assine para continuar", "bloqueado"))
    _text, _adm, error = news_cards.card_document({"url_fonte": "https://exemplo.com"})
    assert "parcial" in error.lower()


def test_dollar_signs_are_escaped_for_streamlit_markdown():
    """Bug relatado: "R$ 12 bilhões ... R$ 1 bilhão" virava fórmula LaTeX e os cifrões sumiam."""
    from src.app.text import md_safe

    text = "O perdão de R$ 12 bilhões deve gerar impacto de R$ 1 bilhão por ano."
    assert md_safe(text) == "O perdão de R\\$ 12 bilhões deve gerar impacto de R\\$ 1 bilhão por ano."
    assert md_safe(md_safe(text)) == md_safe(text)  # idempotente
    assert md_safe(None) == ""


def test_seeded_glossary_has_levels_and_pending_status():
    glossary = load_glossary()
    assert len(glossary.termos) > 150 and glossary.hash
    selic = glossary.entry_for("Selic")
    assert selic.nivel == "intermediario" and selic.is_technical
    assert glossary.entry_for("forward guidance").nivel == "avancado"
    assert not any(e.is_approved for e in glossary.termos)  # aprovação é da autora (seção 4.5)
    assert glossary.approved_impact_explanations() == []


def test_same_variation_cannot_point_to_two_terms():
    with pytest.raises(ValueError):
        Glossary(termos=[GlossaryEntry(termo="Selic", variacoes=["taxa básica"]),
                         GlossaryEntry(termo="CDI", variacoes=["taxa básica"])])


def test_edited_carousel_and_script_are_parsed_by_format():
    carousel = {"slides": content.good_output("carrossel", "iniciante")["slides"], "linha_vermelha_nivel": "em cima"}
    parsed = parse_edited_content("carrossel", json.dumps(carousel), None)
    assert len(parsed["slides"]) == 5
    script = content.good_output("roteiro_video", "iniciante")
    for scene in script["scenes"]:
        scene["fala_falada"] = scene["fala_escrita"]
    assert len(parse_edited_content("roteiro_video", {"texto": json.dumps(script)}, None)["scenes"]) == 5
