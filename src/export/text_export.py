"""Text export helpers (Markdown e HTML) e leitura do Markdown editado na validação humana."""
from __future__ import annotations

import base64
import html
import re

from src.generation.models import AnalyticalText

SECTION_TITLES = {"introduction": "Introdução", "development": "Desenvolvimento", "analysis": "Análise",
                  "conclusion": "Conclusão"}


def _secao_texto(secao) -> str:
    """Extrai o texto de uma seção AnalyticalSection ou retorna string direta."""
    if hasattr(secao, "content"):
        return secao.content
    return str(secao)


def _secao_titulo(secao, default: str) -> str:
    title = getattr(secao, "title", "") or ""
    return title if title and title.lower() not in SECTION_TITLES else default


STATUS_LABEL = {"convergencia": "Convergência", "divergencia_numerica": "Divergência numérica",
                "divergencia_qualitativa": "Divergência qualitativa", "sem_contraponto": "Sem contraponto",
                "nao_comparavel": "Não comparável"}
POSITION = {"apoiar": "apoia", "contestar": "contesta", "neutra": "neutra"}


def _matrix_rows(text: AnalyticalText) -> tuple[list[str], list[list[str]]]:
    tri = text.triangulacao or {}
    fontes = tri.get("fontes") or []
    header = ["Linha", "Ponto", "Status", *[f["nome"] for f in fontes]]
    rows = []
    for row in tri.get("matriz") or []:
        cells = {c["fonte_id"]: c for c in row.get("celulas", [])}
        values = []
        for fonte in fontes:
            cell = cells.get(fonte["id"])
            if cell is None:
                values.append("não trata")
            elif cell.get("dado_numerico"):
                values.append(cell.get("valor_texto") or "")
            else:
                values.append(POSITION.get(cell.get("posicao_qualitativa") or "", ""))
        rows.append([row["linha_id"], row["topico"], STATUS_LABEL.get(row["status"], row["status"]), *values])
    return header, rows


