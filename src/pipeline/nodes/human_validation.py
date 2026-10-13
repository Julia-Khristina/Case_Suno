"""Human validation and export gating."""
from typing import Any

from src.pipeline.nodes.evaluate_deterministic import evaluate_analytical_text
from src.shared.llm_client import LLMClient


class PendingTermsBlockApproval(Exception):
    """Raised or represented when pending terms block approval."""


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
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    pending_terms = pending_terms or []
    glossary_terms = glossary_terms or []
    forbidden_terms = forbidden_terms or []
    main_points = main_points or []

    if decision not in {"aprovar", "editar", "rejeitar"}:
        raise ValueError("Decisao invalida")

    if decision == "aprovar" and pending_terms:
        return {
            "decision": decision,
            "status": "bloqueado_por_termos_pendentes",
            "exports_enabled": False,
            "evaluation": None,
            "term_pending_blocked": True,
        }

    from src.persistence.repositories.decision_repository import DecisionRepository
    from src.persistence.repositories.material_repository import MaterialRepository

    material_repo = MaterialRepository(conn)
    decision_repo = DecisionRepository(conn)

    if decision == "aprovar":
        material_repo.set_state(material_id, "aprovado")
        decision_repo.create(material_id=material_id, decision="aprovar")
        return {
            "decision": decision,
            "status": "aprovado",
            "exports_enabled": True,
            "evaluation": None,
            "term_pending_blocked": False,
        }

    if decision == "rejeitar":
        material_repo.set_state(material_id, "rejeitado")
        decision_repo.create(material_id=material_id, decision="rejeitar")
        return {
            "decision": decision,
            "status": "rejeitado",
            "exports_enabled": False,
            "evaluation": None,
            "term_pending_blocked": False,
        }

    # editar
    evaluation = None
    final_content = edited_content
    if edited_content is not None and source_text is not None:
        from src.generation.models import AnalyticalText

        if isinstance(edited_content, dict):
            edited_content = AnalyticalText.model_validate(edited_content)
        evaluation = evaluate_analytical_text(
            analytical_text=edited_content,
            level="intermediario",
            source_text=source_text,
            main_points=main_points,
            glossary_terms=glossary_terms,
            forbidden_terms=forbidden_terms,
            thresholds=thresholds or {},
        )
        final_content = edited_content

    material_repo.set_state(material_id, "editado")
    material_repo.set_edited_content(material_id, final_content.model_dump() if hasattr(final_content, "model_dump") else final_content)
    decision_repo.create(material_id=material_id, decision="editar")
    return {
        "decision": decision,
        "status": "editado",
        "exports_enabled": False,
        "evaluation": evaluation,
        "term_pending_blocked": False,
    }