"""Hub interativo de materiais: notícia → nível → formato → conteúdo, com revisão humana."""

from __future__ import annotations

import streamlit as st

from src.generation.models import AnalyticalText, Carousel, Script
from src.export.script_export import to_person_script, to_ai_prompt
from src.export.text_export import to_markdown
from src.app.text import md_safe
from src.app.theme import empty_state, esc, humanize, option_card_html, section_title, status_chip, stepper, svg
from src.pipeline.nodes.human_validation import apply_human_decision
from src.persistence.repositories.material_repository import MaterialRepository

LEVELS = ["iniciante", "intermediario", "avancado"]
LEVEL_LABELS = {"iniciante": "Iniciante", "intermediario": "Intermediário", "avancado": "Avançado"}
LEVEL_ICONS = {"iniciante": "sprout", "intermediario": "chart", "avancado": "target"}
FORMATS = ["texto_analitico", "carrossel", "roteiro_video"]
FORMAT_ICONS = {"texto_analitico": "book", "carrossel": "slides", "roteiro_video": "video"}
FORMAT_HINTS = {
    "texto_analitico": "Introdução, desenvolvimento, análise e conclusão, com fonte e termos explicados.",
    "carrossel": "Slides 1080×1350 no modelo Suno Asset, com legenda para o Instagram.",
    "roteiro_video": "Cenas com fala escrita, fala falada, texto na tela e tempos.",
}
STEPS = ["Notícia", "Nível", "Formato", "Conteúdo"]


def _fmt_dt(value) -> str:
    """Data e hora no fuso de São Paulo, ex.: 17/10/2026 14:45."""
    from src.app.theme import TZ, parse_dt

    dt = parse_dt(value)
    return dt.astimezone(TZ).strftime("%d/%m/%Y %H:%M") if dt else "—"


def _level_taglines() -> dict[str, str]:
    """Rótulos de nível usados nos slides (config/tokens_visuais.yaml), para a interface falar a mesma língua."""
    try:
        from src.rendering.playwright_renderer import load_tokens

        return dict(load_tokens().get("rotulo_nivel") or {})
    except Exception:  # noqa: BLE001
        return {}


def _accepts_state(session_value, default=None):
    return session_value if session_value is not None else default


def _list_documents(db_connection):
    """Uma linha por documento com a execução mais recente e quantos materiais ela gerou (mais recentes primeiro)."""
    if db_connection is None:
        return []
    with db_connection.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (d.hash) d.hash, d.titulo_origem, d.id_card, d.criado_em, e.id_execucao,
                   (SELECT COUNT(*) FROM materiais m WHERE m.id_execucao = e.id_execucao) AS n_materiais
            FROM documentos d
            JOIN execucoes e ON e.hash_documento = d.hash
            -- execução que quebrou antes de gerar (ex.: dependência faltando) não esconde a anterior nem lista vazio
            WHERE EXISTS (SELECT 1 FROM materiais m WHERE m.id_execucao = e.id_execucao)
            ORDER BY d.hash, e.criado_em DESC
            """
        )
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    rows.sort(key=lambda r: str(r.get("criado_em") or ""), reverse=True)
    return rows


def _list_materials(db_connection, execution_id):
    if db_connection is None or execution_id is None:
        return []
    with db_connection.cursor() as cur:
        cur.execute(
            """
            SELECT id_material, nivel, formato, estado, conteudo_gerado, conteudo_editado, status_avaliacao, aviso,
                   nivel_classificado
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


def _meta(icon: str, text: str) -> str:
    return f'<span class="m">{svg(icon, 15)}{esc(text)}</span>'


def _panel_title(icon: str, text: str) -> None:
    st.markdown(f'<div class="panel-title">{svg(icon, 18)}{esc(text)}</div>', unsafe_allow_html=True)


def _back_buttons() -> None:
    """Botões de voltar de cada etapa (aparecem conforme a profundidade da navegação)."""
    buttons = []
    if st.session_state["materiais_news_hash"] is not None:
        buttons.append(("‹ Voltar às notícias", "back_noticias", _reset_news))
    if st.session_state["materiais_nivel"] is not None and st.session_state["materiais_news_hash"] is not None:
        buttons.append(("‹ Voltar aos níveis", "back_niveis", _reset_level))
    if st.session_state["materiais_formato"] is not None:
        buttons.append(("‹ Voltar aos formatos", "back_formatos", _reset_format))
    if not buttons:
        return
    cols = st.columns(len(buttons) + 3)
    for col, (label, key, callback) in zip(cols, buttons):
        col.button(label, key=key, on_click=callback)


