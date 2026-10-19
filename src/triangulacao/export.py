"""Exportações para triangulação de fontes (HTML, Markdown, PNG, ZIP)."""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


def _hash_contexto(versoes: dict[str, str]) -> str:
    """Gera hash do contexto de execução."""
    h = hashlib.sha256()
    h.update(json.dumps(versoes, sort_keys=True).encode("utf-8"))
    return h.hexdigest()[:16]


def _imagem_para_base64(caminho: Path) -> str:
    """Converte imagem PNG para base64 para embutir no HTML."""
    if not caminho or not caminho.exists():
        return ""
    with caminho.open("rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def exportar_html_autocontido(
    triangulacao_id: str,
    nivel: str,
    dados: dict[str, Any],
    pasta_saida: Path,
) -> dict[str, Any]:
    """Exporta HTML autocontido com CSS inline, gráficos em base64, sem dependência externa."""
    pasta_saida.mkdir(parents=True, exist_ok=True)
    nome_arquivo = f"relatorio_{triangulacao_id}_{nivel}.html"
    caminho = pasta_saida / nome_arquivo

    fontes = dados.get("fontes", [])
    matriz = dados.get("matriz", [])
    texto = dados.get("texto", {})
    graficos = dados.get("graficos", [])
    hash_contexto = dados.get("hash_contexto_execucao", "")

    # Monta bloco de fontes
    fontes_html = ""
    for f in fontes:
        origem = f.get("origem_comum_id", "")
        origem_texto = f" (grupo de origem: {origem})" if origem else ""
        fontes_html += (
            f"<li><strong>{f.get('nome', '')}</strong> "
            f"({f.get('tipo_fonte', '')}, {f.get('data', 'sem data')}){origem_texto}</li>"
        )

    # Monta matriz como tabela
    matriz_html = "<table border='1' cellpadding='5'>"
    matriz_html += "<tr><th>Linha</th><th>Tópico</th><th>Status</th><th>Fontes</th></tr>"
    for linha in matriz:
        fontes_celula = ", ".join(c.get("fonte_nome", "") for c in linha.get("celulas", []))
        matriz_html += (
            f"<tr>"
            f"<td>{linha.get('linha_id', '')}</td>"
            f"<td>{linha.get('topico', '')}</td>"
            f"<td>{linha.get('status', '')}</td>"
            f"<td>{fontes_celula}</td>"
            f"</tr>"
        )
    matriz_html += "</table>"

    # Monta gráficos em base64
    graficos_html = ""
    for g in graficos:
        img_b64 = _imagem_para_base64(Path(g.get("arquivo", "")))
        if img_b64:
            graficos_html += (
                f"<figure>"
                f"<img src='data:image/png;base64,{img_b64}' alt='{g.get('texto_alternativo', '')}'/>"
                f"<figcaption>{g.get('texto_alternativo', '')}</figcaption>"
                f"</figure>"
            )

    # HTML completo
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>{texto.get('title', 'Relatório de Triangulação')} — {nivel.title()}</title>
<style>
body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; color: #333; }}
h1 {{ color: #d32f2f; border-bottom: 2px solid #d32f2f; padding-bottom: 10px; }}
h2 {{ color: #d32f2f; }}
h3 {{ color: #666; }}
.section {{ margin-bottom: 30px; }}
.fontes {{ background: #f9f9f9; padding: 15px; border-left: 4px solid #d32f2f; }}
.matriz {{ margin: 20px 0; }}
table {{ border-collapse: collapse; width: 100%; }}
th {{ background: #d32f2f; color: white; }}
td {{ border: 1px solid #ddd; }}
.grafico {{ margin: 20px 0; text-align: center; }}
.grafico img {{ max-width: 100%; height: auto; }}
.aviso {{ background: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; margin: 15px 0; }}
.hash {{ font-size: 0.8em; color: #666; font-family: monospace; }}
</style>
</head>
<body>
<h1>{texto.get('title', 'Relatório de Triangulação')}</h1>
<h2>{texto.get('subtitle', '')}</h2>

<div class="hash"><strong>Hash do contexto de execução:</strong> {hash_contexto}</div>

<div class="section">
<h3>Introdução</h3>
<p>{texto.get('introduction', '')}</p>
</div>

<div class="section">
<h3>Desenvolvimento</h3>
<p>{texto.get('development', '')}</p>
</div>

<div class="section">
<h3>Análise</h3>
<p>{texto.get('analysis', '')}</p>
</div>

<div class="section">
<h3>Conclusão</h3>
<p>{texto.get('conclusion', '')}</p>
</div>

<div class="section fontes">
<h3>Bloco de Fontes</h3>
<ul>
{fontes_html}
</ul>
</div>

<div class="section matriz">
<h3>Matriz de Comparação (Apêndice)</h3>
{matriz_html}
</div>

<div class="section graficos">
<h3>Gráficos</h3>
{graficos_html}
</div>

<div class="aviso">
<strong>Aviso padrão:</strong> Conteúdo educativo. Não é recomendação de investimento.
</div>
</body>
</html>"""

    caminho.write_text(html, encoding="utf-8")

    return {
        "arquivo": str(caminho),
        "tipo": "html_autocontido",
        "nivel": nivel,
        "hash_contexto": hash_contexto,
    }


def exportar_markdown(
    triangulacao_id: str,
    nivel: str,
    dados: dict[str, Any],
    pasta_saida: Path,
) -> dict[str, Any]:
    """Exporta Markdown com PNGs dos gráficos em uma pasta."""
    pasta_saida.mkdir(parents=True, exist_ok=True)
    nome_arquivo = f"relatorio_{triangulacao_id}_{nivel}.md"
    caminho = pasta_saida / nome_arquivo

    fontes = dados.get("fontes", [])
    matriz = dados.get("matriz", [])
    texto = dados.get("texto", {})
    graficos = dados.get("graficos", [])
    hash_contexto = dados.get("hash_contexto_execucao", "")

    # Copia PNGs para a pasta de saída
    graficos_md = ""
    for g in graficos:
        origem = Path(g.get("arquivo", ""))
        if origem.exists():
            destino = pasta_saida / origem.name
            destino.write_bytes(origem.read_bytes())
            graficos_md += f"\n![{g.get('texto_alternativo', '')}]({origem.name})\n{g.get('texto_alternativo', '')}\n"

    # Monta bloco de fontes
    fontes_md = ""
    for f in fontes:
        origem = f.get("origem_comum_id", "")
        origem_texto = f" (grupo de origem: {origem})" if origem else ""
        fontes_md += f"- {f.get('nome', '')} ({f.get('tipo_fonte', '')}, {f.get('data', 'sem data')}){origem_texto}\n"

    # Matriz como tabela markdown
    matriz_md = "| Linha | Tópico | Status | Fontes |\n|-------|--------|--------|--------|\n"
    for linha in matriz:
        fontes_celula = ", ".join(c.get("fonte_nome", "") for c in linha.get("celulas", []))
        matriz_md += f"| {linha.get('linha_id', '')} | {linha.get('topico', '')} | {linha.get('status', '')} | {fontes_celula} |\n"

    md = f"""# {texto.get('title', 'Relatório de Triangulação')} — {nivel.title()}

**Hash do contexto de execução:** `{hash_contexto}`

## Introdução

{texto.get('introduction', '')}

## Desenvolvimento

{texto.get('development', '')}

{graficos_md}

## Análise

{texto.get('analysis', '')}

## Conclusão

{texto.get('conclusion', '')}

## Bloco de Fontes

{fontes_md}

## Matriz de Comparação (Apêndice)

{matriz_md}

---

*Aviso padrão: Conteúdo educativo. Não é recomendação de investimento.*
"""

    caminho.write_text(md, encoding="utf-8")

    return {
        "arquivo": str(caminho),
        "tipo": "markdown",
        "nivel": nivel,
        "hash_contexto": hash_contexto,
    }


def exportar_zip_graficos(
    triangulacao_id: str,
    graficos: list[dict[str, Any]],
    pasta_saida: Path,
) -> dict[str, Any]:
    """Exporta ZIP com os gráficos PNG."""
    import zipfile

    pasta_saida.mkdir(parents=True, exist_ok=True)
    nome_arquivo = f"graficos_{triangulacao_id}.zip"
    caminho = pasta_saida / nome_arquivo

    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as archive:
        for g in graficos:
            arquivo_png = Path(g.get("arquivo", ""))
            if arquivo_png.exists():
                archive.write(arquivo_png, arcname=arquivo_png.name)
            # Também inclui o JSON de dados se existir
            arquivo_json = arquivo_png.with_suffix(".json")
            if arquivo_json.exists():
                archive.write(arquivo_json, arcname=arquivo_json.name)

    return {
        "arquivo": str(caminho),
        "tipo": "zip_graficos",
        "n_graficos": len(graficos),
    }


def exportar_todos_niveis(
    triangulacao_id: str,
    resultados_por_nivel: dict[str, dict[str, Any]],
    pasta_base: Path,
) -> dict[str, Any]:
    """Exporta relatórios para todos os níveis (HTML, Markdown, ZIP)."""
    pasta_base.mkdir(parents=True, exist_ok=True)

    exportados = []

    for nivel, dados in resultados_por_nivel.items():
        pasta_nivel = pasta_base / nivel

        # HTML
        res_html = exportar_html_autocontido(triangulacao_id, nivel, dados, pasta_nivel)
        exportados.append(res_html)

        # Markdown
        res_md = exportar_markdown(triangulacao_id, nivel, dados, pasta_nivel)
        exportados.append(res_md)

        # ZIP de gráficos
        graficos = dados.get("graficos", [])
        if graficos:
            res_zip = exportar_zip_graficos(triangulacao_id, graficos, pasta_nivel)
            exportados.append(res_zip)

    return {
        "triangulacao_id": triangulacao_id,
        "niveis": list(resultados_por_nivel.keys()),
        "arquivos": exportados,
    }


def estimar_tokens(
    n_fontes: int,
    n_niveis: int,
    n_tentativas_juiz: int = 1,
) -> dict[str, Any]:
    """Estima consumo de tokens para triangulação.

    Referência (suposição a medir): cerca de 85 mil tokens para 3 fontes e 3 níveis.
    """
    # Estimativa baseada na referência
    tokens_por_fonte_extracao = 8000  # extração por documento sem cache
    tokens_por_nivel_geracao = 12000  # geração de texto por nível
    tokens_por_juiz = 6000  # juiz por nível
    tokens_classificacao = 3000  # classificação qualitativa em lote

    tokens_extracao = n_fontes * tokens_por_fonte_extracao
    tokens_geracao = n_niveis * tokens_por_nivel_geracao
    tokens_juiz = n_niveis * n_tentativas_juiz * tokens_por_juiz
    tokens_classificacao_total = tokens_classificacao  # uma chamada em lote

    total_estimado = tokens_extracao + tokens_geracao + tokens_juiz + tokens_classificacao_total

    return {
        "n_fontes": n_fontes,
        "n_niveis": n_niveis,
        "tokens_extracao": tokens_extracao,
        "tokens_geracao": tokens_geracao,
        "tokens_juiz": tokens_juiz,
        "tokens_classificacao": tokens_classificacao_total,
        "total_estimado": total_estimado,
        "referencia": "85 mil tokens para 3 fontes e 3 níveis (suposição a medir)",
        "dentro_cota_dia": total_estimado <= 200000,  # cota diária gratuita do Groq
        "dentro_cota_minuto": total_estimado <= 8000,  # cota por minuto (apenas se executado de uma vez)
    }