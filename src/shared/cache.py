"""Versioned cache: in-memory, optionally persisted on disk (CACHE_DIR) for live/record runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict


class VersionedCache:
    def __init__(self, directory: str | Path | None = None) -> None:
        self._store: Dict[str, Any] = {}
        self.directory = Path(directory) if directory else None
        if self.directory:
            self.directory.mkdir(parents=True, exist_ok=True)

    def build_key(self, *parts: Any) -> str:
        serialized = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _path(self, key: str) -> Path | None:
        return self.directory / f"{key}.json" if self.directory else None

    def get(self, key: str) -> Any:
        if key in self._store:
            return self._store[key]
        path = self._path(key)
        if path is not None and path.exists():
            value = json.loads(path.read_text(encoding="utf-8"))
            self._store[key] = value
            return value
        return None

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value
        path = self._path(key)
        if path is not None:
            path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def clear(self) -> None:
        self._store.clear()
