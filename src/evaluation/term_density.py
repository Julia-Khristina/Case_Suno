"""Domain Term Density Score."""
import re


def matching_terms(text: str, glossary_terms: list[str]) -> list[str]:
    lowered = text.lower()
    result: list[str] = []
    for term in glossary_terms:
        if re.search(rf"\b{re.escape(term.lower())}\b", lowered):
            result.append(term)
    return result


def term_density_per_100_words(text: str, glossary_terms: list[str]) -> float:
    words = len(re.findall(r"\w+", text, flags=re.UNICODE))
    if words == 0:
        return 0.0
    return len(matching_terms(text, glossary_terms)) / words * 100.0