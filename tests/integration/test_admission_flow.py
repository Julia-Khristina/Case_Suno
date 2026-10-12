from unittest.mock import patch

from src.admission.models import OriginMetadata
from src.admission.service import admit_text, admit_url, admit_pdf

FINANCIAL_TEXT = ("selic ipca copom juros taxa " * 45) + " O Copom aumentou a taxa Selic. " + ("palavra " * 50) + "."
GLOSSARY_TERMS = ["selic", "ipca", "copom", "juros", "taxa"]


def test_admit_partial_text_is_blocked():
    result = admit_text("texto curto", glossary_terms=GLOSSARY_TERMS, min_characters=500)
    assert result.status == "bloqueado"
    assert result.is_partial is True


def test_admit_financial_text_is_admitted():
    result = admit_text(FINANCIAL_TEXT, glossary_terms=GLOSSARY_TERMS)
    assert result.status == "admitido"
    assert result.financial_rule_passed is True
    assert result.language == "pt"


def test_admit_non_financial_text_returns_warning():
    result = admit_text("texto curto sem termos financeiros.", glossary_terms=GLOSSARY_TERMS, min_characters=10)
    assert result.status == "aviso"
    assert result.financial_rule_passed is False


def test_admit_url_uses_fetcher_result():
    fetched = type("Fetched", (), {
        "html": "<title>Ata</title><p>" + FINANCIAL_TEXT + "</p>",
        "title": "Ata",
        "text": FINANCIAL_TEXT,
    })()
    with patch("src.admission.service.fetch_url", return_value=fetched):
        result = admit_url("https://www.bcb.gov.br/publicacoes/atascopom/cronologicos", glossary_terms=GLOSSARY_TERMS)
    assert result.status == "admitido"
    assert result.origin.instituicao == "Banco Central"


def test_admit_pdf_uses_extracted_text():
    with patch("src.admission.service.extract_pdf_text", return_value=FINANCIAL_TEXT):
        result = admit_pdf("fake.pdf", glossary_terms=GLOSSARY_TERMS, origin=OriginMetadata(titulo="PDF teste"))
    assert result.status == "admitido"
    assert result.origin.titulo == "PDF teste"