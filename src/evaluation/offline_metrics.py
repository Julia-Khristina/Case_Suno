"""Offline evaluation and acceptance helpers."""

from collections import Counter
from typing import Any


def build_confusion_matrix(actual: list[str], predicted: list[str], labels: list[str] | None = None) -> dict[str, Any]:
    if not labels:
        labels = sorted(set(actual) | set(predicted))
    matrix = {label: {other: 0 for other in labels} for label in labels}
    for expected, value in zip(actual, predicted):
        if expected in matrix and value in matrix[expected]:
            matrix[expected][value] += 1
    return {"labels": labels, "matrix": matrix}


def precision_for(matrix: dict[str, Any], label: str) -> float:
    total = sum(matrix["matrix"][row][label] for row in matrix["labels"])
    if total == 0:
        return 0.0
    return matrix["matrix"][label][label] / total


def recall_for(matrix: dict[str, Any], label: str) -> float:
    total = sum(matrix["matrix"][label].values())
    if total == 0:
        return 0.0
    return matrix["matrix"][label][label] / total


def f1_for(matrix: dict[str, Any], label: str) -> float:
    precision = precision_for(matrix, label)
    recall = recall_for(matrix, label)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def acceptance_checklist() -> list[tuple[str, bool]]:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    checks = [
        ("config/glossario.yaml", (root / "config/glossario.yaml").exists()),
        ("config/limiares.yaml", (root / "config/limiares.yaml").exists()),
        ("src/pipeline/graph.py", (root / "src/pipeline/graph.py").exists()),
        ("src/collection/scheduler.py", (root / "src/collection/scheduler.py").exists()),
        ("tests/offline", (root / "tests/offline").exists()),
        ("scripts/run_offline_suite.py", (root / "scripts/run_offline_suite.py").exists()),
    ]
    return checks