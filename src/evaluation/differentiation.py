"""Level differentiation metrics."""
from __future__ import annotations

import re
from typing import Iterable


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", (text or "").lower(), flags=re.UNICODE)


def trigrams(text: str) -> set[tuple[str, str, str]]:
    words = _tokenize(text)
    return {tuple(words[i:i + 3]) for i in range(len(words) - 2)}


def trigram_overlap_ratio(left: str, right: str) -> float:
    left_trigrams = trigrams(left)
    right_trigrams = trigrams(right)
    union = left_trigrams | right_trigrams
    if not union:
        return 1.0
    return len(left_trigrams & right_trigrams) / len(union)


def assert_differentiation(outputs: dict[str, str], threshold: float = 0.7) -> None:
    levels = list(outputs)
    for index, left_level in enumerate(levels):
        for right_level in levels[index + 1 :]:
            ratio = trigram_overlap_ratio(outputs[left_level], outputs[right_level])
            if ratio > threshold:
                raise AssertionError(
                    f"overlap above threshold for {left_level}/{right_level}: {ratio:.2f} > {threshold:.2f}"
                )
