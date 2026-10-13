"""Coverage checks and beginner term window."""
import re


def main_points_coverage(text: str, main_point_titles: list[str]) -> int:
    lowered = text.lower()
    covered = 0
    for title in main_point_titles:
        title_lower = title.lower()
        if title_lower in lowered:
            covered += 1
            continue
        tokens = [token for token in title_lower.split() if token]
        matches = sum(1 for token in tokens if token in lowered)
        if tokens and matches >= max(1, len(tokens) // 2):
            covered += 1
    return covered


def beginner_term_has_explanation_window(text: str, term: str, glossary_explanation: str, window_words: int = 20) -> bool:
    words = text.split()
    lowered = text.lower()
    pos = lowered.find(term.lower())
    if pos == -1:
        return True
    word_index = len(text[:pos].split())
    start = max(0, word_index - window_words)
    end = min(len(words), word_index + window_words + 1)
    window = " ".join(words[start:end]).lower()
    return glossary_explanation.lower() in window or term.lower() not in window