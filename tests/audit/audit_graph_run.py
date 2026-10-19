# -*- coding: utf-8 -*-
"""RETRATO DO ESTADO ANTERIOR À CORREÇÃO (17/10/2026): reproduz os defeitos encontrados na auditoria.
Auditoria (diagnóstico, sem rede): executa o grafo LangGraph real de ponta a ponta.

Cenário 1: LLM_MODE=simulated puro (como a interface roda hoje).
Cenário 2: LLMClient substituído por um falso que devolve JSON válido e conta chamadas,
           para observar o roteamento, retry_count, feedback e o juiz.

Uso: python -m tests.audit.audit_graph_run
"""
from __future__ import annotations

import json
import os
import sys
from unittest.mock import patch

os.environ["LLM_MODE"] = "simulated"

from src.pipeline.graph import build_graph  # noqa: E402
from src.pipeline.state import PipelineState  # noqa: E402

SOURCE = (
    "O Comitê de Política Monetária (Copom) decidiu manter a taxa Selic em 10,50% ao ano. "
    "Segundo a ata, a inflação medida pelo IPCA acumulou 4,23% em doze meses. "
    "O comitê avalia que a política monetária deve permanecer contracionista por período prolongado. "
    "As expectativas de inflação seguem desancoradas, o que exige cautela. "
) * 6  # ~250 palavras, financeiro


def _initial():
    return PipelineState(
        execution_id="audit",
        document={"content": SOURCE, "origin": {"instituicao": "BCB", "titulo": "Ata"}},
        selected_levels=["iniciante"],
    ).model_dump()


class FakeLLM:
    """Cliente falso: devolve respostas válidas por schema e registra cada chamada."""

    calls: list[dict] = []

    def __init__(self, *a, **k):
        self.usage = {"total_tokens": 1000}
        self.latency = 0.1

    def generate(self, prompt, schema_name="text", model_id=None, **kw):
        from src.shared.llm_client import LLMCallResult

        FakeLLM.calls.append({"schema": schema_name, "model_id": model_id,
                              "has_feedback": "(nenhum)" not in prompt, "prompt_len": len(prompt)})
        if schema_name == "extraction":
            resp = {
                "main_points": [
                    {"id": "mp1", "order": 1, "title": "Selic mantida em 10,50%", "assertion_ids": ["a1"]},
                    {"id": "mp2", "order": 2, "title": "IPCA acumulado de 4,23%", "assertion_ids": ["a2"]},
                    {"id": "mp3", "order": 3, "title": "Política contracionista prolongada", "assertion_ids": ["a3"]},
                ],
                "assertions": [
                    {"id": "a1", "text": "O Copom manteve a Selic em 10,50% ao ano.", "type": "fato",
                     "source_span": {"text": "decidiu manter a taxa Selic em 10,50% ao ano"}},
                    {"id": "a2", "text": "O IPCA acumulou 4,23% em doze meses.", "type": "fato",
                     "source_span": {"text": "acumulou 4,23% em doze meses"}},
                    {"id": "a3", "text": "A política deve permanecer contracionista.", "type": "projecao",
                     "source_span": {"text": "deve permanecer contracionista por período prolongado"}},
                ],
                "numeric_data": [],
                "source_complexity": {"word_count": 250},
            }
        elif schema_name == "analytical_text":
            sec = lambda c: {"title": "x", "content": c, "ponto_ids": ["mp1"]}  # noqa: E731
            resp = {"title": "Selic", "subtitle": "Ata", "introduction": sec("A Selic ficou em 10,50%."),
                    "development": sec("O IPCA acumulou 4,23%."), "analysis": sec("Política contracionista."),
                    "conclusion": sec("Acompanhar a inflação."), "word_count_total": 400,
                    "word_count_by_section": {"introduction": 60, "development": 140, "analysis": 120, "conclusion": 80},
                    "fonte_bloco": "Fonte: BCB", "caixa_entenda_os_termos": "Selic: taxa básica."}
        elif schema_name == "judge":
            resp = {"rubric_version": "1.1", "judge_model_id": "x", "scores": {"a": 9}, "justification": "ok",
                    "text_length": 10, "evidence": []}
        else:
            resp = {}
        return LLMCallResult(response=resp, usage={"total_tokens": 1000}, latency_seconds=0.1,
                             model_id=model_id or "gen", mode="fake")


