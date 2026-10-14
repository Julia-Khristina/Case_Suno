"""Tela de validação humana."""
import streamlit as st

from src.app.status_stream import render_queue
from src.persistence.repositories.material_repository import MaterialRepository
from src.export.text_export import to_markdown
from src.generation.models import AnalyticalText
from src.app.theme import esc, section_title

from src.pipeline.nodes.human_validation import apply_human_decision


def render_validation_screen(material_id: str = "", db_connection=None, pending_terms: list[str] | None = None):
    pending_terms = pending_terms or []
    section_title("Validação humana")
    render_queue(st.session_state.get("generation_queue", []))

    rows = MaterialRepository(db_connection).list_materials() if db_connection is not None else []
    if not rows:
        st.caption("Nenhum material disponível para validação.")
        return
    options = {str(row["id_material"]): f"{str(row['id_material'])[:8]} · {row['nivel']} · {row['formato']} · {row['estado']}" for row in rows}
    requested_id = str(material_id or "").strip()
    default_id = requested_id if requested_id in options else next(
        (str(row["id_material"]) for row in rows if row.get("estado") in {"na_fila", "gerado", "editado"}),
        str(rows[0]["id_material"]),
    )
    selected_id = st.selectbox(
        "Selecione o material",
        list(options),
        index=list(options).index(default_id),
        format_func=lambda item: options[item],
        key="validation_material_selector",
    )
    selected_row = next(row for row in rows if str(row["id_material"]) == str(selected_id))

    with st.container(key="panel_validation"):
        st.markdown(
            f'<div class="meta">Material: <b>{esc(selected_id)}</b> · Nível: <b>{esc(selected_row.get("nivel"))}</b> · Estado: <b>{esc(selected_row.get("estado"))}</b></div>',
            unsafe_allow_html=True,
        )
        if pending_terms:
            st.warning("Termos pendentes bloqueiam a aprovação: " + ", ".join(pending_terms))
        selected_content = selected_row.get("conteudo_editado") or selected_row.get("conteudo_gerado")
        initial_text = ""
        try:
            if isinstance(selected_content, dict):
                a = AnalyticalText.model_validate(selected_content)
                initial_text = "\\n\\n".join(
                    [f"# {a.title}", a.subtitle, "## Introducao", a.introduction, "## Desenvolvimento", a.development, "## Analise", a.analysis, "## Conclusao", a.conclusion]
                )
            else:
                initial_text = str(selected_content or "")
        except Exception:
            initial_text = str(selected_content or "")
        text_key = f"validation_text_{selected_id}"
        if text_key not in st.session_state:
            st.session_state[text_key] = initial_text
        content = st.text_area("Texto gerado / editado", height=240, key=text_key)
        observation = st.text_input("Observação")
        col1, col2, col3 = st.columns(3)
        aprovar = col1.button("Aprovar", type="primary", disabled=bool(pending_terms))
        editar = col2.button("Editar")
        rejeitar = col3.button("Rejeitar")
        decision = None
        outcome = None
        if db_connection is not None and str(selected_id).strip():
            try:
                if aprovar:
                    decision = "aprovar"
                    outcome = apply_human_decision(
                        db_connection,
                        str(selected_id).strip(),
                        "aprovar",
                        pending_terms=pending_terms,
                    )
                elif editar:
                    decision = "editar"
                    outcome = apply_human_decision(
                        db_connection,
                        str(selected_id).strip(),
                        "editar",
                        edited_content={"texto": content.strip()} if content.strip() else None,
                        pending_terms=pending_terms,
                    )
                elif rejeitar:
                    decision = "rejeitar"
                    outcome = apply_human_decision(
                        db_connection,
                        str(selected_id).strip(),
                        "rejeitar",
                        pending_terms=pending_terms,
                    )
            except Exception as exc:  # noqa: BLE001
                st.error(f"Falha ao registrar decisão: {exc}")
        elif (aprovar or editar or rejeitar) and db_connection is None:
            st.info("Banco indisponível: decisão não persistida.")

        if outcome:
            status = outcome.get("status")
            if status == "bloqueado_por_termos_pendentes":
                st.warning("Termos pendentes bloqueiam a aprovação.")
            elif status == "aprovado":
                st.success("Material aprovado. Exportações ativadas.")
            elif status == "editado":
                st.success("Edição registrada e material marcado como editado.")
            elif status == "rejeitado":
                st.info("Material rejeitado.")
            if outcome.get("exports_enabled") and isinstance(selected_content, dict):
                try:
                    approved_text = AnalyticalText.model_validate(selected_content)
                    st.download_button(
                        "Baixar texto aprovado (Markdown)",
                        data=to_markdown(approved_text),
                        file_name=f"material-{selected_id}.md",
                        mime="text/markdown",
                        key=f"download_md_{selected_id}",
                    )
                except Exception:
                    st.caption("Texto não pôde ser exportado.")
            decision = status

        if decision and not outcome:
            st.session_state["last_human_decision"] = decision
        decision = decision or st.session_state.get("last_human_decision")
        if decision:
            st.caption(f"Última decisão: {decision}")
        if observation:
            st.caption(f"Observação registrada: {observation}")
        if content.strip():
            st.caption("Exportações ficam ativas somente após aprovação.")