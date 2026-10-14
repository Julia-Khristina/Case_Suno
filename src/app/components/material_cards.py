"""Hub interactivo de materiais."""

from __future__ import annotations

import streamlit as st

from src.generation.models import AnalyticalText, Carousel, Script
from src.export.script_export import to_person_script, to_ai_prompt
from src.export.text_export import to_markdown
from src.pipeline.nodes.human_validation import apply_human_decision
from src.persistence.repositories.material_repository import MaterialRepository


def _accepts_state(session_value, default=None):
    return session_value if session_value is not None else default


def _list_documents(db_connection):
    if db_connection is None:
        return []
    with db_connection.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (d.hash) d.hash, d.titulo_origem, d.id_card, d.criado_em, e.id_execucao
            FROM documentos d
            JOIN execucoes e ON e.hash_documento = d.hash
            ORDER BY d.hash, d.criado_em DESC
            """
        )
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _list_materials(db_connection, execution_id):
    if db_connection is None or execution_id is None:
        return []
    with db_connection.cursor() as cur:
        cur.execute(
            """
            SELECT id_material, nivel, formato, estado, conteudo_gerado, conteudo_editado
            FROM materiais
            WHERE id_execucao = %s
            ORDER BY nivel, criado_em
            """,
            (execution_id,),
        )
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _format_label(fmt):
    return {
        "texto_analitico": "Relatório analítico",
        "carrossel": "Carrossel",
        "roteiro_video": "Roteiro de vídeo",
    }.get(fmt, fmt)


def _text_from_content(content):
    if not content:
        return ""
    try:
        at = AnalyticalText.model_validate(content)
        return to_markdown(at)
    except Exception:
        import json

        return json.dumps(content, ensure_ascii=False, indent=2)


def render_materials_hub(db_connection):
    st.session_state.setdefault("materiais_news_hash", None)
    st.session_state.setdefault("materiais_nivel", None)
    st.session_state.setdefault("materiais_formato", None)
    st.session_state.setdefault("materiais_material_id", None)

    news_list = _list_documents(db_connection)

    if st.session_state["materiais_news_hash"] is not None:
        st.button("Voltar às notícias", key="voltar_noticias_materiais", on_click=lambda: _reset_news())
    if st.session_state["materiais_nivel"] is not None and st.session_state["materiais_news_hash"] is not None:
        st.button("Voltar aos níveis", key="voltar_niveis", on_click=lambda: _reset_level())
    if st.session_state["materiais_formato"] is not None:
        st.button("Voltar aos formatos", key="voltar_formatos", on_click=lambda: _reset_format())

    if not news_list:
        st.caption("Nenhuma notícia com materiais gerados ainda.")
        return

    if st.session_state["materiais_news_hash"] is None:
        st.subheader("Notícias selecionadas para geração de novos materiais")
        cols = st.columns(3)
        for idx, row in enumerate(news_list):
            with cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"**{row.get('titulo_origem') or 'Notícia sem título'}**")
                    st.caption(f"Criada em: {row.get('criado_em')}")
                    if st.button("Abrir material", key=f"open_news_{row.get('hash')}", use_container_width=True):
                        st.session_state["materiais_news_hash"] = row.get("hash")
                        st.session_state["materiais_nivel"] = None
                        st.session_state["materiais_formato"] = None
                        st.session_state["materiais_material_id"] = None
                        st.rerun()
        return

    selected_hash = st.session_state["materiais_news_hash"]
    selected_row = next((r for r in news_list if str(r.get("hash")) == str(selected_hash)), None)
    if selected_row is None:
        _reset_news()
        st.rerun()
        return

    execution_id = selected_row.get("id_execucao")
    materials = _list_materials(db_connection, execution_id)
    title = selected_row.get("titulo_origem") or "Notícia sem título"

    st.subheader(f"Notícia selecionada: {title}")
    levels = ["iniciante", "intermediario", "avancado"]
    LABELS = {"iniciante": "Iniciante", "intermediario": "Intermediário", "avancado": "Avançado"}

    if st.session_state["materiais_nivel"] is None:
        st.markdown("### Níveis")
        lcols = st.columns(3)
        for idx, level in enumerate(levels):
            related = [m for m in materials if m.get("nivel") == level]
            with lcols[idx]:
                with st.container(border=True):
                    st.markdown(f"**{LABELS.get(level)}**")
                    st.caption(f"{len(related)} conteúdos gerados")
                    if st.button("Abrir", key=f"open_level_{level}", use_container_width=True):
                        st.session_state["materiais_nivel"] = level
                        st.session_state["materiais_formato"] = None
                        st.session_state["materiais_material_id"] = None
                        st.rerun()
        return

    level = st.session_state["materiais_nivel"]
    st.markdown(f"### Nível selecionado: {LABELS.get(level)}")
    formats = ["texto_analitico", "carrossel", "roteiro_video"]
    level_materials = [m for m in materials if m.get("nivel") == level]

    if st.session_state["materiais_formato"] is None:
        fcols = st.columns(3)
        for idx, fmt in enumerate(formats):
            rows = [m for m in level_materials if m.get("formato") == fmt]
            related = rows[-1] if rows else None
            with fcols[idx]:
                with st.container(border=True):
                    st.markdown(f"**{_format_label(fmt)}**")
                    st.caption(related.get("estado") if related else "não gerado")
                    if related and st.button(_format_label(fmt), key=f"open_format_{fmt}", use_container_width=True):
                        st.session_state["materiais_formato"] = fmt
                        st.session_state["materiais_material_id"] = str(related.get("id_material"))
                        st.rerun()
        return

    selected_material_id = st.session_state["materiais_material_id"]
    selected_format = st.session_state["materiais_formato"]
    material_detail = None
    for m in level_materials:
        if str(m.get("id_material")) == str(selected_material_id):
            material_detail = m
            break
    if material_detail is None and level_materials:
        selected_material_id = str(level_materials[0].get("id_material"))
        material_detail = level_materials[0]

    st.subheader(f"Conteúdo selecionado: {_format_label(selected_format)}")

    content = material_detail.get("conteudo_editado") or material_detail.get("conteudo_gerado")
    raw_text = _text_from_content(content)
    key = f"editor_text_{selected_material_id}"
    st.session_state.setdefault(key, raw_text)

    editing = st.text_area("Texto / conteúdo editável", key=key, height=260)
    observation = st.text_input("Observação", key=f"obs_{selected_material_id}")

    expected_type = type(content)
    if selected_format == "carrossel" and isinstance(content, dict):
        carousel = Carousel.model_validate(content)
        with st.expander("Slides do carrossel", expanded=True):
            for slide in carousel.slides:
                st.markdown(f"**{slide.order}. {slide.title}** - {slide.role}")
                st.caption(slide.body)
    elif selected_format == "roteiro_video" and isinstance(content, dict):
        script = Script.model_validate(content)
        total = script.total_duration_sec
        with st.expander(f"Cenas do roteiro (até {total:.1f}s)", expanded=True):
            for scene in script.scenes:
                st.markdown(f"**Cena {scene.order}: {scene.role} ({scene.start_sec:.1f}s-{scene.end_sec:.1f}s)**")
                st.caption(f"Fala: {scene.spoken}")
                st.caption(f"Tela: {scene.screen_text}")
                if scene.visual:
                    st.caption(f"Visual: {scene.visual}")
    else:
        st.markdown(raw_text)

    state = material_detail.get("estado")
    st.caption(f"Estado atual: {state}")

    col1, col2, col3 = st.columns(3)
    aprovar = col1.button("Aprovar", type="primary", key=f"aprove_mat_{selected_material_id}")
    editar = col2.button("Editar", key=f"editar_mat_{selected_material_id}")
    rejeitar = col3.button("Rejeitar", key=f"rejeitar_mat_{selected_material_id}")

    outcome = None
    if db_connection is not None:
        try:
            if aprovar:
                outcome = apply_human_decision(db_connection, str(selected_material_id), "aprovar")
            elif editar:
                outcome = apply_human_decision(db_connection, str(selected_material_id), "editar", edited_content={"texto": editing})
            elif rejeitar:
                outcome = apply_human_decision(db_connection, str(selected_material_id), "rejeitar")
        except Exception as exc:
            st.error(str(exc))

    if outcome:
        st.toast(outcome.get("status", "decisão registrada"))
        if outcome.get("exports_enabled"):
            if isinstance(content, dict):
                try:
                    if selected_format == "texto_analitico":
                        at = AnalyticalText.model_validate(content)
                        st.download_button(
                            "Baixar texto aprovado (Markdown)",
                            data=to_markdown(at),
                            file_name=f"relatorio-{selected_material_id}.md",
                            mime="text/markdown",
                            key=f"dmd_rel_{selected_material_id}",
                        )
                    elif selected_format == "carrossel":
                        carousel_out = Carousel.model_validate(content)
                        import json

                        st.download_button(
                            "Baixar carrossel (JSON)",
                            data=json.dumps(carousel_out.model_dump(), ensure_ascii=False, indent=2),
                            file_name=f"carrossel-{selected_material_id}.json",
                            mime="application/json",
                            key=f"dc_json_{selected_material_id}",
                        )
                    elif selected_format == "roteiro_video":
                        script_out = Script.model_validate(content)
                        st.download_button(
                            "Baixar roteiro (texto)",
                            data=to_person_script(script_out),
                            file_name=f"roteiro-{selected_material_id}.txt",
                            mime="text/plain",
                            key=f"dr_txt_{selected_material_id}",
                        )
                        st.download_button(
                            "Baixar roteiro (prompt IA)",
                            data=to_ai_prompt(script_out),
                            file_name=f"roteiro-{selected_material_id}-ai.txt",
                            mime="text/plain",
                            key=f"dr_ai_{selected_material_id}",
                        )
                except Exception as exc:
                    st.error(str(exc))

    if observation:
        st.caption(f"Observação: {observation}")


def _reset_news():
    st.session_state["materiais_news_hash"] = None
    st.session_state["materiais_nivel"] = None
    st.session_state["materiais_formato"] = None
    st.session_state["materiais_material_id"] = None


def _reset_level():
    st.session_state["materiais_nivel"] = None
    st.session_state["materiais_formato"] = None
    st.session_state["materiais_material_id"] = None


def _reset_format():
    st.session_state["materiais_formato"] = None
    st.session_state["materiais_material_id"] = None
