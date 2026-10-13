"""Analytical text generation."""
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.shared.llm_client import LLMClient
from src.extraction.models import ExtractionResult
from src.generation.models import AnalyticalText

PROMPT_TEMPLATE = (Path(__file__).resolve().parent / "prompts" / "text" / "analytical.txt").read_text(encoding="utf-8")


class AnalyticalTextGenerator:
    def __init__(
        self,
        llm_client: LLMClient | None = None,
        model_id: str | None = None,
        word_min: int = 350,
        word_max: int = 500,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.model_id = model_id
        self.word_min = word_min
        self.word_max = word_max

    def generate(
        self,
        extraction: ExtractionResult,
        level: str,
        source_text: str,
        feedback: str | None = None,
        glossary_terms: list[str] | None = None,
        forbidden_terms: list[str] | None = None,
    ) -> AnalyticalText:
        main_points = "\n".join(f"- {point.title}" for point in extraction.main_points)
        numeric_data = "\n".join(
            f"- {item.indicator}: {item.value} {item.unit or ''} ({item.reference_period or ''})".strip()
            for item in extraction.numeric_data
        )
        prompt = PROMPT_TEMPLATE.format(
            level=level,
            word_min=self.word_min,
            word_max=self.word_max,
            main_points=main_points or "- (sem pontos centrais extraidos)",
            numeric_data=numeric_data or "- (sem dados numericos extraidos)",
            glossary_terms=", ".join(glossary_terms or []),
            forbidden_terms=", ".join(forbidden_terms or []),
            feedback=feedback or "(nenhum)",
        )
        prompt += f"\n\nTexto analitico fonte:\n{source_text}\n"
        response = self.llm_client.generate(
            prompt,
            schema_name="analytical_text",
            model_id=self.model_id,
            cache_parts={"level": level, "prompt_version": "block4"},
        )
        try:
            return AnalyticalText.model_validate(response)
        except ValidationError as exc:
            raise ValueError(f"Resposta invalida de geracao: {exc}") from exc