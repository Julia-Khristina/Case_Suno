"""Structured LLM-as-a-judge."""
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from src.shared.llm_client import LLMClient


class JudgeCriterionScore(BaseModel):
    criterion: str
    score: float
    justification: str


class JudgeResult(BaseModel):
    rubric_version: str
    judge_model_id: str
    scores: dict[str, float]
    justification: str
    text_length: int
    evidence: list[str] = []


class LLMJudge:
    def __init__(
        self,
        llm_client: LLMClient | None = None,
        model_id: str | None = None,
        rubric_path: str | Path = "src/evaluation/rubric.yaml",
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.model_id = model_id or "judge-model"
        self.rubric = self._load_rubric(rubric_path)
        self.rubric_version = self.rubric.get("versao", "0.1")
        self.last_usage: dict[str, int] = {}

    def _load_rubric(self, path: str | Path) -> dict:
        file_path = Path(path)
        if not file_path.exists():
            return {"versao": "0.1", "criterios": [], "prompt": ""}
        with file_path.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {}

    def evaluate(
        self,
        generated_text: str,
        source_text: str = "",
        level: str | None = None,
        main_points: list[str] | None = None,
        evidence: list[str] | None = None,
    ) -> JudgeResult:
        criteria = self.rubric.get("criterios", [])
        prompt = (
            f"{self.rubric.get('prompt', '')}\n\n"
            f"Rubrica versao: {self.rubric_version}\n"
            f"Nivel alvo: {level or 'nao_informado'}\n"
            f"Criterios: {', '.join(criteria)}\n"
            f"Pontos centrais esperados: {', '.join(main_points or [])}\n"
            f"Texto gerado:\n{generated_text}\n\n"
            f"Texto fonte (resumo):\n{source_text[:2000]}\n"
        )
        response = self.llm_client.generate(
            prompt,
            schema_name="judge",
            model_id=self.model_id,
            cache_parts={"rubric_version": self.rubric_version, "level": level},
        )
        self.last_usage = getattr(self.llm_client, "last_usage", {}) or {}
        parsed = JudgeResult.model_validate(response)
        parsed.rubric_version = parsed.rubric_version or self.rubric_version
        parsed.judge_model_id = parsed.judge_model_id or self.model_id
        parsed.text_length = parsed.text_length or len(generated_text.split())
        parsed.evidence = parsed.evidence or evidence or []
        return parsed