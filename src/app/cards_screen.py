"""Tela Notícias: todos os cards, com filtro de até uma semana."""
import streamlit as st

from src.app.components.news_cards import load_recent_cards, render_news_grid
from src.app.level_selection import render_add_manual_button
from src.app.theme import page_header

PERIODOS = {"Hoje": 1, "Últimos 3 dias": 3, "Últimos 7 dias": 7}


def render_cards_screen(db_connection=None):
    page_header("Notícias", "Selecione um card para escolher os níveis de geração. O histórico vai até uma semana.")

    f1, f2 = st.columns([3, 2], vertical_alignment="bottom")
    periodo = f1.selectbox("Período", list(PERIODOS), index=2, key="periodo_cards")
    atualizar = f2.button("Atualizar cards manualmente", key="refresh_cards", disabled=db_connection is None)

    if atualizar:
        try:
            from src.collection.scheduler import run_collection

            result = run_collection(conn=db_connection)
            st.success(f"Coleta concluída: {len(result['cards'])} cards, {len(result['errors'])} erros.")
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Coleta manual falhou: {exc}")

    cards, erro = load_recent_cards(db_connection, days=PERIODOS[periodo])
    if erro and db_connection is not None:
        st.warning(erro)
    render_news_grid(cards, key_prefix="list")
    render_add_manual_button()