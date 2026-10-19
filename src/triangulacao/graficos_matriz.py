"""Gráficos gerados por regra (nunca pelo modelo) a partir da matriz de triangulação ou dos dados de uma fonte.

Regras de integridade: cada valor plotado vem de um dado extraído com trecho de origem; rótulos usam o texto
original da fonte; eixo a partir de zero; a diferença calculada aparece só no subtítulo; os dados plotados e um
texto alternativo montado por regra acompanham cada imagem.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src.triangulacao.dossie import format_quantity, parse_quantity  # noqa: E402
from src.triangulacao.models import LinhaMatriz, StatusLinhaMatriz  # noqa: E402

RED, DARK, GREY, LIGHT, WHITE = "#c1121f", "#222222", "#8a8a8a", "#e6e6e6", "#ffffff"
STATUS_LABEL = {
    StatusLinhaMatriz.CONVERGENCIA: "Convergência",
    StatusLinhaMatriz.DIVERGENCIA_NUMERICA: "Divergência numérica",
    StatusLinhaMatriz.DIVERGENCIA_QUALITATIVA: "Divergência qualitativa",
    StatusLinhaMatriz.SEM_CONTRA_PONTO: "Sem contraponto",
    StatusLinhaMatriz.NAO_COMPARAVEL: "Não comparável",
}
POSITION_LABEL = {"apoiar": "apoia", "contestar": "contesta", "neutra": "neutra", "nao_menciona": "não menciona"}
POSITION_COLOR = {"apoiar": "#2e7d32", "contestar": RED, "neutra": GREY}


def _save(fig, folder: Path, name: str, data: list[dict], meta: dict) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    png = folder / f"{name}.png"
    fig.savefig(png, dpi=150, bbox_inches="tight", facecolor=WHITE)
    plt.close(fig)
    (folder / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"id": name, "arquivo": str(png), "hash": hashlib.sha256(png.read_bytes()).hexdigest()[:16],
            "dados": data, **meta}


def chart_values_by_source(row: LinhaMatriz, folder: Path) -> dict | None:
    """Barras: o valor que cada fonte informa para o mesmo ponto (só linhas numéricas comparáveis)."""
    if row.status not in {StatusLinhaMatriz.CONVERGENCIA, StatusLinhaMatriz.DIVERGENCIA_NUMERICA}:
        return None
    points = [(c.fonte_nome, c.dado_numerico["valor_canonico"], c.valor_texto)
              for c in row.celulas if c.dado_numerico and c.dado_numerico.get("valor_canonico") is not None]
    if len(points) < 2:
        return None
    unit = row.celulas[0].dado_numerico.get("unidade_canonica", "")
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    colors = [RED if i == 0 else (DARK if i == 1 else GREY) for i in range(len(points))]
    bars = ax.bar([p[0] for p in points], [p[1] for p in points], color=colors, width=0.55)
    for bar, (_name, _value, label) in zip(bars, points):
        ax.annotate(label, (bar.get_x() + bar.get_width() / 2, bar.get_height()), ha="center", va="bottom",
                    fontsize=10, xytext=(0, 3), textcoords="offset points")
    ax.set_ylim(bottom=0, top=max(p[1] for p in points) * 1.18)
    ax.set_yticks([])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    subtitle = STATUS_LABEL[row.status]
    if row.status == StatusLinhaMatriz.DIVERGENCIA_NUMERICA and row.diferenca_absoluta is not None:
        subtitle += f" — diferença calculada: {format_quantity(row.diferenca_absoluta, unit)}"
    ax.set_title(f"{row.topico}\n{subtitle}", fontsize=11, loc="left", color=DARK)
    plt.xticks(fontsize=9)
    data = [{"fonte": n, "valor_fonte": label, "valor_canonico": v, "unidade": unit} for n, v, label in points]
    alt = f"Gráfico de barras: {row.topico}. " + "; ".join(f"{n}: {label}" for n, _v, label in points) + f". {subtitle}."
    return _save(fig, folder, f"valores_{row.linha_id}", data,
                 {"tipo": "valores_por_fonte", "titulo": row.topico, "linha_ids": [row.linha_id], "texto_alternativo": alt})


def chart_position_map(rows: list[LinhaMatriz], sources: list[dict], folder: Path) -> dict | None:
    """Mapa ponto × fonte: o que cada fonte diz (posição ou valor) e o status de cada ponto."""
    if not rows or len(sources) < 2:
        return None
    import textwrap

    names = [s["nome"] for s in sources]
    label_width = 2.6  # coluna do ponto, em unidades de célula
    fig_height = 0.8 + 0.75 * len(rows)
    fig, ax = plt.subplots(figsize=(3.4 + 2.0 * len(names), fig_height))
    ax.set_xlim(0, len(names) + label_width)
    ax.set_ylim(0, len(rows))
    ax.axis("off")
    data = []
    for r_index, row in enumerate(rows):
        y = len(rows) - r_index - 0.5
        topic = textwrap.shorten(f"{row.linha_id}. {row.topico}", width=60, placeholder="…")
        ax.text(0.02, y + 0.12, "\n".join(textwrap.wrap(topic, 30)[:2]), va="center", fontsize=8.5, color=DARK)
        ax.text(0.02, y - 0.33, STATUS_LABEL[row.status], va="center", fontsize=7, color=RED if "Divergência" in
                STATUS_LABEL[row.status] else GREY)
        by_source = {c.fonte_id: c for c in row.celulas}
        for s_index, source in enumerate(sources, start=1):
            cell = by_source.get(source["id"])
            x = label_width + s_index - 0.5
            if cell is None:
                label, color = "não trata", LIGHT
            elif cell.dado_numerico:
                label, color = cell.valor_texto or "", DARK
            else:
                key = (cell.posicao_qualitativa.value if cell.posicao_qualitativa else "neutra")
                label, color = POSITION_LABEL.get(key, key), POSITION_COLOR.get(key, GREY)
            ax.add_patch(plt.Rectangle((x - 0.47, y - 0.45), 0.94, 0.9, color=color if color != DARK else LIGHT,
                                       alpha=0.25 if color not in {LIGHT} else 1.0, linewidth=0))
            ax.text(x, y, label[:24], ha="center", va="center", fontsize=8, color=DARK)
            data.append({"linha": row.linha_id, "fonte": source["nome"], "conteudo": label})
    for s_index, name in enumerate(names, start=1):
        ax.text(label_width + s_index - 0.5, len(rows) + 0.1, name[:22], ha="center", va="bottom", fontsize=8.5,
                color=DARK, fontweight="bold")
    alt = "Mapa de posições por fonte: " + "; ".join(f"{d['linha']} {d['fonte']}: {d['conteudo']}" for d in data)
    return _save(fig, folder, "mapa_posicoes", data,
                 {"tipo": "mapa_posicoes", "titulo": "O que cada fonte diz sobre cada ponto",
                  "linha_ids": [r.linha_id for r in rows], "texto_alternativo": alt})


def charts_for_matrix(rows: list[LinhaMatriz], sources: list[dict], folder: Path, max_charts: int) -> list[dict]:
    """Mapa de posições primeiro; depois um gráfico por linha numérica comparável (divergências antes)."""
    charts = []
    position_map = chart_position_map(rows, sources, folder)
    if position_map:
        charts.append(position_map)
    numeric = sorted(rows, key=lambda r: r.status != StatusLinhaMatriz.DIVERGENCIA_NUMERICA)
    for row in numeric:
        if len(charts) >= max_charts:
            break
        chart = chart_values_by_source(row, folder)
        if chart:
            charts.append(chart)
    return charts[:max_charts]


def indicator_families(extraction: dict, min_overlap: float = 0.5) -> list[dict]:
    """Agrupa os números da fonte por indicador (mesma unidade e radicais do nome em comum).

    Decisão de 18/10/2026: um gráfico nunca põe no mesmo eixo indicadores de natureza diferente (ex.: perdão de
    dívidas e reajuste do Bolsa Família, ambos em R$ bilhões), porque a comparação visual sugeriria uma relação
    que a fonte não faz. Só entram no mesmo gráfico valores do mesmo indicador (em períodos ou recortes diferentes).
    """
    from src.evaluation.text_utils import content_stems

    families: list[dict] = []
    for item in (extraction or {}).get("numeric_data", []):
        value, unit = parse_quantity(item.get("value", ""), item.get("unit"))
        if value is None or not unit:
            continue
        indicator = str(item.get("indicator") or "").strip()
        stems = content_stems(indicator)
        point = {"indicador": indicator, "valor": value, "rotulo": f"{item.get('value')} {item.get('unit') or ''}".strip(),
                 "dado_id": item.get("id", ""), "periodo": str(item.get("reference_period") or "").strip()}
        for family in families:
            if family["unidade"] != unit or not stems or not family["stems"]:
                continue
            overlap = len(stems & family["stems"]) / min(len(stems), len(family["stems"]))
            if overlap >= min_overlap:
                family["pontos"].append(point)
                if len(indicator) < len(family["nome"]):
                    family["nome"] = indicator
                break
        else:
            families.append({"nome": indicator, "unidade": unit, "stems": set(stems), "pontos": [point]})
    return [f for f in families if len(f["pontos"]) >= 2]


def _period_key(period: str) -> tuple:
    years = re.findall(r"(?:19|20)\d{2}", period)
    return (int(years[0]) if years else 9999, period)


def charts_for_single_source(extraction: dict, folder: Path, max_charts: int = 2) -> list[dict]:
    """Fonte única: um gráfico por indicador. Linha do tempo (barras por período) quando o mesmo indicador aparece
    em 2 ou mais períodos; senão, barras com os recortes do mesmo indicador. Sem indicador repetido, sem gráfico."""
    charts = []
    families = sorted(indicator_families(extraction), key=lambda f: -len(f["pontos"]))
    for family in families:
        if len(charts) >= max_charts:
            break
        points = family["pontos"][:8]
        unit, name = family["unidade"], family["nome"][:60]
        periods = [p["periodo"] for p in points]
        timeline = all(periods) and len(set(periods)) == len(periods)
        index = len(charts) + 1
        if timeline:
            points = sorted(points, key=lambda p: _period_key(p["periodo"]))
            fig, ax = plt.subplots(figsize=(7.5, 4.0))
            bars = ax.bar([p["periodo"][:18] for p in points], [p["valor"] for p in points], color=RED, width=0.55)
            for bar, point in zip(bars, points):
                ax.annotate(point["rotulo"], (bar.get_x() + bar.get_width() / 2, bar.get_height()), ha="center",
                            va="bottom", fontsize=9, xytext=(0, 3), textcoords="offset points")
            ax.set_ylim(bottom=0, top=max(p["valor"] for p in points) * 1.2)
            ax.set_yticks([])
            for side in ("top", "right", "left"):
                ax.spines[side].set_visible(False)
            title, kind, name_file = f"{name}: evolução por período ({unit})", "serie_temporal", f"serie_{index}"
            alt = f"Gráfico de barras por período de {name}: " + "; ".join(
                f"{p['periodo']}: {p['rotulo']}" for p in points)
        else:
            labels = [f"{p['indicador'][:38]}{' (' + p['periodo'][:12] + ')' if p['periodo'] else ''}" for p in points]
            fig, ax = plt.subplots(figsize=(7.5, 0.6 + 0.5 * len(points)))
            bars = ax.barh(labels[::-1], [p["valor"] for p in points][::-1], color=RED, height=0.5)
            for bar, point in zip(bars, points[::-1]):
                ax.annotate(point["rotulo"], (bar.get_width(), bar.get_y() + bar.get_height() / 2), va="center",
                            fontsize=9, xytext=(4, 0), textcoords="offset points")
            ax.set_xlim(left=0, right=max(p["valor"] for p in points) * 1.3)
            ax.set_xticks([])
            for side in ("top", "right", "bottom"):
                ax.spines[side].set_visible(False)
            title, kind, name_file = f"{name} ({unit})", "mesmo_indicador", f"indicador_{index}"
            alt = f"Gráfico de barras de {name}: " + "; ".join(f"{label}: {p['rotulo']}" for label, p in zip(labels, points))
        ax.set_title(title, fontsize=11, loc="left", color=DARK)
        data = [{"indicador": p["indicador"], "periodo": p["periodo"] or None, "valor_fonte": p["rotulo"],
                 "valor_canonico": p["valor"], "dado_id": p["dado_id"]} for p in points]
        charts.append(_save(fig, folder, name_file, data,
                            {"tipo": kind, "titulo": title, "linha_ids": [], "texto_alternativo": alt}))
    return charts
