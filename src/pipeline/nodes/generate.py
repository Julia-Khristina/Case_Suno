"""Nó de geração: chama o gerador do formato atual com a entrada estruturada e o feedback da tentativa anterior."""
from __future__ import annotations

from typing import Any

from src.generation.carousel import CarouselGenerator
from src.generation.script import ScriptGenerator
from src.generation.text_analytical import AnalyticalTextGenerator
from src.pipeline.nodes.common import extraction_of, key_of, safe_persist

GENERATORS = {
    "texto_analitico": AnalyticalTextGenerator,
    "carrossel": CarouselGenerator,
    "roteiro_video": ScriptGenerator,
}


def combined_feedback(human: str | None, automatic: str | None) -> str | None:
    """Motivo da revisora (quando a versão anterior foi rejeitada) + feedback numérico da tentativa anterior.

    O motivo humano vai em todas as tentativas: o feedback automático muda a cada reescrita, o motivo não.
    Ele orienta a correção, mas não autoriza nada fora das regras: grounding, nível e termos proibidos continuam
    sendo checados pelas mesmas métricas e pelo juiz.
    """
    if not human:
        return automatic
    block = ("REVISÃO HUMANA: a versão anterior deste material foi rejeitada pela revisora. Motivo: "
             f"{human.strip()}\nCorrija esse problema mantendo todas as regras do formato e do nível; não acrescente "
             "nada que não esteja na fonte.")
    return f"{block}\n\n{automatic}" if automatic else block


def generate_node(state: dict[str, Any], deps=None) -> dict[str, Any]:
    from src.pipeline.deps import PipelineDeps

    deps = deps or PipelineDeps()
    level, fmt = state.get("current_level"), state.get("current_format")
    if not level or fmt not in GENERATORS:
        return {"status": "falhou", "next_action": "end",
                "errors": list(state.get("errors") or []) + [f"Combinação inválida para geração: {level}:{fmt}"]}

    updates: dict[str, Any] = {}
    key = key_of(state)
    material_ids = dict(state.get("material_ids") or {})
    if key not in material_ids:
        material_id = safe_persist(state, updates, "material",
                                   lambda: deps.persistence.create_material(state.get("execution_id"), level, fmt))
        if material_id:
            material_ids[key] = material_id
    document = state.get("document") or {}
    triangulacao = state.get("triangulacao") or {}
    extra: dict[str, Any] = {}
    if fmt == "texto_analitico" and triangulacao.get("matriz"):
        from src.generation.text_triangulado import TriangulatedTextGenerator

        generator = TriangulatedTextGenerator(llm_client=deps.llm_client)
        extra["triangulacao"] = triangulacao
    else:
        generator = GENERATORS[fmt](llm_client=deps.llm_client)
    feedback = combined_feedback(state.get("human_feedback"), state.get("feedback"))
    record: dict[str, Any] = {"nivel": level, "formato": fmt, "feedback_usado": feedback}
    calls_before = len(getattr(deps.llm_client, "calls", []))
    try:
        result = generator.generate(
            extraction=extraction_of(state), level=level, source_text=document.get("content", ""),
            feedback=feedback, glossary=deps.glossary, forbidden_terms=deps.forbidden_terms,
            origin=document.get("origin") or {}, thresholds=deps.thresholds, **extra,
        )
        model = result[0] if isinstance(result, tuple) else result
        record["conteudo"] = model.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001  saída inválida conta como falha da tentativa (seção 4.10)
        record["erro"] = f"{type(exc).__name__}: {exc}"
    new_calls = list(getattr(deps.llm_client, "calls", []))[calls_before:]
    record.update(
        tokens=sum(int(c.get("total_tokens", 0)) for c in new_calls),
        latencia=sum(float(c.get("latency_seconds", 0.0)) for c in new_calls),
        modelo=new_calls[-1]["model_id"] if new_calls else None,
        versao_prompt=generator.last_input.prompt_version() if generator.last_input else None,
    )
    return {
        **updates,
        "material_ids": material_ids,
        "last_generation": record,
        "token_count": int(state.get("token_count") or 0) + record["tokens"],
        "latency_total": float(state.get("latency_total") or 0) + record["latencia"],
        "next_action": "evaluate",
    }