def to_markdown(text: AnalyticalText) -> str:
    parts = [f"# {text.title}", "", text.subtitle, ""]
    for name, default in SECTION_TITLES.items():
        section = getattr(text, name)
        parts += [f"## {_secao_titulo(section, default)}", "", _secao_texto(section), ""]
    if text.triangulacao:
        header, rows = _matrix_rows(text)
        parts += ["## Matriz de triangulação", "", "| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        parts += ["| " + " | ".join(r) + " |" for r in rows] + [""]
    for chart in text.graficos:
        parts += [f"![{chart.get('texto_alternativo', '')}]({chart.get('arquivo', '')})", ""]
    if text.caixa_entenda_os_termos:
        parts += ["## Entenda os termos", "", text.caixa_entenda_os_termos, ""]
    parts += ["## Fonte" if not text.triangulacao else "## Fontes", "", text.fonte_bloco, ""]
    return "\n".join(parts)


def _annotate(paragraph: str, trace: list[dict]) -> str:
    """HTML do parágrafo com selo nas frases de projeção ou evento futuro."""
    escaped = html.escape(paragraph)
    for item in trace:
        label = {"projecao": "projeção", "evento_futuro": "evento futuro"}.get(item.get("tipo") or "")
        sentence = html.escape(item.get("texto") or "")
        if label and sentence and sentence in escaped:
            source = html.escape(item.get("fonte") or "")
            escaped = escaped.replace(sentence, f'{sentence} <span class="selo" title="{source}">{label}</span>', 1)
    return escaped


def _chart_img(chart: dict) -> str:
    from pathlib import Path

    path = Path(chart.get("arquivo", ""))
    if not path.exists():
        return ""
    data = base64.b64encode(path.read_bytes()).decode()
    alt = html.escape(chart.get("texto_alternativo", ""))
    return (f'<figure><img src="data:image/png;base64,{data}" alt="{alt}" style="max-width:100%">'
            f"<figcaption>{html.escape(chart.get('titulo', ''))}</figcaption></figure>")


def to_html(text: AnalyticalText, standalone: bool = False) -> str:
    e = html.escape
    trace = text.rastreio or []
    sections = "".join(
        f"<section><h3>{e(_secao_titulo(getattr(text, n), d))}</h3>"
        + "".join(f"<p>{_annotate(p, trace)}</p>" for p in _secao_texto(getattr(text, n)).split("\n\n") if p.strip())
        + "</section>"
        for n, d in SECTION_TITLES.items())
    matrix = ""
    if text.triangulacao:
        header, rows = _matrix_rows(text)
        matrix = ("<section><h3>Matriz de triangulação</h3><table><thead><tr>"
                  + "".join(f"<th>{e(h)}</th>" for h in header) + "</tr></thead><tbody>"
                  + "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in r) + "</tr>" for r in rows)
                  + "</tbody></table></section>")
    charts = "".join(_chart_img(c) for c in text.graficos)
    box = (f"<aside><h3>Entenda os termos</h3><p>{e(text.caixa_entenda_os_termos)}</p></aside>"
           if text.caixa_entenda_os_termos else "")
    article = (f"<article>\n<h1>{e(text.title)}</h1>\n<h2>{e(text.subtitle)}</h2>\n{sections}\n{matrix}{charts}{box}"
               f"<section><h3>{'Fontes' if text.triangulacao else 'Fonte'}</h3><p>{e(text.fonte_bloco)}</p></section>\n</article>")
    if not standalone:
        return article
    style = ("body{font-family:Georgia,serif;max-width:760px;margin:2rem auto;color:#222;line-height:1.55}"
             "h1,h2,h3{font-family:Arial,sans-serif}h1{color:#c1121f}table{border-collapse:collapse;width:100%;font-size:.85rem}"
             "td,th{border:1px solid #ddd;padding:4px 6px;text-align:left}.selo{font:600 .7rem Arial;color:#c1121f;"
             "border:1px solid #c1121f;border-radius:3px;padding:0 4px;margin-left:2px}figcaption{font-size:.8rem;color:#666}")
    return (f'<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><title>{e(text.title)}</title>'
            f"<style>{style}</style></head><body>{article}</body></html>")


def from_markdown(markdown: str, original: dict | None = None) -> dict:
    """Lê o Markdown gerado por to_markdown (e editado por uma pessoa) de volta para o contrato do texto.

    As quatro seções são lidas na ordem; `ponto_ids` e `afirmacao_ids` são preservados do original.
    """
    original = original or {}
    lines = markdown.replace("\r\n", "\n").split("\n")
    title = next((l[2:].strip() for l in lines if l.startswith("# ")), original.get("title", ""))
    blocks = re.split(r"^## +(.+)$", markdown.replace("\r\n", "\n"), flags=re.MULTILINE)
    head = blocks[0]
    subtitle_lines = [l.strip() for l in head.split("\n") if l.strip() and not l.startswith("# ")]
    named = [(blocks[i].strip(), blocks[i + 1].strip()) for i in range(1, len(blocks) - 1, 2)]
    body = [(t, c) for t, c in named if t.lower() not in {"fonte", "entenda os termos"}]
    data = {"title": title, "subtitle": " ".join(subtitle_lines) or original.get("subtitle", "")}
    for (name, _default), (heading, content) in zip(SECTION_TITLES.items(), body):
        previous = original.get(name) or {}
        data[name] = {"title": heading, "content": content,
                      "ponto_ids": previous.get("ponto_ids") or ["editado"], "afirmacao_ids": previous.get("afirmacao_ids", [])}
    for name in SECTION_TITLES:
        data.setdefault(name, original.get(name) or {"title": name, "content": "", "ponto_ids": ["editado"]})
    source = next((c for t, c in named if t.lower() == "fonte"), original.get("fonte_bloco") or "Fonte: texto editado.")
    box = next((c for t, c in named if t.lower() == "entenda os termos"), original.get("caixa_entenda_os_termos"))
    words = {n: len(data[n]["content"].split()) for n in SECTION_TITLES}
    data.update(fonte_bloco=source if "Fonte" in source else f"Fonte: {source}", caixa_entenda_os_termos=box,
                word_count_total=sum(words.values()), word_count_by_section=words,
                covered_main_points=original.get("covered_main_points", []))
    return data
