"""Blocos do hub de materiais: gráficos, matriz de triangulação, selos de fato/projeção e painel de qualidade."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.app.text import md_safe

STATUS_LABEL = {"convergencia": "Convergência", "divergencia_numerica": "Divergência numérica",
                "divergencia_qualitativa": "Divergência qualitativa", "sem_contraponto": "Sem contraponto",
                "nao_comparavel": "Não comparável"}
TYPE_LABEL = {"fato": "fato", "projecao": "projeção", "evento_futuro": "evento futuro"}
POSITION = {"apoiar": "apoia", "contestar": "contesta", "neutra": "neutra"}


def annotated_markdown(content: dict, base_markdown: str) -> str:
    """Acrescenta o selo `projeção` ou `evento futuro` depois das frases que vêm de afirmações desse tipo."""
    text = base_markdown
    for item in content.get("rastreio") or []:
        label = TYPE_LABEL.get(item.get("tipo") or "")
        if label and label != "fato" and item.get("texto") and item["texto"] in text:
            text = text.replace(item["texto"], f"{item['texto']} `{label}`", 1)
    return text


def render_reader_blocks(content: dict) -> None:
    triangulacao = content.get("triangulacao")
    if triangulacao:
        _render_matrix(triangulacao)
    charts = content.get("graficos") or []
    if charts:
        st.markdown("#### Gráficos")
        for chart in charts:
            path = Path(chart.get("arquivo", ""))
            if path.exists():
                st.image(str(path), caption=md_safe(chart.get("titulo", "")))
            st.caption(md_safe(chart.get("texto_alternativo", "")))
    trace = [t for t in content.get("rastreio") or [] if t.get("afirmacao_id")]
    if content.get("rastreio"):
        total = len(content["rastreio"])
        with st.expander(f"Rastreio por frase ({len(trace)} de {total} frases ligadas a uma afirmação da fonte)"):
            rows = [{"Frase": t["texto"], "Tipo": TYPE_LABEL.get(t.get("tipo") or "", "—"), "Fonte": t.get("fonte") or "—",
                     "Trecho de origem": t.get("trecho") or "—"} for t in content["rastreio"]]
            st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_matrix(triangulacao: dict) -> None:
    fontes = triangulacao.get("fontes") or []
    st.markdown(md_safe(f"#### Matriz de triangulação — {triangulacao.get('assunto') or ''}"))
    groups = triangulacao.get("grupos_origem") or []
    st.caption(f"{len(fontes)} fontes, {triangulacao.get('independentes')} independentes."
               + "".join(f" Mesma origem: {', '.join(g['fonte_ids'])} ({g['motivo']})." for g in groups))
    rows = []
    for row in triangulacao.get("matriz") or []:
        cells = {c["fonte_id"]: c for c in row.get("celulas", [])}
        line = {"Linha": row["linha_id"], "Ponto": row["topico"], "Status": STATUS_LABEL.get(row["status"], row["status"])}
        for fonte in fontes:
            cell = cells.get(fonte["id"])
            if cell is None:
                line[fonte["nome"]] = "não trata"
            elif cell.get("dado_numerico"):
                line[fonte["nome"]] = cell.get("valor_texto")
            else:
                line[fonte["nome"]] = POSITION.get(cell.get("posicao_qualitativa") or "", "") + ": " + (cell.get("valor_texto") or "")
        line["Por quê"] = row.get("justificativa_status") or ""
        rows.append(line)
    st.dataframe(rows, use_container_width=True, hide_index=True)
    with st.expander("Trechos de cada fonte"):
        for row in triangulacao.get("matriz") or []:
            st.markdown(md_safe(f"**{row['linha_id']}. {row['topico']}**"))
            for cell in row.get("celulas", []):
                st.caption(md_safe(f"{cell['fonte_nome']}: “{cell.get('trecho_curto') or cell.get('trecho') or ''}”"))


def render_quality_panel(db_connection, material_id: str, level: str | None) -> None:
    """Métricas de cada tentativa contra a faixa do nível, notas do juiz e o que mudou entre as tentativas."""
    if db_connection is None or not material_id:
        return
    try:
        with db_connection.cursor() as cur:
            cur.execute("""SELECT t.id_tentativa, t.numero_tentativa, t.metricas, t.falhas, t.feedback_usado, t.conteudo,
                                  t.nivel_classificado, t.tokens, t.latencia, j.notas, j.justificativas, j.media_ponderada,
                                  j.aprovado, j.id_modelo_juiz
                           FROM tentativas t LEFT JOIN avaliacoes_juiz j ON j.id_tentativa = t.id_tentativa
                           WHERE t.id_material = %s ORDER BY t.numero_tentativa""", (material_id,))
            columns = [d[0] for d in cur.description]
            attempts = [dict(zip(columns, row)) for row in cur.fetchall()]
    except Exception as exc:  # noqa: BLE001
        db_connection.rollback()
        st.caption(f"Painel de qualidade indisponível: {exc}")
        return
    if not attempts:
        return
    from src.evaluation.diff_utils import css_diff, gerar_diff_html
    from src.evaluation.thresholds import load_thresholds

    t = load_thresholds()
    bands = {"iniciante": f"Flesch ≥ {t['flesch_iniciante_min']}, densidade ≤ {t['densidade_iniciante_max']}",
             "intermediario": f"Flesch {t['flesch_intermediario_min']}–{t['flesch_intermediario_max']}, densidade "
                              f"{t['densidade_intermediaria_min']}–{t['densidade_intermediaria_max']}",
             "avancado": f"Flesch ≤ {t['flesch_avancado_max']}, densidade ≥ {t['densidade_avancado_min']}"}
    with st.expander(f"Qualidade e tentativas ({len(attempts)})"):
        st.caption(f"Faixa do nível: {bands.get(level or '', '—')}")
        st.dataframe([{
            "Tentativa": a["numero_tentativa"], "Palavras": (a["metricas"] or {}).get("palavras"),
            "Intervalo": str((a["metricas"] or {}).get("intervalo_palavras")), "Flesch": (a["metricas"] or {}).get("flesch"),
            "Densidade": (a["metricas"] or {}).get("densidade_termos"), "Nível classificado": a["nivel_classificado"],
            "Falhas": ", ".join(f.get("code", "") for f in a["falhas"] or []) or "—",
            "Juiz (média)": a["media_ponderada"], "Tokens": a["tokens"],
        } for a in attempts], use_container_width=True, hide_index=True)
        last_judged = next((a for a in reversed(attempts) if a.get("notas")), None)
        if last_judged:
            st.markdown(f"**Notas do juiz** ({last_judged['id_modelo_juiz']}, tentativa {last_judged['numero_tentativa']})")
            st.bar_chart(last_judged["notas"], horizontal=True)
            for criterion in last_judged.get("justificativas") or []:
                st.caption(md_safe(f"{criterion.get('nome')}: {criterion.get('nota')} — {criterion.get('justificativa')} "
                                   f"(evidência: {'; '.join(criterion.get('evidencias') or [])})"))
        for previous, current in zip(attempts, attempts[1:]):
            st.markdown(f"**Da tentativa {previous['numero_tentativa']} para a {current['numero_tentativa']}**")
            if current.get("feedback_usado"):
                st.code(current["feedback_usado"], language=None)
            before = _plain(previous.get("conteudo"))
            after = _plain(current.get("conteudo"))
            if before or after:
                st.html(f"<style>{css_diff()}</style><div style='font-size:0.9rem'>{gerar_diff_html(before, after)}</div>")


def _plain(content) -> str:
    if not isinstance(content, dict):
        return ""
    parts = [content.get("title", "")]
    for name in ("introduction", "development", "analysis", "conclusion"):
        section = content.get(name)
        if isinstance(section, dict):
            parts.append(section.get("content", ""))
    for slide in content.get("slides", []) or []:
        parts.append(f"{slide.get('title', '')}. {slide.get('body', '')}")
    for scene in content.get("scenes", []) or []:
        parts.append(scene.get("fala_escrita", ""))
    return "\n".join(p for p in parts if p)


# ------------------------------------------------------------------------------------------ carrossel

SLIDES_DIR = Path("data/exports/carrossel")


def _slides_key(material_id: str, content: dict) -> str:
    import hashlib
    import json

    digest = hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()[:10]
    return f"{material_id}_{digest}"


def rendered_slides(material_id: str, content: dict, level: str) -> tuple[list[Path], dict]:
    """Renderiza (ou reaproveita) os PNGs do carrossel; a chave inclui o conteúdo, então edição gera nova imagem."""
    from src.rendering.playwright_renderer import PlaywrightCarouselRenderer

    key = _slides_key(material_id, content)
    folder = SLIDES_DIR / key
    paths = sorted(folder.glob("slide_*.png"))
    state_key = f"slides_overflow_{key}"
    if len(paths) == len(content.get("slides") or []) and paths:
        return paths, st.session_state.get(state_key, {})
    result = PlaywrightCarouselRenderer(SLIDES_DIR).render(content, level, basename=key)
    st.session_state[state_key] = result.overflow
    return result.paths, result.overflow


def render_carousel_preview(material_id: str, content: dict, level: str) -> None:
    """Pré-visualização com os mesmos modelos da exportação (seção 4.6), antes da validação humana."""
    if not st.button("Pré-visualizar slides (PNG 1080×1350)", key=f"preview_slides_{material_id}"):
        key = _slides_key(material_id, content)
        if not sorted((SLIDES_DIR / key).glob("slide_*.png")):
            return
    try:
        with st.spinner("Renderizando os slides..."):
            paths, overflow = rendered_slides(material_id, content, level)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Não foi possível renderizar os slides: {exc}")
        return
    for order, fields in overflow.items():
        st.warning(f"Slide {order}: o texto não coube ({', '.join(fields)}). Edite o slide antes de aprovar.")
    columns = st.columns(3)
    for index, path in enumerate(paths):
        columns[index % 3].image(str(path), caption=f"Slide {index + 1}", use_container_width=True)


def carousel_zip(material_id: str, content: dict, level: str) -> bytes:
    from src.rendering.playwright_renderer import zip_slides

    paths, _overflow = rendered_slides(material_id, content, level)
    return zip_slides(paths)
