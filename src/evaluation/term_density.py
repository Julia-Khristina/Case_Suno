"""Domain Term Density Score.

Densidade = ocorrências de termos técnicos do glossário (nível intermediário ou avançado) por 100 palavras.
A versão anterior contava termos distintos, o que tornava a faixa do Avançado (> 8) inalcançável.
"""
from __future__ import annotations

import re

from src.evaluation.text_utils import word_count


def matching_terms(text: str, glossary_terms: list[str]) -> list[str]:
    lowered = text.lower()
    return [t for t in glossary_terms if re.search(rf"(?<!\w){re.escape(t.lower())}(?!\w)", lowered)]


def term_occurrences(text: str, glossary_terms: list[str]) -> int:
    """Ocorrências sem sobreposição; formas mais longas têm prioridade ("taxa selic" antes de "selic")."""
    lowered = text.lower()
    taken: list[tuple[int, int]] = []
    count = 0
    for term in sorted(set(t.lower() for t in glossary_terms if t), key=len, reverse=True):
        for m in re.finditer(rf"(?<!\w){re.escape(term)}(?!\w)", lowered):
            if any(m.start() < b and m.end() > a for a, b in taken):
                continue
            taken.append(m.span())
            count += 1
    return count


def term_density_per_100_words(text: str, glossary_terms: list[str]) -> float:
    words = word_count(text)
    if words == 0:
        return 0.0
    return term_occurrences(text, glossary_terms) / words * 100.0


def technical_density(text: str, glossary) -> float:
    """Densidade usando só os termos técnicos (intermediário/avançado) de um `Glossary`."""
    return term_density_per_100_words(text, glossary.technical_forms())
