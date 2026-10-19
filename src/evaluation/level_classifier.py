"""Classificador de nível por faixas de legibilidade e densidade de termos (seção 4.7).

As faixas vêm de config/limiares.yaml. Texto fora de todas as faixas, ou que combina a legibilidade
de um nível com a densidade de outro, é 'indistinto' (outcome válido e registrado).
"""
from __future__ import annotations

from src.evaluation.flesch_ptbr import evaluate_level, flesch_reading_ease_pt
from src.evaluation.term_density import term_density_per_100_words
from src.evaluation.thresholds import as_thresholds

LEVELS = ("iniciante", "intermediario", "avancado")


def density_in_band(density: float, level: str, thresholds) -> bool:
    t = as_thresholds(thresholds)
    if level == "iniciante":
        return density <= t.req("densidade_iniciante_max")
    if level == "intermediario":
        return t.req("densidade_intermediaria_min") <= density <= t.req("densidade_intermediaria_max")
    if level == "avancado":
        return density >= t.req("densidade_avancado_min")
    return False


def classify_scores(flesch: float, density: float, thresholds=None) -> str:
    matches = [lvl for lvl in LEVELS if evaluate_level(flesch, lvl, thresholds) and density_in_band(density, lvl, thresholds)]
    return matches[0] if len(matches) == 1 else "indistinto"


def classify_level(text: str, technical_terms: list[str], thresholds=None) -> str:
    """`technical_terms`: formas dos termos técnicos (glossary.technical_forms())."""
    return classify_scores(flesch_reading_ease_pt(text), term_density_per_100_words(text, technical_terms), thresholds)
