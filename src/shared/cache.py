"""Versioned in-memory cache for Block 0."""
import hashlib
import json
from typing import Any, Dict


class VersionedCache:
    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}

    def build_key(self, *parts: Any) -> str:
        serialized = json.dumps(parts, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Any:
        return self._store.get(key)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def clear(self) -> None:
        self._store.clear()