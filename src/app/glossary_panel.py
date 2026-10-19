"""Painel do glossário: indicadores, busca com filtros (abre com 5 termos) e inclusão de termo pendente."""
from __future__ import annotations

import unicodedata
from pathlib import Path

import streamlit as st
import yaml

from src.app.theme import esc, humanize, kpi_card, section_title, status_chip

GLOSSARY_FILE = Path("config/glossario.yaml")
INITIAL_VISIBLE = 5
PAGE_STEP = 5
LEVEL_LABELS = {"iniciante": "Iniciante", "intermediario": "Intermediário", "avancado": "Avançado"}
STATUS_LABELS = {"aprovado": "Aprovado", "autoria_manual": "Autoria manual", "pendente": "Pendente",
                 "sem_definicao": "Sem definição"}
ALL = "Todos"


def _fold(text) -> str:
    """Minúsculas e sem acentos, para a busca achar "inflacao" e "Inflação"."""
    normalized = unicodedata.normalize("NFKD", str(text or "").lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def load_terms(path: Path = GLOSSARY_FILE) -> tuple[dict, list[dict]]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    except FileNotFoundError:
        data = {}
    terms = [t if isinstance(t, dict) else {"termo": str(t), "status": "pendente"} for t in data.get("termos") or []]
    return data, terms


def filter_terms(terms: list[dict], query: str = "", nivel: str = ALL, status: str = ALL) -> list[dict]:
    """Termos que contêm a busca no nome, nas variações ou na explicação, ordenados: nome que começa com a busca primeiro."""
    needle = _fold(query).strip()
    found = []
    for term in terms:
        if nivel != ALL and term.get("nivel") != nivel:
            continue
        if status != ALL and term.get("status") != status:
            continue
        name = _fold(term.get("termo"))
        forms = [name, *(_fold(v) for v in term.get("variacoes") or [])]
        text = " ".join([*forms, _fold(term.get("explicacao_iniciante")), _fold(term.get("explicacao_impacto"))])
        if needle and needle not in text:
            continue
        rank = 0 if needle and any(f.startswith(needle) for f in forms) else 1 if needle and needle in " ".join(forms) else 2
        found.append((rank if needle else 0, name, term))
    return [term for _rank, _name, term in sorted(found, key=lambda item: (item[0], item[1]))]


def add_pending_term(termo: str, nivel: str, path: Path = GLOSSARY_FILE) -> str | None:
    """Acrescenta uma entrada no formato do glossário (status pendente). Devolve erro ou None.

    Mantém o cabeçalho de comentários do arquivo e recusa termo que já existe como termo ou variação.
    """
    termo = termo.strip()
    if not termo:
        return "Informe o termo."
    text = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    data, terms = load_terms(path)
    existing = {_fold(f) for t in terms for f in [t.get("termo"), *(t.get("variacoes") or [])]}
    if _fold(termo) in existing:
        return f"'{termo}' já está no glossário."
    terms.append({"termo": termo, "variacoes": [], "nivel": nivel, "explicacao_iniciante": None,
                  "explicacao_impacto": None, "pronuncia": None, "fonte_definicao": None, "url_fonte": None,
                  "data_consulta": None, "trecho_original": None, "status": "sem_definicao"})
    data["termos"] = terms
    header = "".join(line for line in text.splitlines(keepends=True)[:20] if line.startswith("#"))
    path.write_text(header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    return None


def _term_card(term: dict, index: int) -> None:
    nivel = term.get("nivel")
    definition = term.get("explicacao_iniciante")
    variations = term.get("variacoes") or []
    parts = [
        '<div class="term-top">'
        f'<span class="term-name">{esc(term.get("termo"))}</span>'
        f'<span class="chip">{esc(LEVEL_LABELS.get(nivel, humanize(nivel)))}</span>'
        f'{status_chip(term.get("status"), STATUS_LABELS.get(term.get("status")))}</div>'
    ]
    if variations:
        parts.append(f'<div class="term-var">Variações: {esc(", ".join(variations))}</div>')
    if definition:
        parts.append(f'<div class="term-def">{esc(definition)}</div>')
    else:
        parts.append('<div class="term-def none">Sem definição de fonte autorizada ainda.</div>')
    if term.get("explicacao_impacto"):
        parts.append(f'<div class="term-def"><b>Impacto:</b> {esc(term["explicacao_impacto"])}</div>')
    if term.get("fonte_definicao"):
        source = esc(term["fonte_definicao"])
        if term.get("url_fonte"):
            source = f'<a href="{esc(term["url_fonte"])}" target="_blank">{source}</a>'
        consulted = f' · consultado em {esc(term["data_consulta"])}' if term.get("data_consulta") else ""
        parts.append(f'<div class="term-src">Fonte: {source}{consulted}</div>')
    with st.container(key=f"term_{index}"):
        st.markdown("".join(parts), unsafe_allow_html=True)


def render_glossary_panel():
    section_title("Painel do glossário")
    _data, terms = load_terms()

    approved = sum(1 for t in terms if t.get("status") in {"aprovado", "autoria_manual"})
    pending = sum(1 for t in terms if t.get("status") == "pendente")
    no_definition = sum(1 for t in terms if t.get("status") == "sem_definicao")
    c1, c2, c3, c4 = st.columns(4, gap="medium")
    with c1:
        kpi_card("book", "Termos cadastrados", len(terms), "no glossário versionado")
    with c2:
        kpi_card("check", "Aprovados", approved, "usados nas explicações")
    with c3:
        kpi_card("clock", "Pendentes", pending, "aguardando aprovação da autora")
    with c4:
        kpi_card("alert", "Sem definição", no_definition, "sem fonte autorizada")

    st.write("")
    s1, s2, s3 = st.columns([3, 1.2, 1.2], gap="medium")
    query = s1.text_input("Pesquisar termo", key="gloss_query", placeholder="Ex.: Selic, inflação, juros...",
                          help="Busca no termo, nas variações e na explicação; acentos e maiúsculas são ignorados.")
    nivel = s2.selectbox("Nível", [ALL, *LEVEL_LABELS], key="gloss_nivel",
                         format_func=lambda v: LEVEL_LABELS.get(v, v))
    status = s3.selectbox("Status", [ALL, *STATUS_LABELS], key="gloss_status",
                          format_func=lambda v: STATUS_LABELS.get(v, v))

    signature = (query, nivel, status)
    if st.session_state.get("gloss_signature") != signature:  # nova busca volta para os primeiros resultados
        st.session_state["gloss_signature"] = signature
        st.session_state["gloss_limit"] = INITIAL_VISIBLE
    limit = st.session_state.setdefault("gloss_limit", INITIAL_VISIBLE)

    matches = filter_terms(terms, query, nivel, status)
    visible = matches[:limit]
    st.caption(f"Termos cadastrados: {len(terms)} · mostrando {len(visible)} de {len(matches)}"
               + ("" if query or nivel != ALL or status != ALL else ". Pesquise para encontrar outros termos."))
    if not matches:
        st.markdown('<div class="empty">Nenhum termo encontrado para essa busca.</div>', unsafe_allow_html=True)
    for index, term in enumerate(visible):
        _term_card(term, index)
    if len(matches) > len(visible):
        if st.button(f"Mostrar mais {min(PAGE_STEP, len(matches) - len(visible))} termos", key="gloss_more",
                     icon=":material/expand_more:"):
            st.session_state["gloss_limit"] = limit + PAGE_STEP
            st.rerun()

    with st.container(key="panel_glossary"):
        st.markdown('<div class="panel-title">Adicionar termo</div>', unsafe_allow_html=True)
        st.caption("O termo entra sem definição; ele só é usado nas explicações depois de receber definição de "
                   "fonte autorizada e aprovação.")
        n1, n2 = st.columns([3, 1.2], gap="medium")
        new_term = n1.text_input("Novo termo", key="gloss_new_term")
        new_level = n2.selectbox("Nível do termo", list(LEVEL_LABELS), key="gloss_new_level",
                                 format_func=LEVEL_LABELS.get)
        if st.button("Adicionar termo pendente de aprovação", type="primary", key="gloss_add"):
            error = add_pending_term(new_term, new_level)
            if error:
                st.warning(error)
            else:
                st.success("Termo adicionado ao glossário configurado.")
