"""Human validation and export gating (seção 4.8).

Aprovar, editar (com reavaliação pelas métricas determinísticas, no nível e formato do material, preservando a
versão gerada) e rejeitar. Termos pendentes bloqueiam a aprovação. Exportações só depois de aprovar.
"""
from __future__ import annotations

import json
from typing import Any

from src.pipeline.nodes.evaluate_deterministic import evaluate_analytical_text


class PendingTermsBlockApproval(Exception):
    """Raised or represented when pending terms block approval."""


def parse_edited_content(fmt: str, edited: Any, original: dict | None) -> dict:
    """Converte o conteúdo editado (Markdown do texto, JSON do carrossel/roteiro ou dict) para o contrato do formato."""
    from src.export.text_export import from_markdown
    from src.generation.models import AnalyticalText, Carousel, Script

    if isinstance(edited, dict) and "texto" in edited and len(edited) == 1:
        edited = edited["texto"]
    if isinstance(edited, str):
        edited = from_markdown(edited, original) if fmt == "texto_analitico" else json.loads(edited)
    model = {"texto_analitico": AnalyticalText, "carrossel": Carousel, "roteiro_video": Script}[fmt]
    return model.model_validate(edited).model_dump(mode="json")


def _material_context(conn, material_id: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT m.nivel, m.formato, m.conteudo_gerado, e.hash_documento, d.instituicao_origem, d.titulo_origem,
                      d.data_origem, d.url_origem, m.conteudo_editado
               FROM materiais m LEFT JOIN execucoes e ON e.id_execucao = m.id_execucao
               LEFT JOIN documentos d ON d.hash = e.hash_documento WHERE m.id_material = %s""",
            (material_id,),
        )
        row = cur.fetchone()
    if row is None:
        return {}
    keys = ["nivel", "formato", "conteudo_gerado", "hash_documento", "instituicao", "titulo", "data", "url",
            "conteudo_editado"]
    return dict(zip(keys, row))


REJECTION_CATEGORIES = ["Erro factual", "Nível errado", "Texto confuso", "Fora do tema", "Formato ou tamanho",
                        "Tom ou linguagem", "Outro"]


def rejection_note(categories: list[str] | None, reason: str | None) -> str:
    """Observação gravada na rejeição: "[Erro factual; Nível errado] texto livre"."""
    tags = "; ".join(c for c in (categories or []) if c)
    text = (reason or "").strip()
    return f"[{tags}] {text}".strip() if tags else text


def apply_human_decision(
    conn,
    material_id: str,
    decision: str,
    edited_content: Any = None,
    pending_terms: list[Any] | None = None,
    source_text: str | None = None,
    main_points: list[str] | None = None,
    glossary_terms: list[str] | None = None,
    forbidden_terms: list[str] | None = None,
    thresholds: dict | None = None,
    llm_client=None,
    level: str | None = None,
    fmt: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Aplica a decisão da revisora e grava a observação (`note`) em decisoes_humanas.

    Rejeitar exige motivo. Material rejeitado é estado final: aprovar ou editar ficam bloqueados até "reabrir"
    (que volta o material para aguardando revisão e também fica registrado).
    """
    pending_terms = pending_terms or []
    note = (note or "").strip() or None
    if decision not in {"aprovar", "editar", "rejeitar", "reabrir"}:
        raise ValueError("Decisao invalida")
    if decision == "rejeitar" and not note:
        raise ValueError("Informe o motivo da rejeição.")
    if decision == "editar" and not note:
        raise ValueError("Descreva na observação o que foi editado.")

    if decision == "aprovar" and pending_terms:
        return {"decision": decision, "status": "bloqueado_por_termos_pendentes", "exports_enabled": False,
                "evaluation": None, "term_pending_blocked": True}

    from src.persistence.repositories.decision_repository import DecisionRepository
    from src.persistence.repositories.material_repository import MaterialRepository

    material_repo = MaterialRepository(conn)
    decision_repo = DecisionRepository(conn)
    current = material_repo.get_state(material_id)

    if current == "rejeitado" and decision in {"aprovar", "editar"}:
        return {"decision": decision, "status": "bloqueado_material_rejeitado", "exports_enabled": False,
                "evaluation": None, "term_pending_blocked": False}
    if decision == "reabrir":
        if current != "rejeitado":
            return {"decision": decision, "status": current, "exports_enabled": current == "aprovado",
                    "evaluation": None, "term_pending_blocked": False}
        material_repo.set_state(material_id, "aguardando_revisao")
        decision_repo.create(material_id=material_id, decision="reabrir", note=note)
        return {"decision": decision, "status": "aguardando_revisao", "exports_enabled": False, "evaluation": None,
                "term_pending_blocked": False}

    if decision in {"aprovar", "rejeitar"}:
        state = "aprovado" if decision == "aprovar" else "rejeitado"
        material_repo.set_state(material_id, state)
        decision_repo.create(material_id=material_id, decision=decision, note=note)
        return {"decision": decision, "status": state, "exports_enabled": decision == "aprovar", "evaluation": None,
                "term_pending_blocked": False}

    # editar: reavalia no nível e formato do material e preserva o conteúdo gerado
    context = _material_context(conn, material_id)
    level = level or context.get("nivel") or "intermediario"
    fmt = fmt or context.get("formato") or "texto_analitico"
    if source_text is None and context.get("hash_documento"):
        from src.pipeline.persistence import load_document_text

        source_text = load_document_text(context["hash_documento"])
    evaluation = None
    final_content = edited_content
    if edited_content is None:
        raise ValueError("Editar exige o conteúdo alterado.")
    if edited_content is not None:
        final_content = parse_edited_content(fmt, edited_content, context.get("conteudo_gerado"))
        current = context.get("conteudo_editado") or context.get("conteudo_gerado")
        try:
            unchanged = current is not None and final_content == parse_edited_content(fmt, current,
                                                                                      context.get("conteudo_gerado"))
        except Exception:  # noqa: BLE001  versão guardada fora do contrato atual: trata como alterado
            unchanged = False
        if unchanged:
            raise ValueError("O conteúdo não foi alterado: para manter como está, aprove; para descartar, rejeite.")
        if source_text:
            origin = {k: context.get(k) for k in ("instituicao", "titulo", "data", "url") if context.get(k)}
            evaluation = evaluate_analytical_text(final_content, level=level, source_text=source_text,
                                                  main_points=main_points or [], forbidden_terms=forbidden_terms,
                                                  thresholds=thresholds, origin=origin or None, fmt=fmt)
    material_repo.set_state(material_id, "editado")
    if final_content is not None:
        material_repo.set_edited_content(material_id, final_content)
    decision_repo.create(material_id=material_id, decision="editar", note=note)
    return {"decision": decision, "status": "editado", "exports_enabled": False, "evaluation": evaluation,
            "term_pending_blocked": False}


class RegenerationUnavailable(Exception):
    """A regeração não pode refazer este material (ex.: relatório comparado de várias fontes)."""


def regenerate_rejected(conn, material_id: str, deps=None) -> dict[str, Any]:
    """"Rejeitar e gerar de novo": gera uma nova versão só deste nível e formato, na mesma execução, levando o
    motivo da última rejeição como orientação. Passa pelo mesmo ciclo (métricas, reescritas e juiz).

    Chama o modelo de linguagem (extração, que pode vir do cache, e até 3 tentativas de geração + juiz).
    """
    from src.persistence.repositories.decision_repository import DecisionRepository
    from src.persistence.repositories.material_repository import MaterialRepository
    from src.pipeline.persistence import PostgresPersistence, load_document_text

    if MaterialRepository(conn).get_state(material_id) != "rejeitado":
        raise RegenerationUnavailable("Só um material rejeitado (com motivo) pode ser gerado de novo.")
    with conn.cursor() as cur:
        cur.execute("""SELECT m.nivel, m.formato, m.id_execucao, e.hash_documento, d.instituicao_origem, d.titulo_origem,
                              d.data_origem, d.url_origem, d.tipo_origem,
                              EXISTS (SELECT 1 FROM materiais o WHERE o.id_execucao = m.id_execucao
                                      AND jsonb_typeof(o.conteudo_gerado->'triangulacao') = 'object') AS triangulado,
                              (SELECT observacao FROM decisoes_humanas h WHERE h.id_material = m.id_material
                                 AND h.decisao = 'rejeitar' ORDER BY h.criado_em DESC LIMIT 1) AS motivo
                       FROM materiais m JOIN execucoes e ON e.id_execucao = m.id_execucao
                       LEFT JOIN documentos d ON d.hash = e.hash_documento WHERE m.id_material = %s""", (material_id,))
        row = cur.fetchone()
    conn.rollback()
    if row is None:
        raise RegenerationUnavailable("Material não encontrado.")
    level, fmt, execution_id, doc_hash, inst, title, date, url, origin_type, triangulated, reason = row
    if triangulated:
        raise RegenerationUnavailable("Relatório comparado (várias fontes): gere de novo pela pauta na tela Notícias, "
                                      "para reler as fontes e refazer a matriz.")
    if not reason:
        raise RegenerationUnavailable("A rejeição não tem motivo registrado.")
    text = load_document_text(doc_hash) if doc_hash else None
    if not text:
        raise RegenerationUnavailable("O texto do documento original não está mais disponível no volume.")

    from src.pipeline.deps import PipelineDeps
    from src.pipeline.graph import run_pipeline

    origin = {k: v for k, v in {"instituicao": inst, "titulo": title, "data": str(date) if date else None, "url": url,
                                "tipo_origem": origin_type}.items() if v}
    deps = deps or PipelineDeps(persistence=PostgresPersistence(conn))
    final = run_pipeline(text, [level], origin=origin, deps=deps, execution_id=str(execution_id),
                         combos=[f"{level}:{fmt}"], human_feedback=reason)
    output = (final.get("generated_outputs") or {}).get(f"{level}:{fmt}") or {}
    new_id = output.get("material_id")
    DecisionRepository(conn).create(material_id=material_id, decision="regenerar",
                                    note=f"nova versão: {new_id}" if new_id else "nova versão não gerada")
    return {"id_material_novo": new_id, "status": output.get("status"), "aviso": output.get("aviso"),
            "erros": final.get("errors") or [], "tokens": final.get("token_count", 0), "motivo": reason}
