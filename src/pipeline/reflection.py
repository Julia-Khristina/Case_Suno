"""Loop de reflexão para uma combinação nível:formato, executando os MESMOS nós do grafo.

Não há uma segunda implementação do loop: gerar → avaliar → (juiz) → reescrever com feedback numérico,
com teto de `reescritas_maximas` (duas reescritas = até três tentativas) e encaminhamento à validação
humana com aviso ao esgotar.
"""
from __future__ import annotations

from typing import Any

from src.pipeline.deps import PipelineDeps
from src.pipeline.nodes.evaluate_deterministic import evaluate_deterministic_node
from src.pipeline.nodes.generate import generate_node
from src.pipeline.nodes.judge import judge_node
from src.pipeline.nodes.route import finalize_combo_node
from src.pipeline.state import PipelineState


def run_reflection_loop(
    extraction: Any,
    level: str,
    formato: str,
    source_text: str,
    llm_client=None,
    origin: dict | None = None,
    deps: PipelineDeps | None = None,
    max_rewrites: int | None = None,
    **_compat: Any,
) -> dict[str, Any]:
    deps = deps or PipelineDeps(llm_client=llm_client)
    rewrites = int(deps.thresholds.req("reescritas_maximas")) if max_rewrites is None else max_rewrites
    extraction_dict = extraction.model_dump(mode="json") if hasattr(extraction, "model_dump") else dict(extraction)
    state = PipelineState(
        document={"content": source_text, "origin": origin or {}, "hash": "reflexao"},
        selected_levels=[level], extraction=extraction_dict, combos=[f"{level}:{formato}"],
        current_level=level, current_format=formato, max_retries=rewrites, thresholds=dict(deps.thresholds),
    ).model_dump()

    steps = {"generate": generate_node, "evaluate": evaluate_deterministic_node, "judge": judge_node,
             "finalize": finalize_combo_node}
    action = "generate"
    guard = (rewrites + 1) * 3 + 2
    while action in steps and guard > 0:
        state.update(steps[action](state, deps))
        state = PipelineState(**state).model_dump()
        action = state.get("next_action")
        guard -= 1
        if action == "human_validation":
            break

    output = (state.get("generated_outputs") or {}).get(f"{level}:{formato}", {})
    history = state.get("attempt_history") or []
    return {
        "conteudo": output.get("conteudo"),
        "status": output.get("status"),
        "passou": output.get("status") == "aprovado_pelo_juiz",
        "esgotado": output.get("status") in {"reprovado_pelo_juiz", "reprovado_nas_metricas"},
        "aviso": output.get("aviso"),
        "tentativas": output.get("tentativas", 0),
        "avaliacao_deterministica": output.get("avaliacao_deterministica"),
        "avaliacao_juiz": output.get("avaliacao_juiz"),
        "historico": history,
        "token_count": state.get("token_count", 0),
        "warnings": state.get("warnings", []),
        "errors": state.get("errors", []),
    }


def run_analytical_reflection(extraction, level: str, source_text: str, llm_client, main_points=None, **kwargs):
    """Compatibilidade: (conteúdo, avaliação determinística, tentativas) do texto analítico."""
    result = run_reflection_loop(extraction, level, "texto_analitico", source_text, llm_client=llm_client, **kwargs)
    return result["conteudo"], result["avaliacao_deterministica"], result["tentativas"]
