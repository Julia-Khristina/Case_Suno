"""Carousel and caption generation."""
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.shared.llm_client import LLMClient
from src.extraction.models import ExtractionResult
from src.generation.models import Caption, Carousel

PROMPT_TEMPLATE = (Path(__file__).resolve().parent / "prompts" / "carousel" / "carousel.txt").read_text(encoding="utf-8")


class CarouselGenerator:
    def __init__(self, llm_client: LLMClient | None = None, model_id: str | None = None) -> None:
        self.llm_client = llm_client or LLMClient()
        self.model_id = model_id

    def generate(
        self,
        extraction: ExtractionResult,
        level: str,
        source_text: str,
        glossary_terms: list[str] | None = None,
        forbidden_terms: list[str] | None = None,
    ) -> tuple[Carousel, Caption]:
        main_points = "\n".join(f"- {point.title}" for point in extraction.main_points)
        numeric_data = "\n".join(f"- {item.indicator}: {item.value}" for item in extraction.numeric_data)
        prompt = PROMPT_TEMPLATE.format(
            level=level,
            main_points=main_points or "- (sem pontos centrais)",
            numeric_data=numeric_data or "- (sem dados)",
            glossary_terms=", ".join(glossary_terms or []),
            forbidden_terms=", ".join(forbidden_terms or []),
        )
        response = self.llm_client.generate(
            prompt + f"\n\nTexto fonte:\n{source_text}",
            schema_name="carousel_with_caption",
            model_id=self.model_id,
            cache_parts={"level": level, "prompt_version": "block5"},
        )
        try:
            # Response may contain { "carousel": {...}, "caption": {...} }.
            if isinstance(response, dict) and "carousel" in response and "caption" in response:
                carousel = Carousel.model_validate(response["carousel"])
                caption = Caption.model_validate(response["caption"])
                return carousel, caption
            # Fallback: carousel only or malformed wrapper.
            carousel = Carousel.model_validate(response)
        except ValidationError as exc:
            raise ValueError(f"Resposta invalida de carrossel: {exc}") from exc
        caption = Caption(
            opening=carousel.slides[0].title,
            short_context=carousel.slides[1].body,
            source_block="Fonte: documento original",
            cta_verb="salvar",
            cta_sentence="Salve este conteudo para consultar depois.",
        )
        return carousel, caption