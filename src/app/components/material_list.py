"""Lista de materiais gerados recentemente."""
from __future__ import annotations

import json
from datetime import datetime

import streamlit as st


def render_recent_materials(db_connection=None) -> None:
    if db_connection is None:
        st.caption("Conecte o banco para exibir os materiais gerados.")
        return
    try:
        with db_connection.cursor() as cur:
            cur.execute(
                """
                SELECT nivel, formato, estado, conteudo_gerado, criado_em
                FROM materiais
                WHERE DATE(criado_em) = CURRENT_DATE
                ORDER BY nivel, criado_em DESC
                """
            )
            rows = cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        st.caption(f"Não foi possível carregar materiais: {exc}")
        return

    if not rows:
        st.caption("Nenhum material gerado hoje.")
        return
    for nivel, formato, estado, conteudo, criado_em in rows:
        content = conteudo if isinstance(conteudo, dict) else {}
        title = content.get("title") or f"Material {nivel}"
        with st.expander(f"{nivel} · {formato} · {estado}", expanded=False):
            if isinstance(criado_em, datetime):
                st.caption(criado_em.strftime("%d/%m/%Y %H:%M"))
            if content:
                st.markdown(f"**{title}**")
                introduction = content.get("introduction")
                if introduction:
                    st.text(introduction[:1000])