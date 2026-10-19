"""Encerramento de cada combinação nível:formato e roteamento condicional (seção 4.10).

Os nós que avaliam decidem `next_action`; os roteadores só o leem. Assim o teto de reescritas fica num
lugar só (retry_count incrementado por quem reprova) e não há caminho sem saída.
"""
from __future__ import annotations

from typing import Any

from src.pipeline.nodes.common import key_of, safe_persist
from src.pipeline.persistence import link_sentences, traceability_ratio


def _status(state: dict) -> tuple[str, str | None]:
    judge = state.get("judge_evaluation") or {}
    report = state.get("deterministic_evaluation") or {}
    attempts = int(state.get("retry_count") or 0) + 1
    if judge.get("erro"):
        return "juiz_falhou", f"O juiz não avaliou este material ({judge['erro'][:160]}). Revise com atenção."
    if judge and judge.get("aprovado"):
        return "aprovado_pelo_juiz", None
    if judge:
        return "reprovado_pelo_juiz", (f"Reprovado pelo juiz após {attempts} tentativa(s): média "
                                       f"{judge.get('media_ponderada')}; abaixo do mínimo: {judge.get('criterios_abaixo_do_minimo')}.")
    failures = [f.get("code") for f in report.get("failures") or []]
    if state.get("stop_reason") == "reescrita_sem_mudanca":
        return "reprovado_nas_metricas", (f"Encerrado após {attempts} tentativa(s): a reescrita repetiu a anterior sem "
                                          f"corrigir {', '.join(failures)}.")
    return "reprovado_nas_metricas", (f"Limite de reescritas atingido ({attempts} tentativa(s)) sem passar nas métricas "
                                      f"determinísticas: {', '.join(failures)}.")


def _best_content(state: dict) -> tuple[Any, dict | None]:
    """Conteúdo final: a última tentativa com saída válida (uma saída inválida não substitui uma válida)."""
    key = key_of(state)
    attempts = [a for a in state.get("attempt_history") or []
                if a.get("combo") == key and a.get("avaliacao") == "deterministica" and a.get("conteudo")]
    if not attempts:
        return None, None
    return attempts[-1]["conteudo"], attempts[-1]


def finalize_combo_node(state: dict[str, Any], deps=None) -> dict[str, Any]:
    """Grava o resultado da combinação atual e avança para a próxima (ou para a validação humana)."""
    from src.pipeline.deps import PipelineDeps

    deps = deps or PipelineDeps()
    key = key_of(state)
    status, warning = _status(state)
    content, attempt = _best_content(state)
    links = link_sentences(content or {}, state.get("current_format"), state.get("extraction") or {}) if content else []
    if content is not None and state.get("current_format") == "texto_analitico":
        content = attach_reader_blocks(content, state, links)
    record = {
        "conteudo": content, "nivel": state.get("current_level"), "formato": state.get("current_format"),
        "status": status, "aviso": warning, "tentativas": int(state.get("retry_count") or 0) + 1,
        "nivel_classificado": (attempt or {}).get("nivel_classificado"),
        "avaliacao_deterministica": state.get("deterministic_evaluation"), "avaliacao_juiz": state.get("judge_evaluation"),
        "rastreabilidade": round(traceability_ratio(links), 3), "material_id": (state.get("material_ids") or {}).get(key),
    }
    updates: dict[str, Any] = {}
    if record["material_id"] and content is not None:
        safe_persist(state, updates, "material", lambda: deps.persistence.finalize_material(
            record["material_id"], content, status, warning, record["nivel_classificado"],
            (attempt or {}).get("complexidade_fonte"), (state.get("config_versions") or {}).get("glossario", ""), links,
            (state.get("document") or {}).get("hash")))
    outputs = dict(state.get("generated_outputs") or {})
    outputs[key] = record
    warnings = list(updates.get("warnings", state.get("warnings") or []))
    if warning:
        warnings.append(f"{key}: {warning}")

    combos = list(state.get("combos") or [])
    index = int(state.get("combo_index") or 0) + 1
    reset = {"retry_count": 0, "feedback": None, "last_generation": None, "deterministic_evaluation": None,
             "judge_evaluation": None, "stop_reason": None}
    if index < len(combos):
        level, fmt = combos[index].split(":")
        return {**updates, **reset, "generated_outputs": outputs, "warnings": warnings, "combo_index": index,
                "current_level": level, "current_format": fmt, "next_action": "generate"}
    return {**updates, **reset, "generated_outputs": outputs, "warnings": warnings, "combo_index": index,
            "next_action": "human_validation"}


def attach_reader_blocks(content: dict, state: dict, links: list[dict]) -> dict:
    """Blocos montados por regra, fora da contagem de palavras: gráficos do nível, matriz e rastreio por frase."""
    from src.generation.text_triangulado import charts_for_level

    content = dict(content)
    level = state.get("current_level")
    triangulacao = state.get("triangulacao") or {}
    assertions = {a["id"]: a for a in (state.get("extraction") or {}).get("assertions", [])}
    names = {f["id"]: f["nome"] for f in triangulacao.get("fontes", [])}
    origin = (state.get("document") or {}).get("origin") or {}
    content["rastreio"] = [
        {**link, "tipo": (assertions.get(link["afirmacao_id"]) or {}).get("type"),
         "trecho": ((assertions.get(link["afirmacao_id"]) or {}).get("source_span") or {}).get("text"),
         "fonte": names.get(str(link["afirmacao_id"]).split(":")[0]) if ":" in str(link["afirmacao_id"] or "")
         else origin.get("instituicao")}
        for link in links
    ]
    if triangulacao.get("matriz"):
        content["graficos"] = charts_for_level(triangulacao.get("graficos", []), level)
        content["triangulacao"] = {k: triangulacao.get(k) for k in ("assunto", "fontes", "grupos_origem", "independentes",
                                                                     "matriz", "pontos_centrais")}
    else:
        content["graficos"] = charts_for_level(state.get("graficos") or [], level)
    return content


# Compatibilidade com o nome antigo do nó
advance_combo_node = finalize_combo_node


def _get(state: Any, name: str) -> Any:
    return state.get(name) if isinstance(state, dict) else getattr(state, name, None)


def route_next(state: Any) -> str:
    return _get(state, "next_action") or "end"


def route_after_deterministic(state: Any) -> str:
    action = _get(state, "next_action")
    return action if action in {"judge", "generate", "finalize"} else "finalize"


def route_after_judge(state: Any) -> str:
    action = _get(state, "next_action")
    return action if action in {"generate", "finalize"} else "finalize"


def route_after_human(state: Any) -> str:
    decision = _get(state, "human_decision")
    if decision == "aprovar":
        return "export"
    return "end"
