"""Graficos determinísticos para triangulacao (matplotlib, nunca pelo modelo)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")  # backend sem interface grafica
import matplotlib.pyplot as plt


PALETA_VERMELHA = "#d32f2f"
PALETA_BRANCA = "#ffffff"
TONS_NEUTROS = ["#666666", "#999999", "#cccccc", "#e0e0e0"]


def _caminho_grafico(pasta_saida: Path, nome_base: str) -> Path:
    pasta_saida.mkdir(parents=True, exist_ok=True)
    return pasta_saida / f"{nome_base}.png"


def _hash_arquivo(caminho: Path) -> str:
    """Calcula hash SHA256 de um arquivo."""
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(8192), b""):
            h.update(bloco)
    return h.hexdigest()


def _salvar_dados_grafico(caminho_png: Path, dados: list[dict[str, Any]]) -> Path:
    """Salva JSON com os valores plotados ao lado do PNG."""
    caminho_json = caminho_png.with_suffix(".json")
    with caminho_json.open("w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    return caminho_json


def _texto_alternativo(regra: str, valores: list[dict[str, Any]]) -> str:
    """Gera texto alternativo montado por regra."""
    partes = [regra]
    for v in valores:
        partes.append(f"{v.get('fonte', 'fonte')}: {v.get('valor')} {v.get('unidade', '')} ({v.get('periodo', '')})")
    return "; ".join(partes)


def grafico_barras_agrupadas(
    valores: list[dict[str, Any]],
    indicador: str,
    periodo: str,
    pasta_saida: Path,
    nome_arquivo: str,
) -> dict[str, Any]:
    """Gera grafico de barras agrupadas por fonte para o mesmo indicador e periodo.

    So cria se houver 2 ou mais valores comparáveis.
    Retorna dicionario com arquivo, hash, dados_plotados e texto_alternativo.
    """
    if len(valores) < 2:
        return {"criado": False, "motivo": "menos de 2 valores comparáveis"}

    # Valida integridade: eixo y partindo de zero, sem interpolacao
    fontes = [v.get("fonte", "fonte") for v in valores]
    nums = [float(v.get("valor", 0)) for v in valores]
    unidades = [v.get("unidade", "") for v in valores]

    fig, ax = plt.subplots(figsize=(8, 5))
    cores = [PALETA_VERMELHA, PALETA_BRANCA] + TONS_NEUTROS[: len(valores) - 2]
    hatches = ["/", "\\", "|", "-", "+", "x", "o", "O", ".", "*"]

    bars = ax.bar(
        range(len(valores)),
        nums,
        color=cores[: len(valores)],
        edgecolor="#000000",
        hatch=hatches[: len(valores)],
    )

    ax.set_ylabel(f"{indicador} ({unidades[0] if unidades else ''})")
    ax.set_title(f"{indicador} - {periodo}")
    ax.set_xticks(range(len(valores)))
    ax.set_xticklabels(fontes, rotation=15, ha="right")
    ax.set_ylim(bottom=0)  # eixo y partindo de zero

    # Rótulos diretos nas barras (não só por cor)
    for bar, valor in zip(bars, nums):
        altura = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            altura,
            f"{valor}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    plt.tight_layout()

    caminho_png = _caminho_grafico(pasta_saida, nome_arquivo)
    fig.savefig(caminho_png, dpi=150, bbox_inches="tight")
    plt.close(fig)

    hash_arquivo = _hash_arquivo(caminho_png)
    dados_plotados = [
        {"fonte": f, "valor": n, "unidade": u, "periodo": periodo}
        for f, n, u in zip(fontes, nums, unidades)
    ]
    _salvar_dados_grafico(caminho_png, dados_plotados)

    texto_alt = _texto_alternativo(
        f"Grafico de barras agrupadas: {indicador} em {periodo}. ",
        dados_plotados,
    )

    return {
        "criado": True,
        "arquivo": str(caminho_png),
        "hash": hash_arquivo,
        "dados_plotados": dados_plotados,
        "texto_alternativo": texto_alt,
        "tipo": "barras_agrupadas",
        "indicador": indicador,
        "periodo": periodo,
    }


def grafico_tabela_convergencia(
    linhas: list[dict[str, Any]],
    pasta_saida: Path,
    nome_arquivo: str,
) -> dict[str, Any]:
    """Gera tabela de convergencia como imagem."""
    if not linhas:
        return {"criado": False, "motivo": "sem linhas"}

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.axis("off")

    dados_tabela = []
    for linha in linhas:
        dados_tabela.append([
            linha.get("topico", ""),
            linha.get("status", ""),
            str(linha.get("diferenca_absoluta", "")),
            str(linha.get("diferenca_relativa", "")),
        ])

    tabela = ax.table(
        cellText=dados_tabela,
        colLabels=["Topico", "Status", "Diff Absoluta", "Diff Relativa"],
        cellLoc="left",
        loc="center",
    )
    tabela.auto_set_font_size(False)
    tabela.set_fontsize(8)
    tabela.scale(1, 1.5)

    caminho_png = _caminho_grafico(pasta_saida, nome_arquivo)
    fig.savefig(caminho_png, dpi=150, bbox_inches="tight")
    plt.close(fig)

    hash_arquivo = _hash_arquivo(caminho_png)

    return {
        "criado": True,
        "arquivo": str(caminho_png),
        "hash": hash_arquivo,
        "tipo": "tabela_convergencia",
    }


def gerar_graficos_para_nivel(
    comparacoes: list[ComparacaoNumerica],
    nivel: str,
    pasta_saida: Path,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Gera graficos para um nivel, respeitando o máximo configurado."""
    config = config or {}
    max_graficos = {
        "iniciante": 2,
        "intermediario": 3,
        "avancado": 4,
    }.get(nivel, 2)

    # Sobrepoe com configuracao se existir
    cfg_graficos = config.get("graficos_por_nivel", {})
    max_graficos = cfg_graficos.get(nivel, max_graficos)

    gerados: list[dict[str, Any]] = []
    contador = 0

    for comp in comparacoes:
        if contador >= max_graficos:
            break
        if comp.status != "convergencia" and comp.status != "divergencia_numerica":
            continue
        if not comp.valores or len(comp.valores) < 2:
            continue

        nome_arquivo = f"grafico_{nivel}_{contador}_{comp.indicador}_{comp.periodo}"
        resultado = grafico_barras_agrupadas(
            valores=[
                {
                    "fonte": v.fonte_nome,
                    "valor": v.valor,
                    "unidade": v.unidade,
                    "periodo": v.periodo,
                }
                for v in comp.valores
            ],
            indicador=comp.indicador,
            periodo=comp.periodo,
            pasta_saida=pasta_saida,
            nome_arquivo=nome_arquivo,
        )
        if resultado.get("criado"):
            gerados.append(resultado)
            contador += 1

    return gerados