from unittest.mock import patch

from src.extraction.extractor import Extractor
from src.extraction.models import ExtractionResult

CANNED_RESPONSE = {
    "main_points": [
        {"id": "mp1", "order": 1, "title": "Ponto central", "assertion_ids": []}
    ],
    "assertions": [
        {
            "id": "a1",
            "text": "A taxa Selic subiu.",
            "type": "fato",
            "role": "impacto",
            "source_span": {"text": "A taxa Selic subiu.", "start": None, "end": None},
            "variation_declared": True,
        }
    ],
    "numeric_data": [
        {
            "id": "n1",
            "indicator": "Selic",
            "value": "10,50",
            "unit": "%",
            "reference_period": "outubro/2026",
            "source_span": {"text": "10,50%", "start": None, "end": None},
        }
    ],
    "entities": [{"id": "e1", "name": "BC", "canonical_name": "Banco Central"}],
    "events": [{"id": "ev1", "name": "Copom", "canonical_name": "Copom", "reference_date": "2026-10-13"}],
    "detected_terms": ["selic"],
    "pending_terms": [],
    "source_complexity": {"word_count": 12},
}


def test_extraction_parses_and_enriches_spans():
    text = "A taxa Selic subiu. A Selic está em 10,50% hoje."
    with patch("src.extraction.extractor.LLMClient.generate", return_value=CANNED_RESPONSE):
        extractor = Extractor(glossary_terms=[])
        result = extractor.extract(text)

    assert isinstance(result, ExtractionResult)
    assert len(result.main_points) == 1
    assert result.assertions[0].source_span.start is not None
    assert result.assertions[0].source_span.text == "A taxa Selic subiu."
    assert result.numeric_data[0].source_span.start is not None
    assert result.entities[0].canonical_name == "Banco Central"