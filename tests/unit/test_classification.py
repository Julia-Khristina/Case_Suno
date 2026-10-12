from src.admission.classification import classify_text

GLOSSARY_TERMS = ["selic", "ipca", "copom", "juros", "taxa"]


def _financial_text():
    base = "selic ipca copom juros taxa " * 45
    return base + " O Copom aumentou a taxa Selic. " + ("palavra " * 50)


def test_financial_rule_passes_with_enough_terms_and_words():
    result = classify_text(_financial_text(), GLOSSARY_TERMS)
    assert result["financial_rule_passed"] is True
    assert result["is_financial"] is True
    assert result["distinct_glossary_terms"] >= 5
    assert result["word_count"] >= 200


def test_financial_rule_fails_for_short_or_poor_text():
    result = classify_text("texto curto sem termos", GLOSSARY_TERMS)
    assert result["financial_rule_passed"] is False
    assert result["is_financial"] is False


def test_structured_type_is_metadata_only():
    result = classify_text(_financial_text(), GLOSSARY_TERMS)
    assert result["structured_type"] in {"financeiro", "possivelmente_financeiro", "nao_financeiro"}