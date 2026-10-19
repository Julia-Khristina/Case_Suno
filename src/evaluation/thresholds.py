"""Threshold loading helpers.

Todos os limiares vêm de config/limiares.yaml. `Thresholds.get_required` falha de forma explícita
quando uma chave falta, para nenhum limiar ficar escondido em valor padrão no código.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_PATH = "config/limiares.yaml"


class MissingThreshold(KeyError):
    """Chave obrigatória ausente em config/limiares.yaml."""


class Thresholds(dict):
    """Dicionário de limiares com acesso obrigatório."""

    def req(self, key: str) -> Any:
        if key not in self:
            raise MissingThreshold(f"Limiar obrigatório ausente em config/limiares.yaml: {key}")
        return self[key]


def load_thresholds(path: str | Path = DEFAULT_PATH) -> Thresholds:
    file_path = Path(path)
    if not file_path.exists():
        return Thresholds()
    with file_path.open("r", encoding="utf-8") as file:
        return Thresholds(yaml.safe_load(file) or {})


def as_thresholds(value: dict | None) -> Thresholds:
    """Normaliza um dicionário vindo do estado; vazio → carrega o YAML."""
    if isinstance(value, Thresholds) and value:
        return value
    if value:
        return Thresholds(value)
    return load_thresholds()
