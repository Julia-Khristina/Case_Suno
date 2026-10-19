"""Tela inicial: hero, três KPIs, últimas notícias e botão de entrada manual."""
from __future__ import annotations

import streamlit as st

from src.app.components.news_cards import load_recent_cards, render_news_grid
from src.app.level_selection import render_add_manual_button
from src.app.theme import agora, card_datetime, hero, kpi_card, navigate, section_title


# Início do dia em São Paulo. O banco roda em UTC: com CURRENT_DATE, das 21h às 24h (Brasília) "hoje" já era
# o dia seguinte e os indicadores zeravam (visto em 17/10/2026).
TODAY_SP = "(date_trunc('day', NOW() AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'America/Sao_Paulo')"


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

    # Notícias selecionadas hoje = documentos distintos que tiveram execução de geração hoje.
    selecionadas = _count(
        db_connection, f"SELECT COUNT(DISTINCT hash_documento) FROM execucoes WHERE criado_em >= {TODAY_SP}"
    )
    if selecionadas is None:
        queue = st.session_state.get("generation_queue", [])
        selecionadas = len({q.get("id_card") for q in queue})
    gerados = _count(db_connection, f"SELECT COUNT(*) FROM materiais WHERE criado_em >= {TODAY_SP}")
    if gerados is None:
        gerados = 0
    return {"hoje": cards_hoje, "delta": delta, "selecionadas": selecionadas, "gerados": gerados,
            "por_estado": _states_today(db_connection)}


def _states_today(db_connection) -> dict[str, int]:
    """Materiais de hoje por estado da revisão humana."""
    if db_connection is None:
        return {}
    try:
        with db_connection.cursor() as cur:
            cur.execute(f"SELECT estado, COUNT(*) FROM materiais WHERE criado_em >= {TODAY_SP} GROUP BY estado")
            return {state: int(n) for state, n in cur.fetchall()}
    except Exception:  # noqa: BLE001
        db_connection.rollback()
        return {}


def review_summary(by_state: dict[str, int]) -> str:
    """Ex.: "2 aprovados · 5 aguardando · 1 rejeitado" (editado conta como aguardando aprovação)."""
    approved = by_state.get("aprovado", 0)
    rejected = by_state.get("rejeitado", 0)
    waiting = sum(n for state, n in by_state.items() if state not in {"aprovado", "rejeitado"})
    plural = lambda n, one, many: f"{n} {one if n == 1 else many}"  # noqa: E731
    return " · ".join([plural(approved, "aprovado", "aprovados"), f"{waiting} aguardando",
                       plural(rejected, "rejeitado", "rejeitados")])


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
        sub = review_summary(kpis["por_estado"]) if kpis["gerados"] else "textos, carrosséis e roteiros"
        kpi_card("file", "Materiais gerados hoje", kpis["gerados"], sub)

    left, right = st.columns([6, 1], vertical_alignment="bottom")
    with left:
        section_title("Últimas notícias")
    with right:
        st.button("Ver todas ›", key="link_ver_todas", on_click=navigate, args=("noticias",))

    if erro and db_connection is not None:
        st.warning(erro)
    render_news_grid(cards, key_prefix="home", max_groups=6)
    render_add_manual_button()