from unittest.mock import patch
import pytest

from src.evaluation.judge import LLMJudge
from src.evaluation.thresholds import load_thresholds
from src.extraction.models import ExtractionResult, MainPoint, SourceComplexity
from src.generation.models import AnalyticalText
from src.generation.text_analytical import AnalyticalTextGenerator
from src.pipeline.reflection import run_analytical_reflection

CANNED = {
    "title": "Titulo",
    "subtitle": "Subtitulo",
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

JUDGE_RESPONSE = {
    "rubric_version": "0.1",
    "judge_model_id": "judge-test",
    "scores": {"coerencia": 8.0, "fidelidade": 9.0},
    "justification": "Texto adequado.",
    "text_length": 405,
    "evidence": ["10,50%"],
}


@pytest.mark.offline
def test_end_to_end_material_offline():
    with patch("src.generation.text_analytical.LLMClient.generate", return_value=CANNED):
        text, evaluation, attempts = run_analytical_reflection(
            extraction=EXTRACTION,
            level="iniciante",
            source_text="Fonte com 10,50%. Ponto central.",
            llm_client=None,
            main_points=["Ponto central"],
            glossary_terms=[],
            forbidden_terms=[],
            thresholds=load_thresholds(),
            max_attempts=1,
        )
    assert isinstance(text, AnalyticalText)
    assert evaluation.passed is True
    assert attempts == 1

    with patch("src.evaluation.judge.LLMClient.generate", return_value=JUDGE_RESPONSE):
        judge = LLMJudge(model_id="judge-test")
        result = judge.evaluate(text.introduction, source_text="Fonte")
    assert result.scores["fidelidade"] == 9.0


@pytest.mark.offline
def test_generator_output_schema():
    with patch("src.generation.text_analytical.LLMClient.generate", return_value=CANNED):
        generator = AnalyticalTextGenerator()
        result = generator.generate(EXTRACTION, "iniciante", "Fonte com 10,50%.")
    assert result.word_count_total == 405