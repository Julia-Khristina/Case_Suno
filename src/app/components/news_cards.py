"""Cards de notícia (grade de 2 colunas) e diálogo de seleção de níveis."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.app.theme import (
    TZ,
    card_datetime,
    chip,
    empty_state,
    esc,
    tempo_relativo,
)

from src.collection.cleaner import clean_html_text

LEVELS = ["iniciante", "intermediario", "avancado"]
LEVEL_LABELS = {"iniciante": "Iniciante", "intermediario": "Intermediário", "avancado": "Avançado"}


def load_recent_cards(db_connection, days: int = 7):
    """Retorna (cards ordenados do mais recente ao mais antigo, mensagem de erro ou None)."""
    if db_connection is None:
        return [], "Banco indisponível."
    try:
        from src.persistence.repositories.card_repository import CardRepository

        cards = list(CardRepository(db_connection).list_recent(days=days))
    except Exception as exc:  # noqa: BLE001
        return [], f"Não foi possível carregar os cards: {exc}"
    floor = datetime.min.replace(tzinfo=TZ)
    cards.sort(key=lambda c: card_datetime(c) or floor, reverse=True)
    return cards, None


def _initials(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return "?"
    if len(name) <= 2:
        return name.upper()
    return name[0].upper()


@st.dialog("Gerar materiais")
def generation_dialog(card: dict) -> None:
    st.markdown(f"**{card.get('titulo', 'Card')}**")
    st.caption(f"Fonte: {card.get('nome_fonte', '—')}")
    niveis = st.multiselect("Níveis a gerar", LEVELS, default=LEVELS, format_func=LEVEL_LABELS.get)
    st.caption("Para cada nível selecionado, o sistema gera texto analítico, carrossel e roteiro de vídeo.")
    if st.button("Gerar selecionados", type="primary", disabled=not niveis, key="dlg_generate"):
        from src.app.level_selection import _generate_manual_materials

        raw_content = card.get("descricao") or card.get("desc") or card.get("titulo") or ""
        raw_content = clean_html_text(raw_content)
        with st.spinner("Gerando materiais dos níveis selecionados..."):
            generated = _generate_manual_materials(raw_content, niveis, card.get("titulo", "Notícia coletada"))
        st.session_state.setdefault("generation_queue", []).extend(generated)
        st.session_state["page"] = "materiais"
        st.session_state["flash"] = "Materiais gerados para: " + ", ".join(LEVEL_LABELS[n] for n in niveis) + "."
        st.rerun()


def _render_card(card: dict, key_prefix: str) -> None:
    cid = str(card.get("id_card", id(card)))
    categoria = card.get("categoria")
    chip_html = chip(categoria) if categoria else ""
    nome_fonte = card.get("nome_fonte") or "Fonte não informada"
    tempo = tempo_relativo(card_datetime(card))
    time_html = f'<span class="src-div"></span><span class="src-time">{esc(tempo)}</span>' if tempo else ""
    url = str(card.get("url") or "")

    with st.container(key=f"newscard_{key_prefix}_{cid}"):
        st.markdown(
            f'{chip_html}<div class="news-title">{esc(card.get("titulo", "Card"))}</div>'
            f'<p class="news-desc">{esc(clean_html_text(card.get("descricao", "")))}</p>',
            unsafe_allow_html=True,
        )
        c_src, c_gen, c_ext = st.columns([6, 2.6, 0.7], vertical_alignment="center")
        c_src.markdown(
            f'<div class="src"><span>{esc(nome_fonte)}{time_html}</span></div>',
            unsafe_allow_html=True,
        )
        if c_gen.button("Gerar materiais", key=f"gen_{key_prefix}_{cid}"):
            generation_dialog(card)
        # external link image removed per request


def render_news_grid(cards: list[dict], key_prefix: str, empty_message: str | None = None) -> None:
    if not cards:
        empty_state(empty_message or "Nenhuma notícia carregada. Use a coleta ou a entrada manual.")
        return
    for i in range(0, len(cards), 2):
        cols = st.columns(2, gap="medium")
        for col, card in zip(cols, cards[i : i + 2]):
            with col:
                _render_card(card, key_prefix)