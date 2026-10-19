"""LangGraph pipeline (seção 4.10).

admit → extract → generate → evaluate_deterministic ─┬─ passou → judge ─┬─ aprovado → finalize
                    ▲                                 │                  ├─ reprovado e reescrita sobrando → generate
                    │                                 │                  └─ esgotou / juiz falhou → finalize
                    └──── reprovou e reescrita sobrando ┘
                                                      └─ esgotou / sem mudança → finalize
finalize → generate (próxima combinação nível:formato) | human_validation (pausa) → export (se aprovado) | END

O teto de reescritas (config `reescritas_maximas`, padrão 2) é aplicado pelos nós que reprovam; o limite de
recursão do LangGraph é calculado a partir dele e funciona só como rede de segurança.
"""
from __future__ import annotations

from functools import partial
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.pipeline.deps import PipelineDeps
from src.pipeline.nodes.admit import admit_node
from src.pipeline.nodes.evaluate_deterministic import evaluate_deterministic_node
from src.pipeline.nodes.export import export_node, human_validation_node
from src.pipeline.nodes.extract import extract_node
from src.pipeline.nodes.generate import generate_node
from src.pipeline.nodes.judge import judge_node
from src.pipeline.nodes.route import (
    finalize_combo_node,
    route_after_deterministic,
    route_after_human,
    route_after_judge,
    route_next,
)
from src.pipeline.state import PipelineState


def _as_dict(state: Any) -> dict[str, Any]:
    if hasattr(state, "model_dump"):
        return state.model_dump()
    return dict(state or {})


def _wrap_node(name: str, func, deps: PipelineDeps):
    """Converte o estado em dict, aplica o nó e valida o resultado (campo desconhecido levanta erro)."""

    def handler(state: PipelineState) -> PipelineState:
        payload = _as_dict(state)
        updates = func(payload, deps) or {}
        payload.update(updates)
        payload["last_node"] = name
        return PipelineState(**payload)

    handler.__name__ = name
    return handler


def build_graph(checkpointer=None, deps: PipelineDeps | None = None):
    deps = deps or PipelineDeps()
    builder = StateGraph(PipelineState)
    nodes = {
        "admit": admit_node,
        "extract": extract_node,
        "generate": generate_node,
        "evaluate_deterministic": evaluate_deterministic_node,
        "judge": judge_node,
        "finalize": finalize_combo_node,
        "human_validation": human_validation_node,
        "export": export_node,
    }
    for name, func in nodes.items():
        builder.add_node(name, _wrap_node(name, func, deps))

    builder.add_edge(START, "admit")
    builder.add_conditional_edges("admit", route_next, {"extract": "extract", "end": END})
    builder.add_conditional_edges("extract", route_next, {"generate": "generate", "end": END})
    builder.add_conditional_edges("generate", route_next, {"evaluate": "evaluate_deterministic", "end": END})
    builder.add_conditional_edges("evaluate_deterministic", route_after_deterministic,
                                  {"judge": "judge", "generate": "generate", "finalize": "finalize"})
    builder.add_conditional_edges("judge", route_after_judge, {"generate": "generate", "finalize": "finalize"})
    builder.add_conditional_edges("finalize", route_next, {"generate": "generate", "human_validation": "human_validation"})
    builder.add_conditional_edges("human_validation", route_after_human, {"export": "export", "end": END})
    builder.add_edge("export", END)

    if checkpointer is None:
        return builder.compile()
    return builder.compile(checkpointer=checkpointer)


def recursion_limit_for(n_levels: int, max_rewrites: int) -> int:
    """Passos máximos: por combinação, (reescritas + 1) × (gerar, avaliar, julgar) + encerrar; mais folga."""
    per_combo = (max_rewrites + 1) * 3 + 1
    return n_levels * 3 * per_combo + 10


def run_pipeline(content: str, levels: list[str], origin: dict | None = None, deps: PipelineDeps | None = None,
                 admission: dict | None = None, execution_id: str | None = None,
                 fontes: list[dict] | None = None, combos: list[str] | None = None,
                 human_feedback: str | None = None) -> dict[str, Any]:
    """Executa o grafo e devolve o estado final como dict.

    `fontes` (2 a 5, cada uma com id, nome, tipo_fonte, titulo, data, url, conteudo) ativa o texto analítico
    triangulado; com uma fonte só, use `content` e `origin`.

    Regeração de um material rejeitado: `execution_id` da execução original (a nova versão entra nela, sem criar
    outra execução), `combos=["nivel:formato"]` e `human_feedback` com o motivo da revisora.
    """
    deps = deps or PipelineDeps()
    document = {"content": content, "origin": origin or {}}
    if fontes:
        document["fontes"] = fontes
    state = PipelineState(execution_id=execution_id, document=document, selected_levels=levels, admission=admission,
                          combos=list(combos or []), human_feedback=human_feedback)
    app = build_graph(deps=deps)
    n_combos = len(combos) if combos else len(levels) * 3
    limit = recursion_limit_for(max(1, -(-n_combos // 3)), int(deps.thresholds.req("reescritas_maximas")))
    final = app.invoke(state.model_dump(), {"recursion_limit": limit})
    return _as_dict(final)
