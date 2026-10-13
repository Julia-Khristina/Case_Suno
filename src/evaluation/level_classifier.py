"""Level classifier based on Flesch and term density."""
from src.evaluation.flesch_ptbr import flesch_reading_ease_pt
from src.evaluation.term_density import term_density_per_100_words


def classify_level(text: str, glossary_terms: list[str]) -> str:
    flesch = flesch_reading_ease_pt(text)
    density = term_density_per_100_words(text, glossary_terms)

    if flesch >= 55 and density <= 3:
        return "iniciante"
    if 40 <= flesch <= 55 and 3 <= density <= 8:
        return "intermediario"
    if flesch <= 40 and density >= 8:
        return "avancado"
    return "indistinto"