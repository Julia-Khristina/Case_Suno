"""Financial classification with deterministic rule as arbiter."""
from typing import Iterable

from src.glossary.reader import count_distinct_terms

FINANCIAL_KEYWORDS = (
    "selic", "ipca", "copom", "bcb", "cvm", "b3", "inflacao", "juros", "taxa", "dividendos",
    "inflação", "copom", "ata", "fato relevante", "release", "resultado",
)

MIN_FINANCIAL_WORDS = 200
MIN_DISTINCT_GLOSSARY_TERMS = 5


def _normalize(text: str) -> str:
    return text.lower()


def structured_document_type(text: str, distinct_terms: int) -> str:
    lowered = _normalize(text)
    keyword_hits = sum(1 for keyword in FINANCIAL_KEYWORDS if keyword in lowered)
    if keyword_hits >= 3 and distinct_terms >= 3:
        return "financeiro"
    if keyword_hits >= 1 or distinct_terms >= 1:
        return "possivelmente_financeiro"
    return "nao_financeiro"


def classify_text(
    text: str,
    glossary_terms: Iterable[str],
    min_words: int = MIN_FINANCIAL_WORDS,
    min_terms: int = MIN_DISTINCT_GLOSSARY_TERMS,
) -> dict:
    word_count = len(text.split())
    distinct_terms = count_distinct_terms(text, glossary_terms)
    financial_rule_passed = word_count >= min_words and distinct_terms >= min_terms
    return {
        "is_financial": financial_rule_passed,
        "financial_rule_passed": financial_rule_passed,
        "distinct_glossary_terms": distinct_terms,
        "word_count": word_count,
        "structured_type": structured_document_type(text, distinct_terms),
    }