"""Nó de exportação: só materiais aprovados pela pessoa revisora são liberados (seção 4.8)."""
from __future__ import annotations

from typing import Any


def export_node(state: dict[str, Any], deps=None) -> dict[str, Any]:
    outputs = state.get("generated_outputs") or {}
    approved = [key for key, entry in outputs.items() if (entry or {}).get("aprovado")]
    return {"status": "exportado" if approved else state.get("status", "aguardando_revisao"),
            "next_action": "end", "warnings": list(state.get("warnings") or []) + (
                [] if approved else ["Nenhum material aprovado para exportação."])}


def human_validation_node(state: dict[str, Any], deps=None) -> dict[str, Any]:
    """Pausa do fluxo: os materiais ficam aguardando revisão. A decisão (aprovar, editar, rejeitar) é aplicada
    pela interface em cada material (apply_human_decision); retomar com human_decision='aprovar' segue à exportação."""
    from src.pipeline.deps import PipelineDeps

    deps = deps or PipelineDeps()
    execution_id = state.get("execution_id")
    if execution_id:
        try:
            # regeração de um material rejeitado: soma o custo à execução original em vez de sobrescrevê-lo
            deps.persistence.finish_execution(execution_id, int(state.get("token_count") or 0),
                                              float(state.get("latency_total") or 0), "aguardando_revisao",
                                              accumulate=bool(state.get("human_feedback")))
        except Exception as exc:  # noqa: BLE001
            return {"status": "aguardando_revisao", "next_action": "end",
                    "errors": list(state.get("errors") or []) + [f"Falha ao gravar execução: {exc}"]}
    return {"status": "aguardando_revisao", "next_action": "end"}
