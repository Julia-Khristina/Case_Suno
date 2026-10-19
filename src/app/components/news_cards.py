"""Cards de notícia (grade de 2 colunas) e diálogo de seleção de níveis."""
from __future__ import annotations

import html
import re
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
_URL_RE = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)
_ATTR_RE = re.compile(r"\b[\w-]+=\s*[\"'][^\"']*[\"']")


def card_summary(value: str | None) -> str:
    """Descrição do card para exibição: sem marcação HTML (inclusive escapada em dobro), atributos soltos e URLs."""
    text = value or ""
    for _ in range(3):  # feeds às vezes escapam o HTML duas vezes (&amp;lt;img ...&amp;gt;)
        unescaped = html.unescape(text)
        if unescaped == text:
            break
        text = unescaped
    text = clean_html_text(text)
    text = _ATTR_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def category_label(value: str | None) -> str:
    """Categoria em texto legível: "acabou_de_acontecer" vira "Acabou de acontecer"."""
    text = (value or "").replace("_", " ").strip()
    return text[:1].upper() + text[1:]


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
    words = [w for w in re.split(r"[\s,]+", name) if w[:1].isalnum()]
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    return name[:2].upper()


def card_document(card: dict, db_connection=None) -> tuple[str, dict | None, str | None]:
    """Texto completo do documento do card: o já admitido para o card (arquivo no volume) ou a página do link.

    A descrição do card nunca é usada como documento: ela é um resumo de poucas linhas (seção 4.1).
    Retorna (texto, admissão, erro).
    """
    from src.admission.service import admit_url
    from src.app.db import is_usable, safe_rollback
    from src.pipeline.persistence import load_document_text

    card_id = card.get("id_card")
    if is_usable(db_connection) and card_id:
        try:
            with db_connection.cursor() as cur:
                cur.execute("SELECT hash FROM documentos WHERE id_card = %s ORDER BY criado_em DESC LIMIT 1", (card_id,))
                row = cur.fetchone()
            if row:
                text = load_document_text(row[0])
                if text:
                    return text, None, None
        except Exception:  # noqa: BLE001  sem documento salvo: segue para a leitura do link
            safe_rollback(db_connection)
    url = card.get("url_fonte") or card.get("url")
    if not url:
        return "", None, "O card não tem link para o documento de origem. Use a entrada manual e cole o texto."
    try:
        result = admit_url(str(url))
    except Exception as exc:  # noqa: BLE001
        if "login" in str(exc).lower():
            return "", None, "Não consegui acessar a página pois exige login, mande por texto"
        return "", None, f"Não foi possível ler o documento do card ({url}): {exc}"
    if result.status == "bloqueado":
        return "", None, "Conteúdo parcial (paywall ou texto incompleto): " + ", ".join(result.partial_reasons)
    return result.text, result.model_dump(mode="json"), None


@st.dialog("Gerar materiais")
def generation_dialog(card: dict) -> None:
    st.markdown(f"**{card.get('titulo', 'Card')}**")
    st.caption(f"Fonte: {card.get('nome_fonte', '—')}")
    niveis = st.multiselect("Níveis a gerar", LEVELS, default=LEVELS, format_func=LEVEL_LABELS.get)
    st.caption("Para cada nível selecionado, o sistema gera texto analítico, carrossel e roteiro de vídeo.")
    if st.button("Gerar selecionados", type="primary", disabled=not niveis, key="dlg_generate"):
        from src.app.level_selection import generate_and_report

        from src.app.db import get_connection

        db_connection = get_connection()
        text, admission, error = card_document(card, db_connection)
        if error:
            st.error(error)
            return
        origin = {"instituicao": card.get("nome_fonte"), "titulo": card.get("titulo"),
                  "data": str(card.get("data_card")) if card.get("data_card") else None,
                  "url": card.get("url_fonte") or card.get("url"), "tipo_origem": "card"}
        summary = generate_and_report(text, niveis, card.get("titulo", "Notícia coletada"),
                                      {k: v for k, v in origin.items() if v}, admission, db_connection)
        if summary is None:
            return
        st.session_state["page"] = "materiais"
        st.session_state["flash"] = "Materiais gerados para: " + ", ".join(LEVEL_LABELS[n] for n in niveis) + "."
        st.rerun()


def _render_card(card: dict, key_prefix: str) -> None:
    cid = str(card.get("id_card", id(card)))
    categoria = card.get("categoria")
    chip_html = chip(category_label(categoria)) if categoria else ""
    nome_fonte = card.get("nome_fonte") or "Fonte não informada"
    tempo = tempo_relativo(card_datetime(card))
    time_html = f'<span class="src-div"></span><span class="src-time">{esc(tempo)}</span>' if tempo else ""
    descricao = card_summary(card.get("descricao"))
    url = str(card.get("url") or "")

    with st.container(key=f"newscard_{key_prefix}_{cid}"):
        st.markdown(
            f'{chip_html}<div class="news-title">{esc(card.get("titulo", "Card"))}</div>'
            f'<p class="news-desc">{esc(descricao) or "Sem resumo no feed."}</p>',
            unsafe_allow_html=True,
        )
        from src.app.components.triangulation import selection_checkbox

        st.markdown('<div class="news-rule"></div>', unsafe_allow_html=True)
        c_src, c_gen = st.columns([3, 2], vertical_alignment="center")
        c_src.markdown(
            f'<div class="src"><span class="src-av">{esc(_initials(nome_fonte))}</span>'
            f'<span class="src-name">{esc(nome_fonte)}</span>{time_html}</div>',
            unsafe_allow_html=True,
        )
        if c_gen.button("Gerar materiais", key=f"gen_{key_prefix}_{cid}", icon=":material/arrow_forward:"):
            generation_dialog(card)
        selection_checkbox(card, key_prefix)


