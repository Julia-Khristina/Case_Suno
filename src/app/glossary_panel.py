"""Painel do glossário."""
import streamlit as st
import yaml

from src.app.theme import section_title, table_html


def render_glossary_panel():
    section_title("Painel do glossário")
    path = "config/glossario.yaml"
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
    except FileNotFoundError:
        data = {"termos": []}

    terms = data.get("termos", [])
    st.caption(f"Termos cadastrados: {len(terms)}")
    if terms:
        st.markdown(table_html(["Termo"], [[str(item)] for item in terms]), unsafe_allow_html=True)

    with st.container(key="panel_glossary"):
        new_term = st.text_input("Novo termo")
        if st.button("Adicionar termo pendente de aprovação", type="primary"):
            if new_term.strip():
                terms.append(new_term.strip())
                data["termos"] = terms
                with open(path, "w", encoding="utf-8") as file:
                    yaml.safe_dump(data, file, allow_unicode=True, sort_keys=False)
                st.success("Termo adicionado ao glossário configurado.")