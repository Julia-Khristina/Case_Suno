"""Streamlit validation screen skeleton."""
import streamlit as st


def render_validation_screen(material_id: str, pending_terms: list[str] | None = None):
    pending_terms = pending_terms or []
    st.subheader("Validacao humana")
    if pending_terms:
        st.warning("Termos pendentes bloqueiam a aprovacao: " + ", ".join(pending_terms))
    col1, col2, col3 = st.columns(3)
    if col1.button("Aprovar"):
        st.session_state["human_decision"] = "aprovar"
    if col2.button("Editar"):
        st.session_state["human_decision"] = "editar"
    if col3.button("Rejeitar"):
        st.session_state["human_decision"] = "rejeitar"
    return st.session_state.get("human_decision")