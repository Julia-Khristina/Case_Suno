"""Language detection with deterministic heuristics."""
import re

PORTUGUESE_MARKERS = [" a ", " o ", " de ", " da ", " do ", " em ", " para ", " com ", " não ", " que ", " uma ", " um ", " os ", " as ", " na ", " no "]
ENGLISH_MARKERS = [" the ", " and ", " is ", " of ", " to ", " in ", " for "]


def _count_markers(text: str, markers: list[str]) -> int:
    lowered = text.lower()
    return sum(lowered.count(marker) for marker in markers)


def detect_language(text: str) -> str:
    if not text.strip():
        return "desconhecido"
    portuguese_hits = _count_markers(text, PORTUGUESE_MARKERS)
    english_hits = _count_markers(text, ENGLISH_MARKERS)
    if english_hits > portuguese_hits:
        return "desconhecido"
    if portuguese_hits >= 1:
        return "pt"
    return "desconhecido"