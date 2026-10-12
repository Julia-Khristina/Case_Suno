"""Minimal glossary and alias readers."""
from pathlib import Path
from typing import Iterable

import yaml


def load_glossary_terms(path: str | Path = "config/glossario.yaml") -> list[str]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    terms = data.get("termos", [])
    if not isinstance(terms, list):
        return []
    result: list[str] = []
    for item in terms:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict) and item.get("termo"):
            result.append(str(item["termo"]))
    return result


def count_distinct_terms(text: str, terms: Iterable[str]) -> int:
    lowered = text.lower()
    matches = {term for term in terms if term and term.lower() in lowered}
    return len(matches)