"""Pipeline state definition."""

from typing import Any
from pydantic import BaseModel


class PipelineState(BaseModel):
    execution_id: str | None = None
    document: dict[str, Any] | None = None
    selected_levels: list[str] = []
    config_versions: dict[str, str] = {}
    extraction: dict[str, Any] | None = None
    generated_outputs: dict[str, Any] = {}
    attempt_history: list[dict[str, Any]] = []
    deterministic_evaluation: dict[str, Any] | None = None
    judge_evaluation: dict[str, Any] | None = None
    human_decision: str | None = None
    token_count: int = 0
    errors: list[str] = []