"""Coverage checks and beginner term window (seção 4.7)."""
from __future__ import annotations

import re
from typing import Iterable

from src.evaluation.text_utils import content_stems, words

EXPLANATION_CUES = ("ou seja", "isto é", "isso é", "que é", "que são", "significa", "chamad", "é a ", "é o ", "são os ",
                    "são as ", "(", " — ", " – ", ": ")


def point_is_covered(text: str, title: str, assertion_texts: Iterable[str] = (), min_overlap: float = 0.5) -> bool:
    """Um ponto central está coberto se o texto contém a maior parte das palavras de conteúdo do título
    ou de alguma das suas afirmações (comparação por radical, ignorando palavras vazias)."""
    text_stems = content_stems(text)
    for unit in [title, *assertion_texts]:
        stems = content_stems(unit)
        if stems and len(stems & text_stems) / len(stems) >= min_overlap:
            return True
    return False


def main_points_coverage(text: str, main_point_titles: list[str], assertions_by_point: list[list[str]] | None = None,
                         min_overlap: float = 0.5) -> int:
    assertions_by_point = assertions_by_point or [[] for _ in main_point_titles]
    return sum(point_is_covered(text, t, a, min_overlap) for t, a in zip(main_point_titles, assertions_by_point))


def uncovered_points(text: str, points: list[dict], min_overlap: float = 0.5) -> list[str]:
    """`points`: [{"id", "title", "assertions": [texto, ...]}]. Retorna os ids não cobertos."""
    return [p["id"] for p in points if not point_is_covered(text, p["title"], p.get("assertions", []), min_overlap)]


def beginner_term_has_explanation_window(text: str, term: str, glossary_explanation: str | None = None,
                                         window_words: int = 20) -> bool:
    """Compatibilidade: True se toda ocorrência do termo tem explicação na janela."""
    return not _unexplained_occurrences(text, [term], {term.lower(): glossary_explanation}, window_words)


def _unexplained_occurrences(text: str, forms: list[str], explanations: dict[str, str | None], window: int) -> list[str]:
    low = text.lower()
    missing = []
    for form in sorted(set(f.lower() for f in forms), key=len, reverse=True):
        for m in re.finditer(rf"(?<!\w){re.escape(form)}(?!\w)", low):
            before = " ".join(low[:m.start()].split()[-6:])
            after_words = low[m.end():].split()[:window]
            after = " " + " ".join(after_words)
            approved = explanations.get(form)
            apposition = re.match(r"\s*,\s*(o|a|os|as|um|uma)\s", low[m.end():]) is not None
            has_cue = apposition or any(cue in after for cue in EXPLANATION_CUES) or \
                any(cue in before[-25:] for cue in ("(", "chamad"))
            matches_glossary = bool(approved) and len(content_stems(approved) & content_stems(after)) >= 2
            if not (has_cue or matches_glossary):
                missing.append(form)
                break  # uma ocorrência sem explicação basta para o termo
            break  # basta explicar na primeira ocorrência
    return missing


def unexplained_terms(text: str, glossary, window_words: int) -> list[str]:
    """Termos técnicos (intermediário/avançado) usados sem explicação na janela de palavras (nível Iniciante)."""
    forms: list[str] = []
    explanations: dict[str, str | None] = {}
    seen_entries = set()
    for entry, form, _pos in glossary.find_in_text(text, technical_only=True):
        if entry.termo in seen_entries:
            continue  # explicar a primeira ocorrência de cada termo basta
        seen_entries.add(entry.termo)
        forms.append(form)
        explanations[form.lower()] = entry.explicacao_iniciante if entry.is_approved else None
    return sorted(set(_unexplained_occurrences(text, forms, explanations, window_words)))


def jargon_terms(text: str, glossary) -> list[str]:
    return sorted({form for _e, form, _p in glossary.find_in_text(text, technical_only=True)})


def unique_words_ratio(text: str) -> float:
    ws = words(text)
    return len(set(ws)) / len(ws) if ws else 1.0
