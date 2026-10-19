"""Detecao de origem comum entre fontes."""
from __future__ import annotations

import re
from typing import Any
from pathlib import Path

from src.triangulacao.models import OrigemComum


def extrair_dominio(url: str) -> str:
    """Extrai o dominio de uma URL."""
    if not url:
        return ""
    # Remove protocolo
    sem_protocolo = re.sub(r"^https?://", "", url, flags=re.IGNORECASE)
    # Remove caminho
    dominio = sem_protocolo.split("/")[0]
    return dominio.lower().strip()


def mesmo_identificador(texto_a: str, texto_b: str) -> bool:
    """Deteca se dois textos compartilham o mesmo identificador (numero de reuniao Copom, release, etc)."""
    if not texto_a or not texto_b:
        return False
    # Pads de numeros que podem ser identificadores. Anos (1900-2099) não identificam nada: "2026" aparece em
    # notícias independentes do mesmo ano e marcava fontes diferentes como de mesma origem.
    def numeros(texto: str) -> set[str]:
        found = set(re.findall(r"\b\d{2,}[-/]\d{2,}[-/]\d{2,}\b|(?<![\d.,])\d{3,}(?![\d.,]?\d)", texto))
        return {n for n in found if not re.fullmatch(r"(19|20)\d{2}", n)}

    return bool(numeros(texto_a) & numeros(texto_b))


def sobreposicao_literal(texto_a: str, texto_b: str, limiar: float = 0.6) -> bool:
    """Deteca sobreposicao literal de trechos entre dois textos."""
    if not texto_a or not texto_b:
        return False
    palavras_a = set(texto_a.lower().split())
    palavras_b = set(texto_b.lower().split())
    if not palavras_a or not palavras_b:
        return False
    intersecao = palavras_a & palavras_b
    menor = min(len(palavras_a), len(palavras_b))
    if menor == 0:
        return False
    return len(intersecao) / menor >= limiar


def detectar_origem_comum(
    fontes: list[dict[str, Any]],
    limiar_sobreposicao: float = 0.6,
) -> list[OrigemComum]:
    """Deteta grupos de fontes de mesma origem."""
    grupos: list[OrigemComum] = []
    fontes_agrupadas: set[str] = set()

    for i, fonte_a in enumerate(fontes):
        if fonte_a.get("id") in fontes_agrupadas:
            continue
        grupo_fontes = [fonte_a.get("id")]
        motivo_partes: list[str] = []
        documento_primario = None

        # Verifica se a fonte A é primária
        if fonte_a.get("tipo_fonte") == "primaria":
            documento_primario = fonte_a.get("nome", "")
            motivo_partes.append("documento primario")

        for j, fonte_b in enumerate(fontes[i + 1 :], start=i + 1):
            if fonte_b.get("id") in fontes_agrupadas:
                continue
            mesmo_grupo = False
            motivos: list[str] = []

            # 1. Mesmo link para pagina primaria
            url_a = fonte_a.get("url", "")
            url_b = fonte_b.get("url", "")
            if url_a and url_b and url_a == url_b:
                mesmo_grupo = True
                motivos.append("mesma pagina primaria")

            # 2. Mesmo identificador
            if mesmo_identificador(fonte_a.get("titulo", ""), fonte_b.get("titulo", "")):
                mesmo_grupo = True
                motivos.append("mesmo identificador")

            # 3. Sobreposicao literal de trechos
            trecho_a = fonte_a.get("trecho", "") or fonte_a.get("descricao", "") or ""
            trecho_b = fonte_b.get("trecho", "") or fonte_b.get("descricao", "") or ""
            if sobreposicao_literal(trecho_a, trecho_b, limiar_sobreposicao):
                mesmo_grupo = True
                motivos.append("sobreposicao literal de trechos")

            # 4. Uma eh o documento primario da outra
            if fonte_a.get("tipo_fonte") == "primaria" and fonte_b.get("tipo_fonte") == "secundaria":
                if url_a and url_b and dominio_url(url_a) == dominio_url(url_b):
                    mesmo_grupo = True
                    motivos.append("cobertura de documento primario")

            if mesmo_grupo:
                grupo_fontes.append(fonte_b.get("id"))
                fontes_agrupadas.add(fonte_b.get("id"))
                motivo_partes.extend(motivos)
                if fonte_b.get("tipo_fonte") == "primaria":
                    documento_primario = fonte_b.get("nome", "")

        if len(grupo_fontes) > 1:
            grupos.append(
                OrigemComum(
                    origem_comum_id=f"origem_{len(grupos) + 1}",
                    fonte_ids=grupo_fontes,
                    motivo="; ".join(set(motivo_partes)) or "mesma origem",
                    documento_primario=documento_primario,
                )
            )
            for fid in grupo_fontes:
                fontes_agrupadas.add(fid)

    return grupos


def dominio_url(url: str) -> str:
    """Extrai o dominio de uma URL (versao simples)."""
    if not url:
        return ""
    sem_protocolo = re.sub(r"^https?://", "", url, flags=re.IGNORECASE)
    return sem_protocolo.split("/")[0].lower().strip()


def fontes_independentes(
    fontes: list[dict[str, Any]],
    grupos_origem: list[OrigemComum],
) -> list[dict[str, Any]]:
    """Retorna fontes que sao independentes (nao compartilham origem comum)."""
    ids_em_grupo: set[str] = set()
    for grupo in grupos_origem:
        ids_em_grupo.update(grupo.fonte_ids)

    independentes = []
    for fonte in fontes:
        if fonte.get("id") not in ids_em_grupo:
            independentes.append(fonte)
    return independentes