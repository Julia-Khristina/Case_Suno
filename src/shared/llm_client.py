"""LLM client with live and simulated modes."""
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .cache import VersionedCache
from .logging import get_logger

logger = get_logger("llm_client")


class LLMClient:
    def __init__(self, mode: Optional[str] = None, response_dir: str = "tests/fixtures/llm_responses") -> None:
        self.mode = mode or os.getenv("LLM_MODE", "simulated")
        self.response_dir = Path(response_dir)
        self.cache = VersionedCache()
        self.last_usage: dict[str, int] = {}

    def _cache_key(self, prompt: str, model_id: Optional[str], schema_name: str, extra: Dict[str, Any]) -> str:
        return self.cache.build_key(prompt, model_id, schema_name, extra)

    def generate(
        self,
        prompt: str,
        schema_name: str = "text",
        model_id: Optional[str] = None,
        temperature: float = 0.2,
        cache_parts: Optional[Dict[str, Any]] = None,
    ) -> Any:
        cache_parts = cache_parts or {}
        key = self._cache_key(prompt, model_id, schema_name, cache_parts)
        cached = self.cache.get(key)
        if cached is not None:
            logger.info("LLM cache hit: %s", key[:12])
            self.last_usage = {
                "prompt_tokens": max(1, len(prompt.split())),
                "completion_tokens": max(1, len(str(cached).split())),
            }
            return cached

        if self.mode == "simulated":
            raw = self._load_simulated_response(key)
            if isinstance(raw, dict) and "response" in raw:
                self.last_usage = dict(raw.get("usage", {}))
                result = raw["response"]
            elif isinstance(raw, dict) and "usage" in raw:
                self.last_usage = dict(raw.get("usage", {}))
                result = {key: value for key, value in raw.items() if key != "usage"}
            else:
                self.last_usage = {}
                result = raw
        elif self.mode == "live":
            raise RuntimeError("Live mode is not implemented in Block 0; configure provider in later blocks.")
        else:
            raise ValueError(f"Unsupported LLM mode: {self.mode}")

        if not self.last_usage:
            self.last_usage = {
                "prompt_tokens": max(1, len(prompt.split())),
                "completion_tokens": max(1, len(str(result).split())),
            }
        self.cache.set(key, result)
        return result

    def _load_simulated_response(self, key: str) -> Any:
        path = self.response_dir / f"{key}.json"
        if not path.exists():
            raise FileNotFoundError(f"Simulated response not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def hash_prompt(prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()