"""Threshold loading helpers."""
from pathlib import Path
import yaml


def load_thresholds(path: str | Path = "config/limiares.yaml") -> dict:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}