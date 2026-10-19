"""Nó de admissão: valida o documento, registra versões de configuração e monta a fila nível × formato."""
from __future__ import annotations

import hashlib
from typing import Any

from src.admission.models import OriginMetadata
from src.admission.service import admit_text
from src.pipeline.nodes.common import build_combos, safe_persist


def admit_node(state: dict[str, Any], deps=None) -> dict[str, Any]:
    from src.pipeline.deps import PipelineDeps

    deps = deps or PipelineDeps()
    document = dict(state.get("document") or {})
    triangulation_warnings: list[str] = []
    triangulacao = state.get("triangulacao")
    if document.get("fontes") and not triangulacao:
        from src.pipeline.triangulation import admit_sources, combined_origin

        dossie, triangulation_warnings, admitted = admit_sources(document["fontes"], deps)
        if dossie is not None:
            document.update(content=dossie.texto_combinado(), origin=combined_origin(dossie), hash=dossie.hash)
            triangulacao = {"dossie": dossie.model_dump(mode="json")}
            state = {**state, "admission": {"status": "admitido", "partial_reasons": [], "is_financial": True,
                                            "language": "pt", "distinct_glossary_terms": 0}}
        elif admitted:  # sem triangulação: fonte única com a primeira fonte admitida
            first = admitted[0]
            document.update(content=first.get("conteudo", ""), origin={k: first.get(k) for k in ("titulo", "data", "url")}
                            | {"instituicao": first.get("nome")})
        document.pop("fontes", None)
    content = document.get("content") or document.get("texto") or ""
    origin = dict(document.get("origin") or {})
    document_hash = document.get("hash") or hashlib.sha256(content.encode("utf-8")).hexdigest()
    document.update(content=content, origin=origin, hash=document_hash)
    levels = state.get("selected_levels") or []
    updates: dict[str, Any] = {"document": document, "thresholds": dict(deps.thresholds),
                               "max_retries": int(deps.thresholds.req("reescritas_maximas")),
                               "config_versions": deps.config_versions()}

    if not levels:
        return {**updates, "status": "falhou", "next_action": "end", "errors": ["Nenhum nível selecionado."]}

    admission = state.get("admission")
    if admission is None:
        try:
            origin_model = OriginMetadata(**{k: v for k, v in origin.items() if k in OriginMetadata.model_fields})
        except Exception:  # noqa: BLE001
            origin_model = OriginMetadata()
        result = admit_text(content, origin=origin_model, glossary_terms=deps.glossary.all_forms())
        admission = result.model_dump(mode="json")
    if admission.get("status") == "bloqueado":
        reasons = admission.get("partial_reasons") or ["conteúdo parcial ou insuficiente"]
        return {**updates, "admission": admission, "status": "bloqueado", "next_action": "end",
                "errors": [f"Documento bloqueado na admissão: {', '.join(reasons)}"]}

    warnings = list(state.get("warnings") or []) + triangulation_warnings
    if admission.get("status") == "aviso":
        warnings.append("Admissão com aviso: texto pode não ser financeiro ou não estar em português; seguindo por decisão do usuário.")

    # combinações pedidas (regeração de um material) ou todas as dos níveis selecionados
    allowed = build_combos(levels)
    combos = [c for c in (state.get("combos") or []) if c in allowed] or allowed
    level, fmt = combos[0].split(":")
    if state.get("execution_id"):  # regeração: a nova versão entra na execução original
        execution_id = state["execution_id"]
    else:
        execution_id = safe_persist(state, updates, "execução", lambda: deps.persistence.start_execution(
            document_hash, content, origin, admission, levels, updates["config_versions"]))
    return {**updates, "admission": admission, "execution_id": execution_id or state.get("execution_id"),
            "combos": combos, "combo_index": 0, "current_level": level, "current_format": fmt,
            "retry_count": 0, "feedback": None, "warnings": warnings, "next_action": "extract",
            "triangulacao": triangulacao}
