"""Auxiliares compartilhados pelos nós do pipeline."""
from __future__ import annotations

from typing import Any, Callable

from src.evaluation.deterministic import EvaluationContext
from src.extraction.models import ExtractionResult

FORMATS_ORDER = ["texto_analitico", "carrossel", "roteiro_video"]
LEVELS_ORDER = ["iniciante", "intermediario", "avancado"]


def key_of(state: dict) -> str:
    return f"{state.get('current_level')}:{state.get('current_format')}"


def extraction_of(state: dict) -> ExtractionResult:
    return ExtractionResult.model_validate(state.get("extraction") or {})


def main_points_for_eval(extraction: ExtractionResult) -> list[dict]:
    by_id = {a.id: a for a in extraction.assertions}
    return [{"id": p.id, "title": p.title, "assertions": [by_id[a].text for a in p.assertion_ids if a in by_id]}
            for p in extraction.main_points]


def evaluation_context(state: dict, deps) -> EvaluationContext:
    from src.pipeline.triangulation import matrix_points_for_eval, triangulation_context

    extraction = extraction_of(state)
    document = state.get("document") or {}
    triangulacao = state.get("triangulacao") or {}
    triangulated = bool(triangulacao.get("matriz"))
    points = matrix_points_for_eval(triangulacao) if triangulated else main_points_for_eval(extraction)
    return EvaluationContext(
        triangulacao=triangulation_context(triangulacao) if triangulated else None,
        level=state["current_level"],
        fmt=state["current_format"],
        source_text=document.get("content", ""),
        glossary=deps.glossary,
        thresholds=deps.thresholds,
        main_points=points,
        assertions=[a.text for a in extraction.assertions],
        declared_variations=[a.text for a in extraction.assertions if a.variation_declared],
        forbidden_terms=deps.forbidden_terms,
        recommendation_patterns=deps.recommendation_patterns,
        origin=document.get("origin") or {},
    )


def assertions_block(extraction: ExtractionResult) -> str:
    lines = []
    for a in extraction.assertions:
        lines.append(f"- {a.id} ({a.type}{', ' + a.role if a.role != 'nenhum' else ''}): {a.text} | trecho: \"{a.source_span.text}\"")
    return "\n".join(lines) or "(sem afirmações)"


def safe_persist(state: dict, updates: dict, label: str, fn: Callable[[], Any]) -> Any:
    """Executa uma gravação; falha vira erro visível no estado (nunca silenciosa), sem derrubar a geração."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        errors = list(updates.get("errors", state.get("errors") or []))
        errors.append(f"Falha ao gravar {label}: {type(exc).__name__}: {exc}")
        updates["errors"] = errors
        return None


def build_combos(levels: list[str]) -> list[str]:
    ordered = [lvl for lvl in LEVELS_ORDER if lvl in (levels or [])]
    return [f"{lvl}:{fmt}" for lvl in ordered for fmt in FORMATS_ORDER]