def _render_news_step(news_list) -> None:
    section_title("Notícias selecionadas para geração de novos materiais")
    st.caption(f"{len(news_list)} notícia(s) com materiais gerados. Abra uma para escolher o nível e o formato.")
    cols = st.columns(3, gap="medium")
    for idx, row in enumerate(news_list):
        n = row.get("n_materiais")
        meta = _meta("calendar", f"Criada em: {_fmt_dt(row.get('criado_em'))}")
        if n is not None:
            meta += _meta("layers", f"{n} material(is)")
        with cols[idx % 3]:
            with st.container(key=f"opt_news_{row.get('hash')}"):
                st.markdown(option_card_html("newspaper", row.get("titulo_origem") or "Notícia sem título", meta=meta),
                            unsafe_allow_html=True)
                if st.button("Abrir material", key=f"open_news_{row.get('hash')}", use_container_width=True,
                             icon=":material/arrow_forward:"):
                    st.session_state["materiais_news_hash"] = row.get("hash")
                    st.session_state["materiais_nivel"] = None
                    st.session_state["materiais_formato"] = None
                    st.session_state["materiais_material_id"] = None
                    st.rerun()


def _render_level_step(materials) -> None:
    section_title("Níveis")
    taglines = _level_taglines()
    lcols = st.columns(3, gap="medium")
    for idx, level in enumerate(LEVELS):
        related = [m for m in materials if m.get("nivel") == level]
        approved = sum(1 for m in related if m.get("estado") == "aprovado")
        meta = _meta("layers", f"{len(related)} conteúdos gerados") + _meta("check", f"{approved} aprovado(s)")
        with lcols[idx]:
            with st.container(key=f"opt_level_{level}"):
                st.markdown(option_card_html(LEVEL_ICONS[level], LEVEL_LABELS[level], taglines.get(level, ""), meta),
                            unsafe_allow_html=True)
                if st.button("Abrir", key=f"open_level_{level}", use_container_width=True, disabled=not related,
                             icon=":material/arrow_forward:"):
                    st.session_state["materiais_nivel"] = level
                    st.session_state["materiais_formato"] = None
                    st.session_state["materiais_material_id"] = None
                    st.rerun()


def _render_format_step(level_materials, level) -> None:
    section_title(f"Nível selecionado: {LEVEL_LABELS.get(level)}")
    fcols = st.columns(3, gap="medium")
    for idx, fmt in enumerate(FORMATS):
        rows = [m for m in level_materials if m.get("formato") == fmt]
        related = rows[-1] if rows else None
        badge = status_chip(related.get("estado")) if related else status_chip(None, "Não gerado")
        meta = _meta("check", f"Avaliação: {humanize(related.get('status_avaliacao'))}") if related else ""
        with fcols[idx]:
            with st.container(key=f"opt_format_{fmt}"):
                st.markdown(option_card_html(FORMAT_ICONS[fmt], _format_label(fmt), FORMAT_HINTS[fmt], meta, badge),
                            unsafe_allow_html=True)
                if st.button(_format_label(fmt), key=f"open_format_{fmt}", use_container_width=True,
                             disabled=related is None, icon=":material/arrow_forward:"):
                    st.session_state["materiais_formato"] = fmt
                    st.session_state["materiais_material_id"] = str(related.get("id_material"))
                    st.rerun()


def _render_carousel(content, level, material_id) -> None:
    carousel = Carousel.model_validate(content)
    with st.expander("Slides do carrossel", expanded=True):
        rows = "".join(
            f'<div class="slide-row"><span class="slide-n">{slide.order}</span><span class="slide-t">{esc(slide.title)}</span>'
            f'<span class="slide-r">{esc(humanize(slide.role))}</span><div class="slide-b">{esc(slide.body)}</div></div>'
            for slide in carousel.slides
        )
        st.markdown(rows, unsafe_allow_html=True)
    if carousel.legenda is not None:
        with st.expander("Legenda do Instagram", expanded=True):
            st.text(carousel.legenda.texto_final or "")
    from src.app.components.material_extras import render_carousel_preview

    render_carousel_preview(str(material_id), content, level)