def group_cards(cards: list[dict]) -> list[list[dict]]:
    """Cards da mesma pauta juntos (na ordem do primeiro que aparece); fonte primária primeiro dentro da pauta.
    Card sem pauta é um grupo de um card só."""
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for card in cards:
        key = f"pauta:{card['id_pauta']}" if card.get("id_pauta") else f"card:{card.get('id_card', id(card))}"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(card)
    return [sorted(groups[k], key=lambda c: 0 if c.get("tipo_fonte") == "primaria" else 1) for k in order]


def _source_line(card: dict) -> str:
    nome_fonte = card.get("nome_fonte") or "Fonte não informada"
    tempo = tempo_relativo(card_datetime(card))
    time_html = f'<span class="src-div"></span><span class="src-time">{esc(tempo)}</span>' if tempo else ""
    return (f'<div class="src"><span class="src-av">{esc(_initials(nome_fonte))}</span>'
            f'<span class="src-name">{esc(nome_fonte)}</span>{time_html}</div>')


def _render_pauta(members: list[dict], key_prefix: str, all_cards: list[dict]) -> None:
    """Card de pauta: a mesma notícia em fontes diferentes, pronta para o relatório comparado."""
    from src.app.components.triangulation import selected_cards, triangulation_dialog

    lead = members[0]
    pid = str(lead.get("id_pauta"))
    independentes = lead.get("pauta_independentes") or len(members)
    categoria = lead.get("categoria")
    chips = (chip(category_label(categoria)) if categoria else "") + (
        f'<span class="chip pauta-chip">Comparável · {len(members)} fontes</span>' if independentes >= 2 else
        f'<span class="chip pauta-chip mute">{len(members)} fontes · mesma origem</span>')
    rows = "".join(
        f'<div class="pauta-row">{_source_line(card)}<div class="pauta-title">{esc(card.get("titulo", ""))}</div></div>'
        for card in members)
    with st.container(key=f"newscard_{key_prefix}_pauta_{pid}"):
        st.markdown(
            f'<div class="chips-row">{chips}</div><div class="news-title">{esc(lead.get("titulo", "Card"))}</div>'
            f'<p class="news-desc">{esc(card_summary(lead.get("descricao"))) or "Sem resumo no feed."}</p>'
            f'<div class="pauta-list">{rows}</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="news-rule"></div>', unsafe_allow_html=True)
        c_cmp, c_gen = st.columns([3, 2], vertical_alignment="center")
        if c_cmp.button("Gerar relatório comparado", key=f"cmpgen_{key_prefix}_{pid}", type="primary",
                        icon=":material/compare_arrows:", disabled=independentes < 2,
                        help="Relatório analítico que mostra, lado a lado, o que cada fonte diz sobre a notícia."):
            chosen = selected_cards()
            chosen.clear()
            chosen.update({str(card.get("id_card")): card for card in members})
            triangulation_dialog(all_cards)
        if c_gen.button("Gerar materiais", key=f"gen_{key_prefix}_{lead.get('id_card')}", icon=":material/arrow_forward:",
                        help=f"Materiais a partir de uma fonte só: {lead.get('nome_fonte')}."):
            generation_dialog(lead)
        chosen = selected_cards()
        ids = [str(card.get("id_card")) for card in members]
        checked = st.checkbox("Comparar", value=all(i in chosen for i in ids), key=f"cmp_{key_prefix}_pauta_{pid}",
                              help="Inclui todas as fontes desta pauta na comparação com outros cards.")
        if checked:
            chosen.update({i: card for i, card in zip(ids, members)})
        elif all(i in chosen for i in ids):
            for i in ids:
                chosen.pop(i, None)


def render_news_grid(cards: list[dict], key_prefix: str, empty_message: str | None = None,
                     max_groups: int | None = None) -> None:
    if not cards:
        empty_state(empty_message or "Nenhuma notícia carregada. Use a coleta ou a entrada manual.")
        return
    groups = group_cards(cards)
    groups = groups[:max_groups] if max_groups else groups
    # pautas comparáveis primeiro, preservando a ordem (mais recentes) dentro de cada tipo
    groups = [g for g in groups if len(g) > 1] + [g for g in groups if len(g) == 1]
    for i in range(0, len(groups), 2):
        cols = st.columns(2, gap="medium")
        for col, group in zip(cols, groups[i : i + 2]):
            with col:
                if len(group) > 1:
                    _render_pauta(group, key_prefix, cards)
                else:
                    _render_card(group[0], key_prefix)