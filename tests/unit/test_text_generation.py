from unittest.mock import patch

from src.evaluation.thresholds import load_thresholds
from src.extraction.models import ExtractionResult, MainPoint, SourceComplexity
from src.generation.models import AnalyticalText
from src.generation.text_analytical import AnalyticalTextGenerator
from src.pipeline.nodes.generate import generate_analytical_text
from src.pipeline.reflection import run_analytical_reflection

CANNED_ANALYTICAL = {
    "title": "Titulo do material",
    "subtitle": "Subtitulo do material",
    "introduction": "sim. " * 90 + "Ponto central.",
    "development": "sim. " * 120 + " 10,50%.",
    "analysis": "sim. " * 110,
    "conclusion": "sim. " * 80,
    "covered_main_points": ["Ponto central"],
    "word_count_total": 405,
    "word_count_by_section": {},
}

EXTRACTION = ExtractionResult(
    main_points=[MainPoint(id="mp1", order=1, title="Ponto central")],
    source_complexity=SourceComplexity(word_count=100),
)


def test_analytical_text_generator_validates_response():
    with patch("src.generation.text_analytical.LLMClient.generate", return_value=CANNED_ANALYTICAL):
        generator = AnalyticalTextGenerator()
        result = generator.generate(EXTRACTION, "iniciante", "Fonte com 10,50%. Ponto central.")
    assert isinstance(result, AnalyticalText)
    assert result.title == "Titulo do material"


def test_analytical_generation_node_returns_valid_model():
    with patch("src.generation.text_analytical.LLMClient.generate", return_value=CANNED_ANALYTICAL):
        result = generate_analytical_text(
            extraction=EXTRACTION,
            level="iniciante",
            source_text="Fonte com 10,50%. Ponto central.",
        )
    assert "10,50%" in result.development


def test_reflection_loop_runs_and_returns_evaluation():
    source_text = "Fonte com 10,50%. Ponto central."
    with patch("src.generation.text_analytical.LLMClient.generate", return_value=CANNED_ANALYTICAL):
        text, evaluation, attempts = run_analytical_reflection(
            extraction=EXTRACTION,
            level="iniciante",
            source_text=source_text,
            llm_client=None,
            main_points=["Ponto central"],
            glossary_terms=[],
            forbidden_terms=[],
            thresholds=load_thresholds(),
            max_attempts=1,
        )
    assert attempts == 1
    assert evaluation.passed is True
    assert text.title == "Titulo do material"