def _render_script(content) -> None:
    script = Script.model_validate(content)
    total = script.total_duration_sec
    with st.expander(f"Cenas do roteiro (até {total:.1f}s)", expanded=True):
        for scene in script.scenes:
            parts = [
                f'<div class="slide-row"><span class="slide-n">{scene.order}</span>'
                f'<span class="slide-t">Cena {scene.order}: {esc(humanize(scene.role))}</span>'
                f'<span class="slide-r">{scene.start_sec:.1f}s–{scene.end_sec:.1f}s</span>',
                f'<div class="slide-b"><b>Fala escrita:</b> {esc(scene.fala_escrita)}</div>',
                f'<div class="slide-b"><b>Fala falada:</b> {esc(scene.fala_falada)}</div>',
                f'<div class="slide-b"><b>Tela:</b> {esc(scene.texto_na_tela)}</div>',
            ]
            if scene.visual:
                parts.append(f'<div class="slide-b"><b>Visual:</b> {esc(scene.visual)}</div>')
            if scene.enquadramento:
                parts.append(f'<div class="slide-b"><b>Enquadramento:</b> {esc(humanize(scene.enquadramento))}</div>')
            st.markdown("".join(parts) + "</div>", unsafe_allow_html=True)


def render_materials_hub(db_connection):
    st.session_state.setdefault("materiais_news_hash", None)
    st.session_state.setdefault("materiais_nivel", None)
    st.session_state.setdefault("materiais_formato", None)
    st.session_state.setdefault("materiais_material_id", None)

    news_list = _list_documents(db_connection)

    depth = sum(st.session_state[k] is not None for k in ("materiais_news_hash", "materiais_nivel", "materiais_formato"))
    stepper(STEPS, depth)
    _back_buttons()

    if not news_list:
        empty_state("Nenhuma notícia com materiais gerados ainda.")
        return

    if st.session_state["materiais_news_hash"] is None:
        _render_news_step(news_list)
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

    if st.session_state["materiais_formato"] is None:
        st.markdown(f'<div class="detail-head"><div class="detail-kicker">Notícia selecionada</div>'
                    f'<div class="detail-title">{esc(title)}</div>'
                    f'<div class="chips">{status_chip("info", f"{len(materials)} materiais nesta execução")}</div></div>',
                    unsafe_allow_html=True)

    if st.session_state["materiais_nivel"] is None:
        _render_level_step(materials)
        return

    level = st.session_state["materiais_nivel"]
    level_materials = [m for m in materials if m.get("nivel") == level]

    if st.session_state["materiais_formato"] is None:
        _render_format_step(level_materials, level)
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
    if material_detail is None:
        empty_state("Material não encontrado para este nível.")
        return

    content = material_detail.get("conteudo_editado") or material_detail.get("conteudo_gerado")
    raw_text = _text_from_content(content)
    state = material_detail.get("estado")

    chips = (status_chip(state, f"Estado: {humanize(state)}")
             + status_chip(material_detail.get("status_avaliacao"),
                           f"Avaliação: {humanize(material_detail.get('status_avaliacao'))}")
             + status_chip(None, f"Nível classificado: {humanize(material_detail.get('nivel_classificado'))}"))
    st.markdown(f'<div class="detail-head"><div class="detail-kicker">Conteúdo selecionado: {esc(_format_label(selected_format))}'
                f' · {esc(LEVEL_LABELS.get(level, level))}</div><div class="detail-title">{esc(title)}</div>'
                f'<div class="chips">{chips}</div></div>', unsafe_allow_html=True)
    if material_detail.get("aviso"):
        st.warning(md_safe(material_detail["aviso"]))

    with st.container(key=f"panel_conteudo_{selected_material_id}"):
        _panel_title(FORMAT_ICONS.get(selected_format, "file"), "Pré-visualização")
        if selected_format == "carrossel" and isinstance(content, dict):
            _render_carousel(content, level, selected_material_id)
        elif selected_format == "roteiro_video" and isinstance(content, dict):
            _render_script(content)
        else:
            from src.app.components.material_extras import annotated_markdown, render_reader_blocks

            st.markdown(md_safe(annotated_markdown(content or {}, raw_text)))
            if isinstance(content, dict):
                render_reader_blocks(content)

    with st.container(key=f"panel_revisao_{selected_material_id}"):
        _render_review(db_connection, material_detail, str(selected_material_id), raw_text, content,
                       selected_format, level)

    previous = [m for m in level_materials if m.get("formato") == selected_format
                and str(m.get("id_material")) != str(selected_material_id)]
    history = _decisions(db_connection, [str(selected_material_id), *[str(m.get("id_material")) for m in previous]])
    if history:
        with st.container(key=f"panel_historico_{selected_material_id}"):
            _panel_title("clock", "Histórico de decisões")
            _render_history(history, str(selected_material_id))

    with st.container(key=f"panel_qualidade_{selected_material_id}"):
        _panel_title("chart", "Qualidade")
        from src.app.components.material_extras import render_quality_panel

        render_quality_panel(db_connection, str(selected_material_id), level)


