"""Triangulação na tela de Notícias: o usuário marca de 2 a 5 cards sobre o mesmo assunto, o sistema sugere
cards relacionados e mostra quais compartilham origem; a geração usa o texto analítico triangulado."""
from __future__ import annotations

import streamlit as st

from src.app.components.news_cards import LEVEL_LABELS, LEVELS, card_document
from src.app.text import md_safe

SESSION_KEY = "triangular_cards"
MIN_SOURCES, MAX_SOURCES = 2, 5


def selected_cards() -> dict[str, dict]:
    return st.session_state.setdefault(SESSION_KEY, {})


def selection_checkbox(card: dict, key_prefix: str) -> None:
    """Caixa "Comparar" no card; guarda a seleção na sessão."""
    cid = str(card.get("id_card"))
    chosen = selected_cards()
    checked = st.checkbox("Comparar", value=cid in chosen, key=f"cmp_{key_prefix}_{cid}",
                          help="Marque de 2 a 5 notícias sobre o mesmo assunto para um relatório triangulado.")
    if checked and cid not in chosen:
        chosen[cid] = card
    elif not checked and cid in chosen:
        chosen.pop(cid)


def _card_item(card: dict):
    from src.collection.pautas import PautaItem

    # sem fonte informada, cada card conta como fonte própria (a regra de pauta não liga notícias da mesma fonte)
    return PautaItem.from_item({**card, "nome_fonte": card.get("nome_fonte") or f"card {card.get('id_card')}",
                                "data_publicacao": card.get("data_card")}, key=str(card.get("id_card")))


def related_score(card: dict, reference: list[dict], corpus=None) -> float:
    """Afinidade de assunto pela mesma regra das pautas da coleta (src/collection/pautas.py): cosseno TF-IDF do
    título e da descrição, só quando há nome/sigla/ticker específico em comum (ou texto muito parecido), fonte
    diferente e data na janela. Data próxima ou vocabulário genérico de mercado sozinhos não contam."""
    from src.collection.pautas import Corpus, similarity

    item = _card_item(card)
    refs = [_card_item(ref) for ref in reference]
    corpus = corpus or Corpus.build([item, *refs])
    return max((similarity(item, ref, corpus) for ref in refs), default=0.0)


def with_stored_text(db_connection, cards: list[dict]) -> list[dict]:
    """Cards com o começo do texto guardado na coleta (`conteudo`), para a afinidade usar mais que o título."""
    from src.app.db import is_usable, safe_rollback
    from src.pipeline.persistence import load_document_text

    ids = [str(card.get("id_card")) for card in cards if card.get("id_card")]
    if not is_usable(db_connection) or not ids:
        return cards
    try:
        with db_connection.cursor() as cur:
            cur.execute("SELECT DISTINCT ON (id_card) id_card::text, hash FROM documentos "
                        "WHERE id_card::text = ANY(%s) ORDER BY id_card, criado_em DESC", (ids,))
            hashes = dict(cur.fetchall())
    except Exception:  # noqa: BLE001  sem os textos, a afinidade usa só título e descrição
        safe_rollback(db_connection)
        return cards
    enriched = []
    for card in cards:
        text = load_document_text(hashes[str(card.get("id_card"))]) if str(card.get("id_card")) in hashes else None
        enriched.append({**card, "conteudo": " ".join(text.split()[:250])} if text else card)
    return enriched


def suggestions(all_cards: list[dict], chosen: dict[str, dict], limit: int = 5, minimum: float = 0.2) -> list[tuple[dict, float]]:
    """Cards de outras fontes sobre o mesmo assunto. O limiar é mais baixo que o das pautas (título e descrição
    são curtos e a sugestão nunca entra sozinha), mas a exigência de entidade específica em comum é a mesma."""
    from src.collection.pautas import Corpus

    reference = list(chosen.values())
    corpus = Corpus.build([_card_item(card) for card in all_cards])
    scored = [(card, related_score(card, reference, corpus)) for card in all_cards
              if str(card.get("id_card")) not in chosen]
    return [item for item in sorted(scored, key=lambda kv: -kv[1]) if item[1] >= minimum][:limit]


