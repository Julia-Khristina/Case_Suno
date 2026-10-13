"""Flesch Reading Ease adapted to Brazilian Portuguese."""
import re

VOWEL_PATTERN = re.compile(r"[aeiouáéíóúâêîôûàèìòùãõ]", re.IGNORECASE)


def count_syllables(word: str) -> int:
    count = len(VOWEL_PATTERN.findall(word))
    return count if count > 0 else 1


def sentence_count(text: str) -> int:
    parts = [part for part in re.split(r"[.!?]+", text) if part.strip()]
    return max(len(parts), 1)


def word_list(text: str) -> list[str]:
    return re.findall(r"\w+", text, flags=re.UNICODE)


def flesch_reading_ease_pt(text: str) -> float:
    words = word_list(text)
    if not words:
        return 0.0
    sentences = sentence_count(text)
    syllables = sum(count_syllables(word) for word in words)
    return 206.835 - 1.015 * (len(words) / sentences) - 84.6 * (syllables / len(words))


def evaluate_level(flesch: float, level: str, thresholds: dict[str, float] | None = None) -> bool:
    thresholds = thresholds or {}
    if level == "iniciante":
        return flesch >= thresholds.get("flesch_iniciante_min", 55)
    if level == "intermediario":
        return thresholds.get("flesch_intermediario_min", 40) <= flesch <= thresholds.get("flesch_intermediario_max", 55)
    if level == "avancado":
        return flesch <= thresholds.get("flesch_avancado_max", 40)
    return False