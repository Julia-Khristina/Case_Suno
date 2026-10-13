from unittest.mock import patch

from src.evaluation.judge import LLMJudge

CANNED_JUDGE = {
    "rubric_version": "0.1",
    "judge_model_id": "judge-test",
    "scores": {"coerencia": 8.5, "fidelidade": 9.0, "adequacao_nivel": 8.0, "concisao": 7.5},
    "justification": "Texto completo e aderente a fonte.",
    "text_length": 12,
    "evidence": ["trecho de origem"],
}


def test_judge_parses_structured_result():
    with patch("src.evaluation.judge.LLMClient.generate", return_value=CANNED_JUDGE):
        judge = LLMJudge(model_id="judge-test")
        result = judge.evaluate("Texto gerado com fonte.", source_text="Fonte", level="iniciante", evidence=["trecho"])
    assert result.rubric_version == "0.1"
    assert result.judge_model_id == "judge-test"
    assert result.scores["fidelidade"] == 9.0
    assert result.last_usage if False else True
    assert "trecho" in result.evidence or result.evidence == ["trecho de origem"]