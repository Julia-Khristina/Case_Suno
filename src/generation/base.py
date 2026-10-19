"""Base comum dos geradores: monta a entrada estruturada, chama o LLM e registra a chamada."""
from __future__ import annotations

from typing import Any

from src.evaluation.format_checks import load_forbidden_terms
from src.evaluation.text_utils import word_count
from src.evaluation.thresholds import as_thresholds
from src.extraction.models import ExtractionResult
from src.generation.inputs import GenerationInput
from src.glossary.reader import load_glossary
from src.shared.llm_client import InvalidLLMOutput, LLMCallResult, LLMClient


class StructuredGenerator:
    fmt: str = ""
    schema_name: str = ""

    def __init__(self, llm_client: LLMClient | None = None, model_id: str | None = None, **_ignored: Any) -> None:
        self.llm_client = llm_client or LLMClient()
        self.model_id = model_id
        self.last_call: LLMCallResult | None = None
        self.last_input: GenerationInput | None = None

    def build_input(self, extraction: ExtractionResult, level: str, source_text: str, feedback: str | None,
                    glossary=None, forbidden_terms: list[str] | None = None, origin: dict | None = None,
                    thresholds: dict | None = None) -> GenerationInput:
        return GenerationInput(
            level=level, fmt=self.fmt, extraction=extraction, glossary=glossary or load_glossary(),
            thresholds=as_thresholds(thresholds), source_words=word_count(source_text), origin=origin or {},
            forbidden_terms=list(forbidden_terms) if forbidden_terms is not None else load_forbidden_terms(),
            feedback=feedback,
        )

    def call(self, gen_input: GenerationInput) -> dict:
        system, prompt = gen_input.render()
        self.last_input = gen_input
        self.last_call = self.llm_client.generate(
            prompt,
            system=system,
            schema_name=self.schema_name,
            model_id=self.model_id,
            role="generation",
            cache_parts={"level": gen_input.level, "format": self.fmt, "prompt_version": gen_input.prompt_version(),
                         "glossary_version": getattr(gen_input.glossary, "hash", "")},
        )
        response = self.last_call.response
        if not isinstance(response, dict):
            raise InvalidLLMOutput(f"Resposta de {self.fmt} não é um objeto JSON")
        return response
