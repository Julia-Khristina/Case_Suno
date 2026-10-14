"""Tela inicial: hero, três KPIs, últimas notícias e botão de entrada manual."""
from __future__ import annotations

import streamlit as st

from src.app.components.news_cards import load_recent_cards, render_news_grid
from src.app.level_selection import render_add_manual_button
from src.app.theme import agora, card_datetime, hero, kpi_card, navigate, section_title


def _count(db_connection, sql: str):
    """Executa um COUNT e devolve int (ou None se a consulta falhar)."""
    if db_connection is None:
        return None
    try:
        with db_connection.cursor() as cur:
            cur.execute(sql)
            return int(cur.fetchone()[0])
    except Exception:  # noqa: BLE001
        try:
            db_connection.rollback()  # evita deixar a transação abortada
        except Exception:  # noqa: BLE001
            pass
        return None


def _kpis(db_connection, cards: list[dict]) -> dict:
    hoje = agora().date()
    cards_hoje = sum(1 for c in cards if (dt := card_datetime(c)) and dt.date() == hoje)
    media = len(cards) / 7 if cards else 0
    delta = round((cards_hoje / media - 1) * 100) if media else None

    # Colunas assumidas na tabela `materiais`: id_card e criado_em (ajuste se o esquema for outro).
    selecionadas = _count(
        db_connection, "SELECT COUNT(DISTINCT id_card) FROM materiais WHERE criado_em >= CURRENT_DATE"
    )
    if selecionadas is None:
        queue = st.session_state.get("generation_queue", [])
        selecionadas = len({q.get("id_card") for q in queue})
    gerados = _count(db_connection, "SELECT COUNT(*) FROM materiais WHERE criado_em >= CURRENT_DATE")
    if gerados is None:
        gerados = 0
    return {"hoje": cards_hoje, "delta": delta, "selecionadas": selecionadas, "gerados": gerados}


def render_suno_dashboard(db_connection=None) -> None:
    cards, erro = load_recent_cards(db_connection, days=7)
    kpis = _kpis(db_connection, cards)

    hero()

    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        if kpis["delta"] is None:
            kpi_card("newspaper", "Notícias por dia", kpis["hoje"], "sem média da semana ainda")
        else:
            sinal = "+" if kpis["delta"] >= 0 else ""
            kpi_card(
                "newspaper", "Notícias por dia", kpis["hoje"],
                f"{sinal}{kpis['delta']}% em relação à média da semana", delta=kpis["delta"],
            )
    with c2:
        kpi_card("filter", "Notícias selecionadas", kpis["selecionadas"], "para geração dos materiais")
    with c3:
        kpi_card("file", "Materiais gerados hoje", kpis["gerados"], "textos, carrosséis e roteiros")

    left, right = st.columns([6, 1], vertical_alignment="bottom")
    with left:
        section_title("Últimas notícias")
    with right:
        st.button("Ver todas ›", key="link_ver_todas", on_click=navigate, args=("noticias",))

    if erro and db_connection is not None:
        st.warning(erro)
    render_news_grid(cards[:6], key_prefix="home")
    render_add_manual_button()