"""Deduplication of collected cards/stories."""

import re
from typing import Any

SOURCE_PRIORITY = {"BCB": 1, "CVM": 2, "B3": 3, "IBGE": 4, "Forbes": 5}


def _source_priority(item: dict[str, Any] | Any) -> int:
    name = _item_field(item, "nome_fonte") or _item_field(item, "source_name")
    return int(SOURCE_PRIORITY.get(str(name), 99))


def _item_field(item: Any, field: str):
    if isinstance(item, dict):
        return item.get(field)
    return getattr(item, field, None)


def _set_field(item: Any, field: str, value: Any) -> None:
    if isinstance(item, dict):
        item[field] = value
    else:
        setattr(item, field, value)


def normalize_title(value: str | None) -> str:
    text = re.sub(r"[^0-9a-zÃ¡Ã©Ã­Ã³ÃºÃ¢ÃªÃ´Ã£ÃµÃ§ ]", " ", (value or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _to_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return dict(item)
    if hasattr(item, "to_dict"):
        return item.to_dict()
    return dict(getattr(item, "__dict__", {}))


def deduplicate_items(items: list[Any]) -> list[dict[str, Any] | Any]:
    """Keep one representative per similar title, preferring primary sources."""
    groups: dict[str, list[Any]] = {}
    for item in items:
        key = normalize_title(_item_field(item, "titulo") or _item_field(item, "title"))
        if not key:
            continue
        groups.setdefault(key, []).append(item)

    result: list[Any] = []
    for group in groups.values():
        ordered = sorted(group, key=_source_priority)
        primary = ordered[0]
        related = [_to_dict(item) for item in ordered[1:]]
        if isinstance(primary, dict):
            primary["relacionados"] = related
        else:
            primary.relacionados = related
        result.append(primary)
    return result


# Backwards-friendly names
deduplicate = deduplicate_items
deduplicate_cards = deduplicate_items
