"""Redundancy metrics (detectam padding e repetição)."""
from __future__ import annotations

from collections import Counter

from src.evaluation.text_utils import sentences as split_sentences, trigrams as text_trigrams


def sentences(text: str) -> list[str]:
    return split_sentences(text)


def _key(sentence: str) -> str:
    return " ".join(sentence.lower().split()).rstrip(".!?")


def sentence_repetition_ratio(text: str) -> float:
    """Fração das frases que repetem uma frase anterior (0 = nenhuma repetida)."""
    lines = [_key(s) for s in sentences(text)]
    if not lines:
        return 0.0
    return 1 - (len(set(lines)) / len(lines))


def repeated_sentences(text: str) -> list[str]:
    counts = Counter(_key(s) for s in sentences(text))
    return [s for s, c in counts.items() if c > 1]


def trigram_repetition_ratio(text: str) -> float:
    """Fração de trigramas que já tinham aparecido antes no mesmo texto."""
    grams = text_trigrams(text)
    if len(grams) < 4:
        return 0.0
    counts = Counter(grams)
    duplicates = sum(c - 1 for c in counts.values() if c > 1)
    return duplicates / len(grams)
