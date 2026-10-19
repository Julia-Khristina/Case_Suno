"""Nó de avaliação determinística (seção 4.7) e decisão do loop de reflexão (seção 4.10).

- Passou: segue ao juiz.
- Reprovou com reescrita sobrando: incrementa retry_count, injeta o relatório numérico e volta a gerar.
- Reprovou sem reescrita sobrando: encerra a combinação com aviso para a validação humana.
- Reescrita igual à anterior (similaridade acima do limiar): encerra, porque repetir não muda o resultado.
"""
from __future__ import annotations

from typing import Any

from src.evaluation.deterministic import (
    DeterministicReport,
    EvaluationContext,
    Failure,
    evaluate,
    text_for_metrics,
)
from src.evaluation.text_utils import jaccard_trigrams, trigrams, word_count
from src.pipeline.nodes.common import evaluation_context, key_of, safe_persist


def _previous_attempt(state: dict) -> dict | None:
    key = key_of(state)
    previous = [a for a in state.get("attempt_history") or [] if a.get("combo") == key and a.get("avaliacao") == "deterministica"]
    return previous[-1] if previous else None


def change_metrics(previous_text: str | None, current_text: str) -> dict[str, Any]:
    """Quanto a tentativa n+1 mudou em relação à n: similaridade e se só acrescentou texto."""
    if not previous_text:
        return {"similaridade_vs_anterior": None, "apenas_acrescentou": False}
    similarity = jaccard_trigrams(previous_text, current_text)
    prev, cur = set(trigrams(previous_text)), set(trigrams(current_text))
    containment = len(prev & cur) / len(prev) if prev else 0.0
    grew = word_count(current_text) > word_count(previous_text)
    return {"similaridade_vs_anterior": round(similarity, 3), "apenas_acrescentou": bool(grew and containment >= 0.9)}


def evaluate_deterministic_node(state: dict[str, Any], deps=None) -> dict[str, Any]:
    from src.pipeline.deps import PipelineDeps

    deps = deps or PipelineDeps()
    ctx = evaluation_context(state, deps)
    generation = state.get("last_generation") or {}
    attempt_number = int(state.get("retry_count") or 0) + 1
    key = key_of(state)

    if generation.get("erro") or not generation.get("conteudo"):
        report = DeterministicReport(nivel=ctx.level, formato=ctx.fmt, passed=False, failures=[Failure(
            code="saida_invalida_do_modelo", metrica="contrato_json_pydantic", valor="inválida", limiar="válida",
            detalhe=[str(generation.get("erro", "sem conteúdo"))[:400]])])
        current_text = ""
    else:
        report = evaluate(generation["conteudo"], ctx)
        current_text = text_for_metrics(generation["conteudo"], ctx.fmt)

    previous = _previous_attempt(state)
    change = change_metrics(previous.get("texto_avaliado") if previous else None, current_text)
    attempt = {
        "combo": key, "nivel": ctx.level, "formato": ctx.fmt, "tentativa": attempt_number, "avaliacao": "deterministica",
        "passou": report.passed, "falhas": [f.model_dump(mode="json") for f in report.failures],
        "motivo_reprovacao": ", ".join(report.failure_codes) or None, "metricas": report.metrics,
        "avisos": report.warnings, "nivel_classificado": report.classified_level,
        "complexidade_fonte": report.source_complexity, "conteudo": generation.get("conteudo"),
        "erro_geracao": generation.get("erro"), "feedback_usado": generation.get("feedback_usado"),
        "tokens": generation.get("tokens", 0), "latencia": generation.get("latencia", 0.0),
        "modelo": generation.get("modelo"), "versao_prompt": generation.get("versao_prompt"),
        "tamanho_texto": word_count(current_text), "texto_avaliado": current_text,
        "mudanca_vs_anterior": change["similaridade_vs_anterior"], "apenas_acrescentou": change["apenas_acrescentou"],
    }
    updates: dict[str, Any] = {}
    material_id = (state.get("material_ids") or {}).get(key)
    if material_id:
        attempt["id_tentativa"] = safe_persist(state, updates, "tentativa",
                                               lambda: deps.persistence.record_attempt(material_id, attempt))
    history = list(state.get("attempt_history") or []) + [attempt]
    updates.update(deterministic_evaluation=report.model_dump(mode="json"), judge_evaluation=None,
                   attempt_history=history)

    if report.passed:
        return {**updates, "next_action": "judge"}

    threshold = float(deps.thresholds.req("reescrita_similaridade_max"))
    if change["similaridade_vs_anterior"] is not None and change["similaridade_vs_anterior"] >= threshold:
        return {**updates, "next_action": "finalize", "stop_reason": "reescrita_sem_mudanca",
                "warnings": list(state.get("warnings") or []) + [
                    f"{key}: reescrita praticamente igual à anterior (similaridade {change['similaridade_vs_anterior']}); "
                    "encaminhada à validação humana."]}
    if int(state.get("retry_count") or 0) < int(state.get("max_retries") or 0):
        return {**updates, "retry_count": attempt_number, "feedback": report.feedback(), "next_action": "generate"}
    return {**updates, "next_action": "finalize"}