DECISION_LABELS = {"aprovar": "Aprovado", "editar": "Editado", "rejeitar": "Rejeitado", "reabrir": "Reaberto",
                   "regenerar": "Gerado de novo"}


def _decisions(db_connection, material_ids: list[str]) -> list[dict]:
    """Decisões humanas (com observação) deste material e das versões anteriores do mesmo nível e formato."""
    if db_connection is None or not material_ids:
        return []
    try:
        with db_connection.cursor() as cur:
            cur.execute("SELECT id_material::text, decisao, observacao, criado_em FROM decisoes_humanas "
                        "WHERE id_material::text = ANY(%s) ORDER BY criado_em DESC", (material_ids,))
            return [dict(zip(["id_material", "decisao", "observacao", "criado_em"], row)) for row in cur.fetchall()]
    except Exception:  # noqa: BLE001
        db_connection.rollback()
        return []


def _render_history(history: list[dict], current_id: str) -> None:
    rows = []
    for item in history:
        version = "esta versão" if item["id_material"] == current_id else "versão anterior"
        note = f'<div class="slide-b">{esc(item["observacao"])}</div>' if item.get("observacao") else ""
        rows.append(f'<div class="slide-row"><span class="slide-t">{esc(DECISION_LABELS.get(item["decisao"], item["decisao"]))}'
                    f'</span><span class="slide-r">{esc(_fmt_dt(item["criado_em"]))} · {version}</span>{note}</div>')
    st.markdown("".join(rows), unsafe_allow_html=True)


def _decide(db_connection, material_id: str, decision: str, flash: str, **kwargs) -> None:
    """Aplica a decisão, mostra o resultado e recarrega a tela para refletir o novo estado."""
    if db_connection is None:
        st.error("Banco indisponível: a decisão não foi registrada.")
        return
    try:
        outcome = apply_human_decision(db_connection, material_id, decision, **kwargs)
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))
        return
    if outcome.get("status") == "bloqueado_material_rejeitado":
        st.warning("Material rejeitado: reabra antes de aprovar ou editar.")
        return
    if outcome.get("status") == "bloqueado_por_termos_pendentes":
        st.warning("Aprovação bloqueada: há termos pendentes no glossário.")
        return
    st.session_state["flash"] = flash
    st.rerun()


