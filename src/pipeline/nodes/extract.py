"""Nó de extração: pontos centrais, afirmações com trecho exato e dados numéricos (seção 4.4).

Modo triangulado: extrai cada fonte do dossiê, alinha as fontes, monta a matriz, escolhe os 3 pontos centrais e
gera os gráficos; a extração combinada alimenta os geradores. Se o alinhamento falhar, segue como fonte única.
"""
from __future__ import annotations

from typing import Any

from src.extraction.extractor import Extractor
from src.glossary.reader import load_aliases
from src.pipeline.nodes.common import safe_persist


def extract_node(state: dict[str, Any], deps=None) -> dict[str, Any]:
    from src.pipeline.deps import PipelineDeps

    deps = deps or PipelineDeps()
    if (state.get("triangulacao") or {}).get("dossie"):
        return _extract_triangulated(state, deps)
    document = state.get("document") or {}
    content = document.get("content") or ""
    extractor = Extractor(llm_client=deps.llm_client, glossary=deps.glossary, aliases=load_aliases(),
                          term_resolver=deps.term_resolver)
    try:
        result = extractor.extract(content)
    except Exception as exc:  # noqa: BLE001
        return {"status": "falhou", "next_action": "end",
                "errors": list(state.get("errors") or []) + [f"Falha na extração: {type(exc).__name__}: {exc}"]}
    updates = _usage_updates(state, extractor.calls)
    updates.update(extraction=result.model_dump(mode="json"), next_action="generate",
                   warnings=list(state.get("warnings") or []) + result.warnings)
    if not result.main_points or not result.assertions:
        return {**updates, "status": "falhou", "next_action": "end",
                "errors": list(state.get("errors") or []) + ["Extração sem pontos centrais ou sem afirmações ancoradas na fonte."]}
    from src.pipeline.triangulation import single_source_charts

    try:
        updates["graficos"] = single_source_charts(updates["extraction"], document.get("hash", ""))
    except Exception as exc:  # noqa: BLE001  gráfico não bloqueia a geração
        updates["warnings"] = updates["warnings"] + [f"Gráficos não gerados: {exc}"]
    safe_persist(state, updates, "extração no grafo",
                 lambda: deps.persistence.persist_extraction(document.get("hash"), content, updates["extraction"]))
    return updates


def _usage_updates(state: dict, calls: list) -> dict:
    return {"token_count": int(state.get("token_count") or 0) + sum(int((c.usage or {}).get("total_tokens", 0)) for c in calls),
            "latency_total": float(state.get("latency_total") or 0) + sum(float(c.latency_seconds or 0) for c in calls)}


def _extract_triangulated(state: dict, deps) -> dict:
    from src.pipeline.triangulation import extract_and_align
    from src.triangulacao.dossie import Dossie

    dossie = Dossie.model_validate(state["triangulacao"]["dossie"])
    calls_before = len(getattr(deps.llm_client, "calls", []))
    try:
        tri_state, merged, warnings, extraction_calls = extract_and_align(dossie, deps)
    except Exception as exc:  # noqa: BLE001  sem triangulação possível: fonte única com a primeira fonte
        return _fallback_single_source(state, deps, dossie, f"Triangulação não concluída ({type(exc).__name__}: {exc}).")
    new_calls = list(getattr(deps.llm_client, "calls", []))[calls_before:]
    updates = {
        "token_count": int(state.get("token_count") or 0) + sum(int(c.get("total_tokens", 0)) for c in new_calls),
        "latency_total": float(state.get("latency_total") or 0) + sum(float(c.get("latency_seconds", 0)) for c in new_calls),
        "extraction": merged.model_dump(mode="json"),
        "triangulacao": {**state["triangulacao"], **tri_state},
        "warnings": list(state.get("warnings") or []) + warnings,
        "next_action": "generate",
    }
    document = state.get("document") or {}
    for fonte in dossie.fontes:
        extraction = tri_state["extracoes"][fonte.id]
        safe_persist(state, updates, f"extração da fonte {fonte.nome}", lambda f=fonte, e=extraction:
                     deps.persistence.persist_extraction(f.hash, f.conteudo, e, mapping_key=document.get("hash"),
                                                         id_prefix=f"{f.id}:"))
    return updates


def _fallback_single_source(state: dict, deps, dossie, reason: str) -> dict:
    first = dossie.fontes[0]
    document = {**(state.get("document") or {}), "content": first.conteudo, "hash": first.hash,
                "origin": first.origin()}
    retry = {**state, "document": document, "triangulacao": None,
             "warnings": list(state.get("warnings") or []) + [f"{reason} O material usa só a fonte '{first.nome}'."]}
    updates = extract_node(retry, deps)
    return {"document": document, "triangulacao": None, "warnings": retry["warnings"], **updates}
