"""Sugestao automatica de candidatos para triangulacao (sem embeddings)."""
from __future__ import annotations

import re
from typing import Any
from pathlib import Path

import yaml

from src.triangulacao.models import TipoFonte


def load_config(path: str = "config/triangulacao.yaml") -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def similaridade_lexica_simples(texto_a: str, texto_b: str) -> float:
    """Similaridade lexical simples baseada em sobreposicao de palavras."""
    if not texto_a or not texto_b:
        return 0.0
    palavras_a = set(re.findall(r"\w+", texto_a.lower()))
    palavras_b = set(re.findall(r"\w+", texto_b.lower()))
    if not palavras_a or not palavras_b:
        return 0.0
    intersecao = palavras_a & palavras_b
    uniao = palavras_a | palavras_b
    return len(intersecao) / len(uniao) if uniao else 0.0


def proximidade_datas(data_a: str | None, data_b: str | None, janela_dias: int = 3) -> float:
    """Pontuacao de proximidade entre duas datas (1.0 = mesma data, 0.0 = fora da janela)."""
    if not data_a or not data_b:
        return 0.0
    try:
        from datetime import datetime

        # Tenta parsear datas comuns
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y"):
            try:
                da = datetime.strptime(data_a, fmt)
                db = datetime.strptime(data_b, fmt)
                diff = abs((da - db).days)
                if diff <= janela_dias:
                    return 1.0 - (diff / janela_dias)
                return 0.0
            except ValueError:
                continue
        return 0.0
    except Exception:
        return 0.0


def extrair_entidades(texto: str, apelidos: dict[str, list[str]] | None = None) -> set[str]:
    """Extrai entidades mencionadas no texto usando lista de apelidos."""
    if not texto:
        return set()
    texto_lower = texto.lower()
    encontradas: set[str] = set()
    if apelidos:
        for canonical, variacoes in apelidos.items():
            for v in [canonical] + variacoes:
                if v.lower() in texto_lower:
                    encontradas.add(canonical.lower())
    return encontradas


def pontuacao_candidato(
    fonte: dict[str, Any],
    fontes_referencia: list[dict[str, Any]],
    apelidos: dict[str, list[str]] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calcula pontuacao de uma fonte como candidata a triangulacao."""
    config = config or {}
    sugestao_cfg = config.get("sugestao", {})
    janela_dias = sugestao_cfg.get("janela_datas_dias", 3)
    peso_entidades = sugestao_cfg.get("peso_entidades_comum", 0.4)
    peso_data = sugestao_cfg.get("peso_proximidade_data", 0.3)
    peso_lexico = sugestao_cfg.get("peso_similaridade_lexica", 0.3)

    motivos: list[str] = []
    score_total = 0.0
    peso_total = 0.0

    texto_fonte = f"{fonte.get('titulo', '')} {fonte.get('descricao', '')}"

    for ref in fontes_referencia:
        if ref.get("id") == fonte.get("id"):
            continue

        texto_ref = f"{ref.get('titulo', '')} {ref.get('descricao', '')}"

        # 1. Entidades em comum
        entidades_fonte = extrair_entidades(texto_fonte, apelidos)
        entidades_ref = extrair_entidades(texto_ref, apelidos)
        entidades_comum = entidades_fonte & entidades_ref
        score_entidades = len(entidades_comum) / max(1, len(entidades_ref)) if entidades_ref else 0.0
        if entidades_comum:
            motivos.append(f"entidades com {ref.get('nome', 'fonte')}: {', '.join(sorted(entidades_comum))}")
        score_total += score_entidades * peso_entidades
        peso_total += peso_entidades

        # 2. Proximidade de datas
        score_data = proximidade_datas(fonte.get("data_publicacao"), ref.get("data_publicacao"), janela_dias)
        if score_data > 0:
            motivos.append(f"data proxima a {ref.get('nome', 'fonte')}")
        score_total += score_data * peso_data
        peso_total += peso_data

        # 3. Similaridade lexica de título/abertura
        score_lexico = similaridade_lexica_simples(texto_fonte, texto_ref)
        if score_lexico > 0.2:
            motivos.append(f"titulo similar a {ref.get('nome', 'fonte')}")
        score_total += score_lexico * peso_lexico
        peso_total += peso_lexico

    score_final = score_total / peso_total if peso_total > 0 else 0.0

    return {
        "id": fonte.get("id"),
        "nome": fonte.get("nome"),
        "titulo": fonte.get("titulo"),
        "tipo_fonte": fonte.get("tipo_fonte"),
        "url": fonte.get("url"),
        "data_publicacao": fonte.get("data_publicacao"),
        "score": round(score_final, 3),
        "motivos": motivos,
        "recomendado": score_final >= 0.4,  # so recomenda se score suficiente
    }


def sugerir_candidatos(
    fonte_referencia: dict[str, Any],
    pool_fontes: list[dict[str, Any]],
    apelidos: dict[str, list[str]] | None = None,
    config: dict[str, Any] | None = None,
    maximo_sugestoes: int = 5,
) -> list[dict[str, Any]]:
    """Sugere candidatos para triangulacao a partir de um pool de fontes."""
    config = config or {}
    candidatos = []

    for fonte in pool_fontes:
        if fonte.get("id") == fonte_referencia.get("id"):
            continue
        pontuacao = pontuacao_candidato(fonte, [fonte_referencia], apelidos, config)
        candidatos.append(pontuacao)

    # Ordena por score decrescente
    candidatos.sort(key=lambda c: c["score"], reverse=True)

    # So retorna os que tem score > 0 e nao sao recomendacao automatica forte
    resultado = []
    for c in candidatos[:maximo_sugestoes]:
        if c["score"] > 0:
            resultado.append(c)

    return resultado


def avaliar_conjunto(
    fontes: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Avalia se um conjunto de fontes e valido para triangulacao."""
    config = config or {}
    fontes_cfg = config.get("fontes", {})
    minimo = fontes_cfg.get("minimo", 2)
    maximo = fontes_cfg.get("maximo", 5)

    if len(fontes) < minimo:
        return {
            "valido": False,
            "motivo": f"minimo de {minimo} fontes necessario, tem {len(fontes)}",
            "total_fontes": len(fontes),
            "fontes_independentes": len(fontes),
            "pode_triangular": False,
        }

    if len(fontes) > maximo:
        return {
            "valido": False,
            "motivo": f"maximo de {maximo} fontes permitido, tem {len(fontes)}",
            "total_fontes": len(fontes),
            "fontes_independentes": len(fontes),
            "pode_triangular": False,
        }

    return {
        "valido": True,
        "motivo": "conjunto valido para triangulacao",
        "total_fontes": len(fontes),
        "fontes_independentes": len(fontes),
        "pode_triangular": True,
    }