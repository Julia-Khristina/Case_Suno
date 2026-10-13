"""Generation node helpers."""
from src.generation.text_analytical import AnalyticalTextGenerator


def generate_analytical_text(
    extraction,
    level: str,
    source_text: str,
    llm_client=None,
    feedback: str | None = None,
    glossary_terms: list[str] | None = None,
    forbidden_terms: list[str] | None = None,
    model_id: str | None = None,
    word_min: int = 350,
    word_max: int = 500,
):
    generator = AnalyticalTextGenerator(
        llm_client=llm_client,
        model_id=model_id,
        word_min=word_min,
        word_max=word_max,
    )
    return generator.generate(
        extraction=extraction,
        level=level,
        source_text=source_text,
        feedback=feedback,
        glossary_terms=glossary_terms,
        forbidden_terms=forbidden_terms,
    )