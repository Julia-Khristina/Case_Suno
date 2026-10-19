"""Entrada manual e seleção de níveis (diálogo aberto pelo botão vermelho do mockup).

A geração sempre passa pelo pipeline LangGraph real (extração → geração → avaliação → juiz → revisão).
Não existe mais modo "demonstração" por template: se o pipeline falhar, a causa real aparece na tela (seção 4.2).
"""
from __future__ import annotations

import tempfile
from datetime import date

import streamlit as st

from src.admission.models import OriginMetadata
from src.admission.service import admit_pdf, admit_text, admit_url
from src.app.components.news_cards import LEVELS, LEVEL_LABELS
from src.app.theme import page_header


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat((value or "").strip()) if value else None
    except ValueError:
        return None


def _origin_dict(origin: OriginMetadata, origin_type: str) -> dict:
    data = origin.model_dump(mode="json")
    data["tipo_origem"] = origin_type
    return {k: v for k, v in data.items() if v}


def run_pipeline_for_document(source_text: str, levels: list[str], title: str, origin: dict | None = None,
                              admission: dict | None = None, db_connection=None, fontes: list[dict] | None = None) -> dict:
    """Executa o pipeline para um documento e devolve o resumo da execução.

    Com banco disponível, execução, materiais, tentativas, avaliações do juiz e rastreabilidade são gravados
    no PostgreSQL; sem banco, ficam só no estado devolvido (e a interface avisa).
    """
    from src.pipeline.deps import PipelineDeps
    from src.pipeline.graph import run_pipeline
    from src.pipeline.persistence import InMemoryPersistence, PostgresPersistence

    origin = dict(origin or {})
    origin.setdefault("titulo", title)
    persistence = PostgresPersistence(db_connection) if db_connection is not None else InMemoryPersistence()
    deps = PipelineDeps(persistence=persistence)
    final = run_pipeline(source_text, levels, origin=origin, deps=deps, admission=admission, fontes=fontes)
    outputs = final.get("generated_outputs") or {}
    return {
        "id_execucao": final.get("execution_id"),
        "hash_documento": (final.get("document") or {}).get("hash"),
        "titulo": title,
        "niveis": levels,
        "status": final.get("status"),
        "materiais": [{"nivel": o.get("nivel"), "formato": o.get("formato"), "status": o.get("status"),
                       "aviso": o.get("aviso"), "id_material": o.get("material_id"), "conteudo_gerado": o.get("conteudo")}
                      for o in outputs.values()],
        "erros": final.get("errors") or [],
        "avisos": final.get("warnings") or [],
        "tokens": final.get("token_count", 0),
        "persistido": db_connection is not None,
        "triangulado": bool(final.get("triangulacao")),
    }


def generate_and_report(text: str, levels: list[str], title: str, origin: dict, admission: dict | None,
                        db_connection=None, fontes: list[dict] | None = None) -> dict | None:
    """Roda o pipeline com spinner e mostra erros e avisos reais. Devolve o resumo ou None se falhou."""
    with st.spinner("Gerando materiais dos níveis selecionados (extração, geração, avaliação e juiz)..."):
        try:
            summary = run_pipeline_for_document(text, levels, title, origin=origin, admission=admission,
                                                db_connection=db_connection, fontes=fontes)
        except Exception as exc:  # noqa: BLE001
            st.error(f"O pipeline falhou: {type(exc).__name__}: {exc}")
            return None
    for error in summary["erros"]:
        st.error(error)
    for warning in summary["avisos"]:
        st.warning(warning)
    if not summary["materiais"]:
        st.error("Nenhum material foi gerado. Veja os erros acima.")
        return None
    if not summary["persistido"]:
        st.warning("Banco indisponível: os materiais não foram gravados e não aparecerão na tela de materiais.")
    st.session_state.setdefault("generation_queue", []).append(summary)
    return summary


