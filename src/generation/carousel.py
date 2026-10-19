"""Carrossel e legenda: LLM sobre entrada estruturada + partes montadas por regra (linha do nível, fonte,
aviso configurado, hashtags e texto final da legenda)."""
from __future__ import annotations

from pydantic import ValidationError

from src.extraction.models import ExtractionResult
from src.generation import rules
from src.generation.base import StructuredGenerator
from src.generation.models import Caption, Carousel
from src.shared.llm_client import InvalidLLMOutput


class CarouselGenerator(StructuredGenerator):
    fmt = "carrossel"
    schema_name = "carousel_with_caption"

    def generate(
        self,
        extraction: ExtractionResult,
        level: str,
        source_text: str,
        feedback: str | None = None,
        glossary=None,
        forbidden_terms: list[str] | None = None,
        origin: dict | None = None,
        thresholds: dict | None = None,
        **_compat,
    ) -> tuple[Carousel, Caption]:
        gen_input = self.build_input(extraction, level, source_text, feedback, glossary, forbidden_terms, origin, thresholds)
        response = self.call(gen_input)
        carousel = finalize_carousel(response, level, origin or {}, [e.model_dump() for e in extraction.entities],
                                     gen_input.prompt_version())
        return carousel, carousel.legenda


def finalize_carousel(response: dict, level: str, origin: dict, entities: list[dict], prompt_version: str) -> Carousel:
    slides = response.get("slides") or (response.get("carousel") or {}).get("slides")
    caption_raw = dict(response.get("caption") or (response.get("carousel") or {}).get("caption") or {})
    if not slides or not caption_raw:
        raise InvalidLLMOutput("Carrossel sem 'slides' ou sem 'caption'")
    source = rules.source_block(origin)
    notice = rules.institutional_notice()
    hashtags = rules.hashtags_from_entities(entities)
    opening, context = caption_raw.get("opening", ""), caption_raw.get("short_context", "")
    cta = caption_raw.get("cta_sentence", "")
    try:
        caption = Caption(
            opening=opening, short_context=context, source_block=source,
            cta_verb=str(caption_raw.get("cta_verb", "")).lower(), cta_sentence=cta,
            institutional_notice=notice, hashtags=hashtags,
            texto_final=rules.caption_final_text(opening, context, source, cta, notice, hashtags),
            versao_prompt=prompt_version,
        )
        return Carousel(slides=slides, linha_vermelha_nivel=rules.level_line(level), legenda=caption,
                        versao_prompt=prompt_version)
    except ValidationError as exc:
        raise InvalidLLMOutput(f"Carrossel fora do contrato: {exc}") from exc
