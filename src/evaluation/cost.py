"""Cost and latency tracking helpers."""
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class CostRecord:
    model_id: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class CostTracker:
    def __init__(self) -> None:
        self.records: list[CostRecord] = []

    def add(self, record: CostRecord) -> None:
        self.records.append(record)

    def total_tokens(self) -> int:
        return sum(record.total_tokens for record in self.records)

    def total_latency_ms(self) -> float:
        return sum(record.latency_ms for record in self.records)

    def by_model(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for record in self.records:
            result[record.model_id] = result.get(record.model_id, 0) + record.total_tokens
        return result