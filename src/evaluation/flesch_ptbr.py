"""Flesch Reading Ease adaptado ao português do Brasil.

Fórmula de Martins et al. (1996): FRE = 248,835 − 1,015 × (palavras/frases) − 84,6 × (sílabas/palavras).
A versão anterior usava os coeficientes do inglês (206,835) e contava cada vogal como sílaba, o que dava
valores negativos para textos simples em português.
"""
from __future__ import annotations

import re

from src.evaluation.text_utils import WORD_RE, normalize

VOWELS = set("aeiouáéíóúâêôãõàü")
STRONG = set("aeoáéóâêôãõà")
ACCENTED = set("áéíóúâêô")


def count_syllables(word: str) -> int:
    """Contagem silábica heurística por núcleos vocálicos, com regras de ditongo e hiato do português."""
    w = word.lower()
    if not w:
        return 0
    if w.isdigit():
        return max(1, len(w))  # números são lidos por extenso; aproximação por dígito
    count = 0
    i = 0
    while i < len(w):
        if w[i] not in VOWELS:
            i += 1
            continue
        count += 1
        j = i + 1
        while j < len(w) and w[j] in VOWELS:
            prev, cur = w[j - 1], w[j]
            gu_qu = prev == "u" and j >= 2 and w[j - 2] in "gq"
            nasal = prev in "ãõ"  # ditongos nasais: mãe, põe, pão
            if cur in ACCENTED and not gu_qu:
                count += 1           # hiato com vogal tônica acentuada: sa-ú-de, pa-ís
            elif prev in STRONG and cur in STRONG and not nasal and (prev, cur) != ("a", "o"):
                count += 1           # duas vogais fortes: po-e-ta, le-ão
            elif prev in "iu" and cur in STRONG and not gu_qu and j == len(w) - 1 or (
                prev in "iu" and cur in STRONG and not gu_qu and j + 1 < len(w) and w[j + 1] == "s" and j + 2 == len(w)
            ):
                count += 1           # final átono: his-tó-ri-a, ri-os
            j += 1
        i = j
    return max(count, 1)


def sentence_count(text: str) -> int:
    parts = [part for part in re.split(r"[.!?]+(?:\s|$)|\n+", normalize(text)) if WORD_RE.search(part)]
    return max(len(parts), 1)


def word_list(text: str) -> list[str]:
    return WORD_RE.findall(normalize(text))


def flesch_reading_ease_pt(text: str) -> float:
    words = word_list(text)
    if not words:
        return 0.0
    sentences = sentence_count(text)
    syllables = sum(count_syllables(word) for word in words)
    return 248.835 - 1.015 * (len(words) / sentences) - 84.6 * (syllables / len(words))


def evaluate_level(flesch: float, level: str, thresholds) -> bool:
    from src.evaluation.thresholds import as_thresholds

    t = as_thresholds(thresholds)
    if level == "iniciante":
        return flesch >= t.req("flesch_iniciante_min")
    if level == "intermediario":
        return t.req("flesch_intermediario_min") <= flesch <= t.req("flesch_intermediario_max")
    if level == "avancado":
        return flesch <= t.req("flesch_avancado_max")
    return False
