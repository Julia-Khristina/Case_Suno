"""Exibição segura de texto gerado no Streamlit.

st.markdown e st.caption interpretam `$...$` como fórmula LaTeX: em "R$ 12 bilhões ... R$ 1 bilhão" o trecho entre
os dois cifrões vira fórmula e os "$" somem. Todo texto gerado passa por `md_safe` antes de ser exibido.
"""
from __future__ import annotations


def md_safe(text: str | None) -> str:
    """Escapa o cifrão (e só ele) para o Markdown do Streamlit não abrir modo matemático."""
    return (text or "").replace("\\$", "$").replace("$", "\\$")
