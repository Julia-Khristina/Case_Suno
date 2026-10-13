"""Routing helpers for reflection."""
from src.evaluation.models import DeterministicEvaluation


def route_after_evaluation(evaluation: DeterministicEvaluation, attempt: int, max_attempts: int = 2) -> str:
    if evaluation.passed:
        return "juiz"
    if attempt < max_attempts:
        return "gerar"
    return "validacao_humana"