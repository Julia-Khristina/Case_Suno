"""Deterministic ranking for collected cards."""

from datetime import date, datetime
from typing import Any

SOURCE_PRIORITY = {"BCB": 1, "CVM": 2, "B3": 3, "IBGE": 4, "Forbes": 5}


def _field(item: Any, name: str):
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


def _source_score(item: Any) -> int:
    source = _field(item, "nome_fonte") or _field(item, "source_name")
    priority = SOURCE_PRIORITY.get(str(source), 99)
    return max(0, 40 - priority * 5)


def _recency_score(item: Any) -> int:
    value = _field(item, "data_publicacao") or _field(item, "card_date")
    if not value:
        return 5
    try:
        if isinstance(value, datetime):
            parsed = value.date()
        elif isinstance(value, date):
            parsed = value
        else:
            parsed = date.fromisoformat(str(value)[:10])
        delta = (date.today() - parsed).days
        if delta <= 0:
            return 30
        if delta <= 1:
            return 20
        if delta <= 3:
            return 10
        if delta <= 7:
            return 5
    except ValueError:
        pass
    return 0


def score_card(item: Any) -> int:
    score = _source_score(item)
    score += _recency_score(item)
    if _field(item, "titulo") or _field(item, "title"):
        score += 10
    if _field(item, "descricao") or _field(item, "description"):
        score += 10
    if _field(item, "url") or _field(item, "source_url"):
        score += 5
    return score


def rank_items(items: list[Any], limit: int | None = None) -> list[Any]:
    ranked = sorted(items, key=lambda item: (-score_card(item), _source_priority(item), str(_field(item, "titulo") or _field(item, "title") or "")))
    return ranked if limit is None else ranked[:limit]


def _source_priority(item: Any) -> int:
    source = _field(item, "nome_fonte") or _field(item, "source_name")
    return SOURCE_PRIORITY.get(str(source), 99)