def _render_review(db_connection, material: dict, material_id: str, raw_text: str, content, fmt: str, level: str) -> None:
    from src.pipeline.nodes.human_validation import REJECTION_CATEGORIES, rejection_note

    state = material.get("estado")
    rejected = state == "rejeitado"
    _panel_title("check", "Revisão humana")
    if rejected:
        st.caption("Material rejeitado: é um estado final. Reabra para revisar de novo ou gere uma nova versão a partir "
                   "do motivo.")
    else:
        st.caption("Aprovar libera as exportações. Editar salva o texto alterado e reavalia pelas métricas. "
                   "Rejeitar pede o motivo. Toda observação fica gravada junto da decisão.")
    key = f"editor_text_{material_id}"
    st.session_state.setdefault(key, raw_text)
    editing = st.text_area("Texto / conteúdo editável", key=key, height=260, disabled=rejected)
    observation = st.text_input(
        "Observação", key=f"obs_{material_id}", disabled=rejected,
        placeholder="Ex.: corrigi o valor do IPCA no parágrafo 2",
        help="Obrigatória para Editar (descreva o que mudou). Opcional para Aprovar. Ao rejeitar, vira o motivo.")
    changed = editing.strip() != (raw_text or "").strip()
    has_note = bool(observation.strip())

    rejecting_key = f"rejecting_{material_id}"
    col1, col2, col3, col4, _spacer = st.columns([1, 1, 1, 1.2, 1.6])
    if col1.button("Aprovar", type="primary", key=f"aprove_mat_{material_id}", icon=":material/check:",
                   use_container_width=True, disabled=rejected):
        _decide(db_connection, material_id, "aprovar", "Material aprovado: exportações liberadas.", note=observation)
    if col2.button("Editar", key=f"editar_mat_{material_id}", icon=":material/edit:", use_container_width=True,
                   disabled=rejected or not (changed and has_note)):
        _decide(db_connection, material_id, "editar", "Edição salva e reavaliada.", edited_content=editing,
                note=observation)
    if not rejected:
        missing = [text for ok, text in ((changed, "altere o texto"), (has_note, "descreva a mudança na observação"))
                   if not ok]
        if missing:
            st.caption("Para editar: " + " e ".join(missing) + ".")
    if rejected:
        if col3.button("Reabrir", key=f"reabrir_mat_{material_id}", icon=":material/undo:", use_container_width=True):
            _decide(db_connection, material_id, "reabrir", "Material reaberto para revisão.")
        if col4.button("Gerar nova versão", key=f"regen_mat_{material_id}", icon=":material/refresh:",
                       use_container_width=True, help="Gera de novo só este nível e formato, levando o motivo da "
                                                       "rejeição. Usa o modelo de linguagem (até 3 tentativas + juiz)."):
            _regenerate(db_connection, material_id)
    elif col3.button("Rejeitar", key=f"rejeitar_mat_{material_id}", icon=":material/close:", use_container_width=True):
        st.session_state[rejecting_key] = True
        if has_note and not st.session_state.get(f"rej_txt_{material_id}"):
            st.session_state[f"rej_txt_{material_id}"] = observation.strip()  # a observação já escrita vira o motivo

    if st.session_state.get(rejecting_key) and not rejected:
        with st.container(key=f"panel_rejeicao_{material_id}"):
            st.markdown('<div class="panel-title">Por que rejeitar?</div>', unsafe_allow_html=True)
            categories = st.multiselect("Categorias (opcional)", REJECTION_CATEGORIES, key=f"rej_cat_{material_id}",
                                        placeholder="Escolha uma ou mais categorias")
            reason = st.text_area("Motivo (obrigatório)", key=f"rej_txt_{material_id}", height=90,
                                  placeholder="Ex.: o slide 3 diz que a Selic subiu, mas a fonte diz que foi mantida.")
            note = rejection_note(categories, reason)
            r1, r2, r3, _s = st.columns([1.2, 1.5, 0.9, 2])
            confirm = r1.button("Confirmar rejeição", key=f"rej_ok_{material_id}", type="primary",
                                disabled=not reason.strip(), use_container_width=True)
            confirm_regen = r2.button("Rejeitar e gerar de novo", key=f"rej_regen_{material_id}",
                                      disabled=not reason.strip(), use_container_width=True,
                                      help="Usa o modelo de linguagem para gerar uma nova versão deste nível e formato.")
            if r3.button("Cancelar", key=f"rej_cancel_{material_id}", use_container_width=True):
                st.session_state.pop(rejecting_key, None)
                st.rerun()
            if not reason.strip():
                st.caption("Escreva o motivo para habilitar a rejeição: ele fica gravado e orienta uma nova versão.")
            if confirm or confirm_regen:
                st.session_state.pop(rejecting_key, None)
                try:
                    apply_human_decision(db_connection, material_id, "rejeitar", note=note)
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))
                    return
                if confirm_regen:
                    _regenerate(db_connection, material_id)
                st.session_state["flash"] = "Material rejeitado; motivo registrado."
                st.rerun()

    if state == "aprovado":
        st.markdown('<div class="panel-title">Exportações</div>', unsafe_allow_html=True)
        _render_downloads(content, fmt, material_id, level)


def _regenerate(db_connection, material_id: str) -> None:
    from src.pipeline.nodes.human_validation import RegenerationUnavailable, regenerate_rejected

    with st.spinner("Gerando nova versão a partir do motivo da rejeição (métricas, reescritas e juiz)..."):
        try:
            result = regenerate_rejected(db_connection, material_id)
        except RegenerationUnavailable as exc:
            st.warning(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            st.error(f"A nova versão falhou: {type(exc).__name__}: {exc}")
            return
    for error in result["erros"]:
        st.error(error)
    if not result["id_material_novo"]:
        return
    st.session_state["materiais_material_id"] = result["id_material_novo"]
    st.session_state["flash"] = "Nova versão gerada a partir do motivo da rejeição: aguardando revisão."
    st.rerun()


def _render_downloads(content, selected_format, selected_material_id, level) -> None:
    if not isinstance(content, dict):
        return
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
            from src.export.text_export import to_html

            st.download_button(
                "Baixar texto aprovado (HTML com gráficos)",
                data=to_html(at, standalone=True),
                file_name=f"relatorio-{selected_material_id}.html",
                mime="text/html",
                key=f"dhtml_rel_{selected_material_id}",
            )
        elif selected_format == "carrossel":
            carousel_out = Carousel.model_validate(content)
            import json

            from src.app.components.material_extras import carousel_zip

            st.download_button(
                "Baixar slides (PNG, ZIP)",
                data=carousel_zip(str(selected_material_id), content, level),
                file_name=f"carrossel-{selected_material_id}.zip",
                mime="application/zip",
                key=f"dc_zip_{selected_material_id}",
            )
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
