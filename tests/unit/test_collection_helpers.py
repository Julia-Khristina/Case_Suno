from src.collection.cleaner import clean_html_text
from src.collection.dedup import deduplicate_items
from src.collection.ranker import rank_items, score_card
from src.collection.card_builder import build_card, categorize_item


def test_clean_html_text():
    assert clean_html_text("<b>Sel (ic) </b> &amp; IPCA") == "Sel (ic) & IPCA"


def test_dedup_keeps_primary_source():
    items = [
        {"titulo": "Copom mantem Selic", "nome_fonte": "Forbes", "url": "https://forbes"},
        {"titulo": "Copom mantem Selic", "nome_fonte": "BCB", "url": "https://bcb"},
    ]
    result = deduplicate_items(items)
    assert len(result) == 1
    assert result[0]["nome_fonte"] == "BCB"


def test_score_card_and_rank():
    item = {"titulo": "IPCA", "nome_fonte": "BCB", "descricao": "inflacao", "url": "u", "data_publicacao": "2026-10-13"}
    ranked = rank_items([item], limit=1)
    assert ranked
    assert score_card(item) > 0


def test_build_card():
    item = {"titulo": "IPCA sobe", "nome_fonte": "BCB", "tipo_fonte": "primaria", "url": "u"}
    card = build_card(item)
    assert card["titulo"] == "IPCA sobe"
    assert card["motivo_entrada"]
    assert categorize_item({"titulo": "historia em andamento"}) == "em_andamento"