def render_selection_bar(all_cards: list[dict]) -> None:
    chosen = selected_cards()
    if not chosen:
        return
    st.divider()
    names = ", ".join(c.get("nome_fonte", "fonte") for c in chosen.values())
    left, right = st.columns([4, 2], vertical_alignment="center")
    left.markdown(md_safe(f"**{len(chosen)} notícia(s) para comparar:** {names}"))
    if right.button(f"Triangular {len(chosen)} fonte(s)", type="primary", key="open_triangulation",
                    disabled=len(chosen) < 1):
        triangulation_dialog(all_cards)


@st.dialog("Relatório triangulado", width="large")
def triangulation_dialog(all_cards: list[dict]) -> None:
    from src.triangulacao.origem_comum import detectar_origem_comum

    chosen = selected_cards()
    st.caption("O texto analítico compara o que cada fonte diz: convergências, divergências lado a lado e gráficos. "
               "Fontes de mesma origem contam como uma só.")
    for card in chosen.values():
        st.markdown(md_safe(f"- **{card.get('nome_fonte')}** — {card.get('titulo')}"))

    from src.app.db import get_connection as _connection

    enriched = with_stored_text(_connection(), all_cards)
    by_id = {str(card.get("id_card")): card for card in enriched}
    related = suggestions(enriched, {cid: by_id.get(cid, card) for cid, card in chosen.items()})
    if related:
        st.markdown("**Notícias relacionadas sugeridas** (a sugestão nunca entra sozinha: você decide)")
        for card, score in related:
            if st.checkbox(md_safe(f"{card.get('nome_fonte')} — {card.get('titulo')} (afinidade {score:.2f})"),
                           key=f"sug_{card.get('id_card')}") and len(chosen) < MAX_SOURCES:
                chosen[str(card.get("id_card"))] = card

    probe = [{"id": str(c.get("id_card")), "nome": c.get("nome_fonte"), "tipo_fonte": c.get("tipo_fonte"),
              "url": c.get("url_fonte") or "", "titulo": c.get("titulo", ""), "trecho": c.get("descricao", "")}
             for c in chosen.values()]
    groups = detectar_origem_comum(probe)
    independent = len(probe) - sum(len(g.fonte_ids) - 1 for g in groups)
    for group in groups:
        names = [p["nome"] for p in probe if p["id"] in group.fonte_ids]
        st.warning(f"Mesma origem ({group.motivo}): {', '.join(names)}. Contam como uma fonte.")
    if not MIN_SOURCES <= len(chosen) <= MAX_SOURCES:
        st.info(f"Selecione de {MIN_SOURCES} a {MAX_SOURCES} notícias (hoje: {len(chosen)}).")
        return
    if independent < MIN_SOURCES:
        st.info("Há menos de 2 fontes independentes: o material será gerado com uma fonte só, sem triangulação.")

    levels = st.multiselect("Níveis a gerar", LEVELS, default=LEVELS, format_func=LEVEL_LABELS.get, key="tri_levels")
    if not st.button("Gerar relatório triangulado", type="primary", disabled=not levels, key="tri_generate"):
        return

    from src.app.db import get_connection
    from src.app.level_selection import generate_and_report

    db_connection = get_connection()
    fontes, problems = [], []
    with st.spinner("Lendo o texto completo de cada fonte..."):
        for index, card in enumerate(chosen.values(), start=1):
            text, _admission, error = card_document(card, db_connection)
            if error:
                problems.append(f"{card.get('nome_fonte')}: {error}")
                continue
            fontes.append({"id": f"f{index}", "nome": card.get("nome_fonte"), "tipo_fonte": card.get("tipo_fonte"),
                           "titulo": card.get("titulo"), "data": str(card.get("data_card") or "") or None,
                           "url": card.get("url_fonte"), "conteudo": text})
    for problem in problems:
        st.warning(problem)
    if len(fontes) < MIN_SOURCES:
        st.error("Não foi possível ler o texto de pelo menos 2 fontes.")
        return
    title = f"Triangulação: {fontes[0]['titulo']}"
    summary = generate_and_report(fontes[0]["conteudo"], levels, title, {"tipo_origem": "card"}, None, db_connection,
                                  fontes=fontes)
    if summary is None:
        return
    chosen.clear()
    st.session_state["page"] = "materiais"
    st.session_state["flash"] = ("Relatório triangulado gerado." if summary.get("triangulado")
                                 else "Gerado com fonte única (sem 2 fontes independentes).")
    st.rerun()
