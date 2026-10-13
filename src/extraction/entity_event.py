"""Entity and event normalization."""
from typing import Any


def normalize_name(name: str, aliases: dict[str, list[str]] | None = None) -> str:
    aliases = aliases or {}
    lowered = name.strip().lower()
    for canonical, values in aliases.items():
        if lowered == canonical.lower() or lowered in {value.lower() for value in values}:
            return canonical
    return name.strip()


def normalize_entities(entities: list[dict[str, Any]], aliases: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    result = []
    for entity in entities:
        name = entity.get("name", "")
        result.append({**entity, "canonical_name": normalize_name(entity.get("canonical_name", name), aliases)})
    return result


def normalize_events(events: list[dict[str, Any]], aliases: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    result = []
    for event in events:
        name = event.get("name", "")
        result.append({**event, "canonical_name": normalize_name(event.get("canonical_name", name), aliases)})
    return result