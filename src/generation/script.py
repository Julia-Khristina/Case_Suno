"""Short video script generation."""
from pathlib import Path

from pydantic import ValidationError

from src.shared.llm_client import LLMClient
from src.extraction.models import ExtractionResult
from src.generation.models import Script


PROMPT_TEMPLATE = (Path(__file__).resolve().parent / "prompts" / "script" / "script.txt").read_text(encoding="utf-8")


class ScriptGenerator:
    def __init__(self, llm_client: LLMClient | None = None, model_id: str | None = None) -> None:
        self.llm_client = llm_client or LLMClient()
        self.model_id = model_id

    def generate(self, extraction: ExtractionResult, level: str, source_text: str) -> Script:
        main_points = "\n".join(f"- {point.title}" for point in extraction.main_points)
        numeric_data = "\n".join(f"- {item.indicator}: {item.value}" for item in extraction.numeric_data)
        prompt = PROMPT_TEMPLATE.format(
            level=level,
            main_points=main_points or "- (sem pontos centrais)",
            numeric_data=numeric_data or "- (sem dados)",
        )
        response = self.llm_client.generate(
            prompt + f"\n\nTexto fonte:\n{source_text}",
            schema_name="script",
            model_id=self.model_id,
            cache_parts={"level": level, "prompt_version": "block5"},
        )
        try:
            return Script.model_validate(response)
        except ValidationError as exc:
            raise ValueError(f"Resposta invalida de roteiro: {exc}") from exc