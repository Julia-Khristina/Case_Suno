"""Reflection loop helpers."""
from src.pipeline.nodes.evaluate_deterministic import evaluate_analytical_text
from src.pipeline.nodes.generate import generate_analytical_text


def run_analytical_reflection(
    extraction,
    level: str,
    source_text: str,
    llm_client,
    main_points: list[str],
    glossary_terms: list[str] | None = None,
    forbidden_terms: list[str] | None = None,
    thresholds: dict | None = None,
    model_id: str | None = None,
    max_attempts: int = 2,
):
    glossary_terms = glossary_terms or []
    forbidden_terms = forbidden_terms or []
    feedback: str | None = None
    analytical_text = None
    evaluation = None

    for attempt in range(1, max_attempts + 1):
        analytical_text = generate_analytical_text(
            extraction=extraction,
            level=level,
            source_text=source_text,
            llm_client=llm_client,
            feedback=feedback,
            glossary_terms=glossary_terms,
            forbidden_terms=forbidden_terms,
            model_id=model_id,
        )
        evaluation = evaluate_analytical_text(
            analytical_text=analytical_text,
            level=level,
            source_text=source_text,
            main_points=main_points,
            glossary_terms=glossary_terms,
            forbidden_terms=forbidden_terms,
            thresholds=thresholds,
            source_complexity={"word_count": len(source_text.split())},
        )
        if evaluation.passed or attempt == max_attempts:
            return analytical_text, evaluation, attempt
        feedback = "; ".join(evaluation.failures)

    return analytical_text, evaluation, max_attempts