"""Tela Notícias: todos os cards, com filtro de até uma semana."""
import streamlit as st

from src.app.components.news_cards import load_recent_cards, render_news_grid
from src.app.level_selection import render_add_manual_button
from src.app.theme import page_header

PERIODOS = {"Hoje": 1, "Últimos 3 dias": 3, "Últimos 7 dias": 7}


def render_cards_screen(db_connection=None):
    page_header("Notícias", "A coleta junta a mesma notícia de fontes diferentes numa pauta: gere o relatório comparado "
                            "direto nela, gere materiais de um card ou marque \"Comparar\" em 2 a 5 cards. "
                            "O histórico vai até uma semana.")

    f1, f2 = st.columns([3, 2], vertical_alignment="bottom")
    periodo = f1.selectbox("Período", list(PERIODOS), index=2, key="periodo_cards")
    atualizar = f2.button("Atualizar cards manualmente", key="refresh_cards", disabled=db_connection is None)

    if atualizar:
        try:
            from src.collection.scheduler import run_collection

            result = run_collection(conn=db_connection)
            discarded = result.get("discarded") or []
            comparable = sum(1 for p in result.get("pautas", []) if p["independentes"] >= 2)
            st.success(f"Coleta concluída: {len(result['cards'])} cards de cunho financeiro e com texto completo "
                       f"({comparable} pauta(s) comparável(is) com 2+ fontes); {len(discarded)} itens descartados; "
                       f"{len(result['errors'])} erros de fonte. Acervo das últimas 72 h: "
                       f"{result.get('comparable_in_window', 0)} pauta(s) comparável(is).")
            if discarded:
                from collections import Counter

                with st.expander("Por que itens ficaram de fora"):
                    for reason, count in Counter(d["motivo"] for d in discarded).most_common():
                        st.caption(f"{count} × {reason}")
            for error in result["errors"]:
                st.caption(error)
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Coleta manual falhou: {exc}")

    cards, erro = load_recent_cards(db_connection, days=PERIODOS[periodo])
    if erro and db_connection is not None:
        st.warning(erro)
    render_news_grid(cards, key_prefix="list")
    from src.app.components.triangulation import render_selection_bar

    render_selection_bar(cards)
    render_add_manual_button()