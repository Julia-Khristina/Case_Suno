"""Deterministic ranking for collected cards (seção 4.1: pontuação transparente).

Sinais: prioridade da fonte (config/coleta_fontes.yaml; primária antes de secundária), recência, força do tema
financeiro, integridade (título, descrição, link, texto completo). Diversidade: no máximo N cards por fonte.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Any


def _field(item: Any, name: str):
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


def _source_priority(item: Any) -> int:
    value = _field(item, "prioridade")
    try:
        return int(value)
    except (TypeError, ValueError):
        return 99


def _source_score(item: Any) -> int:
    score = max(0, 40 - _source_priority(item) * 5)
    if (_field(item, "tipo_fonte") or "") == "primaria":
        score += 10
    return score


def _recency_score(item: Any, today: date | None = None) -> int:
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
    except ValueError:
        return 0
    delta = ((today or date.today()) - parsed).days
    if delta <= 0:
        return 30
    if delta <= 1:
        return 20
    if delta <= 3:
        return 10
    if delta <= 7:
        return 5
    return 0


def score_card(item: Any, topic_terms: int = 0) -> int:
    score = _source_score(item) + _recency_score(item)
    score += min(topic_terms, 4) * 5  # força do tema financeiro no título/descrição
    if _field(item, "titulo") or _field(item, "title"):
        score += 10
    if _field(item, "descricao") or _field(item, "description"):
        score += 5
    if _field(item, "url") or _field(item, "source_url"):
        score += 5
    if _field(item, "conteudo"):
        score += 10
    return score


def rank_items(items: list[Any], limit: int | None = None, max_per_source: int | None = None,
               topic_terms: dict[int, int] | None = None) -> list[Any]:
    """Ordena por pontuação; com `max_per_source`, nenhuma fonte ocupa mais de N posições."""
    topic_terms = topic_terms or {}
    ranked = sorted(items, key=lambda item: (-score_card(item, topic_terms.get(id(item), 0)), _source_priority(item),
                                             str(_field(item, "titulo") or _field(item, "title") or "")))
    if max_per_source:
        per_source: Counter = Counter()
        diverse = []
        for item in ranked:
            source = _field(item, "nome_fonte") or _field(item, "source_name")
            if per_source[source] < max_per_source:
                diverse.append(item)
                per_source[source] += 1
        ranked = diverse
    return ranked if limit is None else ranked[:limit]
