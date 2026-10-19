"""Nó do juiz LLM-as-a-judge (seção 4.7): roda só nos materiais que passaram nas métricas determinísticas.

- Aprovado: encerra a combinação.
- Reprovado com reescrita sobrando: injeta as notas por critério (nota, mínimo, justificativa, evidência).
- Reprovado sem reescrita: encerra com aviso. Falha do juiz (saída inválida, configuração): encerra com aviso,
  sem gastar reescritas do gerador.
"""
from __future__ import annotations

from typing import Any

from src.evaluation.deterministic import text_for_format_checks
from src.evaluation.judge import LLMJudge
from src.pipeline.nodes.common import assertions_block, extraction_of, key_of, safe_persist

JUDGE_METRICS = ("palavras", "flesch", "densidade_termos", "fracao_frases_sem_respaldo", "razao_saida_fonte")


def judge_node(state: dict[str, Any], deps=None) -> dict[str, Any]:
    from src.pipeline.deps import PipelineDeps

    deps = deps or PipelineDeps()
    key = key_of(state)
    generation = state.get("last_generation") or {}
    content = generation.get("conteudo") or {}
    fmt = state.get("current_format")
    report = state.get("deterministic_evaluation") or {}
    metrics = {k: (report.get("metrics") or {}).get(k) for k in JUDGE_METRICS}
    metrics["nivel_classificado"] = report.get("classified_level")
    history = list(state.get("attempt_history") or [])
    attempt = next((a for a in reversed(history) if a.get("combo") == key and a.get("avaliacao") == "deterministica"), {})
    updates: dict[str, Any] = {}

    calls_before = len(getattr(deps.llm_client, "calls", []))
    try:
        if deps.require_distinct_judge:
            deps.llm_client.assert_distinct_models()
        triangulacao = state.get("triangulacao") or {}
        triangulated = fmt == "texto_analitico" and bool(triangulacao.get("matriz"))
        if triangulated:
            from src.generation.text_triangulado import matrix_block
            from src.triangulacao.models import LinhaMatriz

            rubric_path = "src/evaluation/rubric_triangulado.yaml"
            evidence = matrix_block([LinhaMatriz.model_validate(r) for r in triangulacao["matriz"]], include_difference=True)
        else:
            rubric_path, evidence = deps.rubric_path, assertions_block(extraction_of(state))
        judge = LLMJudge(llm_client=deps.llm_client, rubric_path=rubric_path, thresholds=deps.thresholds)
        result = judge.evaluate(
            generated_text=text_for_format_checks(content, fmt),
            level=state.get("current_level"),
            formato="texto_analitico_triangulado" if triangulated else fmt,
            assertions_block=evidence,
            metrics=metrics,
        )
        evaluation = result.model_dump(mode="json")
        error = None
    except Exception as exc:  # noqa: BLE001
        result, evaluation, error = None, {"erro": f"{type(exc).__name__}: {exc}"}, f"{type(exc).__name__}: {exc}"
    new_calls = list(getattr(deps.llm_client, "calls", []))[calls_before:]
    tokens = sum(int(c.get("total_tokens", 0)) for c in new_calls)
    latency = sum(float(c.get("latency_seconds", 0.0)) for c in new_calls)

    judge_record = {"combo": key, "nivel": state.get("current_level"), "formato": fmt,
                    "tentativa": attempt.get("tentativa"), "avaliacao": "juiz", **evaluation,
                    "tokens": tokens, "latencia": latency}
    if result is not None and attempt.get("id_tentativa"):
        safe_persist(state, updates, "avaliação do juiz",
                     lambda: deps.persistence.record_judge(attempt["id_tentativa"], evaluation))
    updates.update(
        judge_evaluation=evaluation,
        attempt_history=history + [judge_record],
        token_count=int(state.get("token_count") or 0) + tokens,
        latency_total=float(state.get("latency_total") or 0) + latency,
    )
    if error:
        return {**updates, "next_action": "finalize",
                "warnings": list(state.get("warnings") or []) + [f"{key}: juiz não avaliou ({error}); revisão humana obrigatória."]}
    if result.aprovado:
        return {**updates, "next_action": "finalize"}
    if int(state.get("retry_count") or 0) < int(state.get("max_retries") or 0):
        feedback = result.feedback(deps.thresholds.req("juiz_media_minima"), deps.thresholds.req("juiz_nota_minima_criterio"))
        return {**updates, "retry_count": int(state.get("retry_count") or 0) + 1, "feedback": feedback,
                "next_action": "generate"}
    return {**updates, "next_action": "finalize"}