def scenario_simulated():
    app = build_graph()
    try:
        final = app.invoke(_initial(), {"recursion_limit": 40})
        return {"ok": True, "last_node": final.get("last_node"), "errors": final.get("errors"),
                "outputs": list((final.get("generated_outputs") or {}).keys()),
                "current_level": final.get("current_level")}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "exception": f"{type(exc).__name__}: {str(exc)[:300]}"}


def scenario_fake_llm():
    FakeLLM.calls = []
    trace = []
    with patch("src.pipeline.nodes.generate.LLMClient", FakeLLM), \
         patch("src.extraction.extractor.LLMClient", FakeLLM), \
         patch("src.evaluation.judge.LLMClient", FakeLLM):
        app = build_graph()
        try:
            for step in app.stream(_initial(), {"recursion_limit": 30}, stream_mode="values"):
                trace.append({
                    "node": step.get("last_node"),
                    "retry_count": step.get("retry_count"),
                    "feedback": step.get("feedback"),
                    "deterministic_ok_in_state": "deterministic_ok" in step,
                    "failures": (step.get("deterministic_evaluation") or {}).get("failures"),
                    "errors": (step.get("errors") or [])[-1:] ,
                })
            outcome = "terminou"
        except Exception as exc:  # noqa: BLE001
            outcome = f"{type(exc).__name__}: {str(exc)[:200]}"
    return {"outcome": outcome, "llm_calls": len(FakeLLM.calls),
            "calls_by_schema": {s: sum(1 for c in FakeLLM.calls if c["schema"] == s)
                                for s in {c["schema"] for c in FakeLLM.calls}},
            "any_prompt_with_feedback": any(c["has_feedback"] for c in FakeLLM.calls if c["schema"] != "extraction"),
            "trace_first_12": trace[:12], "trace_len": len(trace)}


def scenario_router_fixed():
    """Cenário 3 (contrafactual): só os roteadores passam a aceitar o objeto de estado.

    Mostra o que aconteceria com o loop se o AttributeError fosse corrigido isoladamente.
    """
    import src.pipeline.graph as g
    from src.pipeline.nodes import route

    def as_dict(fn):
        return lambda s: fn(s.model_dump() if hasattr(s, "model_dump") else s)

    FakeLLM.calls = []
    steps = []
    with patch("src.pipeline.nodes.generate.LLMClient", FakeLLM), \
         patch("src.extraction.extractor.LLMClient", FakeLLM), \
         patch("src.evaluation.judge.LLMClient", FakeLLM), \
         patch.object(g, "route_after_deterministic", as_dict(route.route_after_deterministic)), \
         patch.object(g, "route_after_judge", as_dict(route.route_after_judge)), \
         patch.object(g, "route_after_human", as_dict(route.route_after_human)):
        app = g.build_graph()
        try:
            for upd in app.stream(_initial(), {"recursion_limit": 25}, stream_mode="updates"):
                for node, st in upd.items():
                    st = st.model_dump() if hasattr(st, "model_dump") else (st or {})
                    steps.append((node, st.get("retry_count"), st.get("feedback"),
                                  (st.get("deterministic_evaluation") or {}).get("failures")))
            outcome = "terminou"
        except Exception as exc:  # noqa: BLE001
            outcome = f"{type(exc).__name__}: {str(exc)[:160]}"
    return {"outcome": outcome, "llm_calls": len(FakeLLM.calls),
            "calls_by_schema": {s: sum(1 for c in FakeLLM.calls if c["schema"] == s)
                                for s in {c["schema"] for c in FakeLLM.calls}},
            "any_generation_prompt_with_feedback": any(c["has_feedback"] for c in FakeLLM.calls
                                                       if c["schema"] == "analytical_text"),
            "node_sequence": [s[0] for s in steps],
            "retry_counts_seen": sorted({s[1] for s in steps if s[1] is not None}),
            "failures_first_eval": next((s[3] for s in steps if s[3]), None)}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out = {"cenario_1_simulado": scenario_simulated(), "cenario_2_llm_falso": scenario_fake_llm(),
           "cenario_3_roteador_corrigido": scenario_router_fixed()}
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