# ---------------------------------------------------------------------------------- compatibilidade


def evaluate_analytical_text(
    analytical_text,
    level: str,
    source_text: str,
    main_points: list[str] | None = None,
    glossary_terms: list[str] | None = None,
    forbidden_terms: list[str] | None = None,
    approved_impact_explanations: list[str] | None = None,
    thresholds: dict | None = None,
    source_complexity: dict | None = None,
    origin: dict | None = None,
    glossary=None,
    fmt: str = "texto_analitico",
):
    """Avalia um material isolado (ex.: texto editado por humano) com o mesmo avaliador do pipeline."""
    from src.evaluation.models import DeterministicEvaluation
    from src.evaluation.thresholds import as_thresholds
    from src.glossary.reader import load_glossary
    from src.evaluation.format_checks import load_forbidden_terms

    content = analytical_text.model_dump(mode="json") if hasattr(analytical_text, "model_dump") else dict(analytical_text)
    ctx = EvaluationContext(
        level=level, fmt=fmt, source_text=source_text, glossary=glossary or load_glossary(),
        thresholds=as_thresholds(thresholds),
        main_points=[{"id": f"p{i}", "title": t, "assertions": []} for i, t in enumerate(main_points or [], start=1)],
        forbidden_terms=load_forbidden_terms() if forbidden_terms is None else forbidden_terms,
        origin=origin or {},
    )
    if fmt == "texto_analitico" and not origin:
        ctx.origin = {}
        content.setdefault("fonte_bloco", "")
    report = evaluate(content, ctx)
    # Edição humana: o bloco de fonte e as declarações de ponto_ids não são exigidos de quem edita
    ignored = {"bloco_de_fonte_diferente_da_regra", "ponto_ids_nao_declarados"} if not origin else set()
    failures = [f for f in report.failures if f.code not in ignored]
    codes = [f.code for f in failures]
    return DeterministicEvaluation(
        flesch=report.metrics.get("flesch", 0.0),
        term_density=report.metrics.get("densidade_termos", 0.0),
        grounding_score=1.0 - float(report.metrics.get("fracao_frases_sem_respaldo", 0.0)),
        numbers_verified="numero_ou_data_sem_origem" not in codes,
        main_points_coverage=len(ctx.main_points) - len(report.metrics.get("pontos_nao_cobertos", [])),
        beginner_term_window_ok="termo_tecnico_sem_explicacao" not in codes,
        format_checks={"no_emoji": "emoji_encontrado" not in codes,
                       "no_forbidden_terms": "termo_proibido_encontrado" not in codes,
                       "word_count_in_range": "tamanho_fora_do_intervalo" not in codes},
        classified_level=report.classified_level,
        source_complexity=source_complexity or report.source_complexity,
        passed=not failures,
        failures=codes,
    )