def _manual_form(prefix: str, db_connection=None) -> bool:
    """Desenha o formulário e devolve True quando a geração foi concluída."""
    st.caption("Informe o texto, um link ou um PDF digital. A origem aparece no bloco de fonte de cada material.")
    content = st.text_area("Texto ou cole o conteúdo financeiro", key=f"{prefix}_content", height=150,
                           placeholder="Cole aqui o texto completo da notícia ou do relatório")
    col_a, col_b = st.columns(2, gap="medium")
    instituicao = col_a.text_input("Instituição ou veículo", key=f"{prefix}_inst", placeholder="Ex.: Banco Central")
    titulo = col_b.text_input("Título", key=f"{prefix}_titulo", placeholder="Título da notícia")
    col_c, col_d = st.columns(2, gap="medium")
    data = col_c.text_input("Data (AAAA-MM-DD)", key=f"{prefix}_data", placeholder="2026-10-17")
    url = col_d.text_input("Link, se houver", key=f"{prefix}_url", placeholder="https://")
    uploaded = st.file_uploader("PDF digital (opcional)", type=["pdf"], key=f"{prefix}_pdf")
    levels = st.multiselect("Níveis", LEVELS, default=LEVELS, format_func=LEVEL_LABELS.get, key=f"{prefix}_levels")

    if not st.button("Admitir e gerar materiais", type="primary", key=f"{prefix}_submit"):
        return False
    if not levels:
        st.warning("Selecione ao menos um nível.")
        return False
    manual_origin = OriginMetadata(instituicao=instituicao or None, titulo=titulo or None, data=_parse_date(data),
                                   url=url.strip() or None)
    try:
        if content.strip():
            result, origin_type = admit_text(content.strip(), origin=manual_origin), "texto"
        elif uploaded is not None:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
                handle.write(uploaded.getvalue())
            result, origin_type = admit_pdf(handle.name, origin=manual_origin), "pdf"
        elif url.strip():
            result, origin_type = admit_url(url.strip()), "link"
        else:
            st.error("Informe texto, URL ou PDF digital.")
            return False
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "login" in message.lower():
            st.error("Não consegui acessar a página pois exige login, mande por texto")
        else:
            st.error(f"Falha ao admitir a notícia: {message}")
        return False

    if result.status == "bloqueado":
        st.error("Notícia não admitida: " + ", ".join(result.partial_reasons or ["conteúdo parcial ou insuficiente"]))
        return False
    if result.status == "aviso":
        st.warning("Admissão com aviso: o texto pode não ser financeiro ou não estar em português. Seguindo mesmo assim.")
    origin = _origin_dict(result.origin if result.origin.has_minimum_origin else manual_origin, origin_type)
    if not (origin.get("instituicao") or origin.get("titulo") or origin.get("url")):
        st.info("Sem origem informada: o material mostrará 'texto enviado pelo usuário'.")
    summary = generate_and_report(result.text, levels, origin.get("titulo") or "Notícia manual", origin,
                                  result.model_dump(mode="json"), db_connection)
    if summary is None:
        return False
    st.session_state["manual_levels"] = levels
    return True


@st.dialog("Adicionar notícia manualmente", width="large")
def manual_entry_dialog() -> None:
    from src.app.db import get_connection

    db_connection = get_connection()
    if _manual_form("dlg_manual", db_connection):
        levels = st.session_state.get("manual_levels", [])
        st.session_state["page"] = "materiais"
        st.session_state["flash"] = "Materiais gerados: " + ", ".join(LEVEL_LABELS[n] for n in levels)
        st.rerun()


def render_add_manual_button(key: str = "add_manual") -> None:
    """Botão vermelho centralizado do rodapé da tela inicial."""
    if st.button("Adicionar notícias manualmente", key=key, type="primary"):
        manual_entry_dialog()


def render_level_selection() -> None:
    """Versão em página inteira (mantida por compatibilidade com o fluxo anterior)."""
    page_header("Entrada manual e seleção de níveis")
    with st.container(key="panel_manual"):
        from src.app.db import get_connection

        if _manual_form("page_manual", get_connection()):
            levels = st.session_state.get("manual_levels", [])
            st.session_state["page"] = "materiais"
            st.success("Materiais gerados: " + ", ".join(LEVEL_LABELS[n] for n in levels))
            st.rerun()
