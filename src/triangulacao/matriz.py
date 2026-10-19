"""Montagem da matriz de triangulacao com revisao humana."""
from __future__ import annotations

from typing import Any
from pathlib import Path
import yaml

from src.triangulacao.models import (
    LinhaMatriz,
    CelulaMatriz,
    StatusLinhaMatriz,
    ComparacaoNumerica,
    PosicaoClassificada,
    PosicaoQualitativa,
    Triangulacao,
)
from src.triangulacao.origem_comum import detectar_origem_comum, fontes_independentes, OrigemComum
from src.triangulacao.normalizacao import comparar_valores_numericos, agrupar_por_indicador_unidade_periodo
from src.triangulacao.classificacao_qualitativa import eh_divergencia_qualitativa, posicoes_opostas


def load_config_triangulacao(path: str = "config/triangulacao.yaml") -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _trecho_curto(trecho: str | None, max_palavras: int = 25) -> str:
    """Gera citacao curta de max 25 palavras."""
    if not trecho:
        return ""
    palavras = trecho.split()
    if len(palavras) <= max_palavras:
        return trecho
    return " ".join(palavras[:max_palavras]) + "..."


def montar_matriz(
    triangulacao: Triangulacao,
    comparacoes_numericas: list[ComparacaoNumerica],
    classificacoes_qualitativas: list[PosicaoClassificada],
    config: dict[str, Any] | None = None,
) -> list[LinhaMatriz]:
    """Monta a matriz de triangulacao a partir de comparacoes numericas e classificacoes qualitativas."""
    config = config or load_config_triangulacao()
    fontes_por_id = {f.get("id"): f for f in triangulacao.fontes}

    linhas: list[LinhaMatriz] = []

    # 1. Linhas a partir de comparacoes numericas
    for comp in comparacoes_numericas:
        celulas: list[CelulaMatriz] = []
        for v in comp.valores:
            fonte_meta = fontes_por_id.get(v.fonte_id, {})
            celulas.append(
                CelulaMatriz(
                    fonte_id=v.fonte_id,
                    fonte_nome=v.fonte_nome,
                    tipo_fonte=fonte_meta.get("tipo_fonte", "secundaria"),
                    data=v.periodo or fonte_meta.get("data"),
                    valor_texto=f"{v.valor} {v.unidade}",
                    trecho=v.trecho,
                    trecho_curto=_trecho_curto(v.trecho),
                    origem_comum_id=None,
                    dado_numerico={
                        "indicador": v.indicador,
                        "valor": v.valor,
                        "unidade": v.unidade,
                        "periodo": v.periodo,
                    },
                )
            )

        status = comp.status
        linha = LinhaMatriz(
            linha_id=f"num_{comp.indicador}_{comp.periodo}",
            topico=f"{comp.indicador} ({comp.periodo})",
            status=status,
            celulas=celulas,
            diferenca_absoluta=comp.diferenca_absoluta,
            diferenca_relativa=comp.diferenca_relativa,
            justificativa_status=comp.motivo_nao_comparavel or f"Comparacao numerica: {comp.status.value}",
        )

        if status == StatusLinhaMatriz.DIVERGENCIA_NUMERICA:
            linha.fontes_divergentes = [v.fonte_id for v in comp.valores]
        elif status == StatusLinhaMatriz.CONVERGENCIA:
            linha.fontes_convergentes = [v.fonte_id for v in comp.valores]

        linhas.append(linha)

    # 2. Linhas a partir de classificacoes qualitativas
    # Agrupa classificacoes por topico (usando o topico da afirmacao ou um default)
    classificacoes_por_topico: dict[str, list[PosicaoClassificada]] = {}
    for c in classificacoes_qualitativas:
        # Usamos o topico da classificacao se disponível, caso contrário extraímos do trecho
        topico = getattr(c, "topico", "afirmacao_qualitativa") or "afirmacao_qualitativa"
        classificacoes_por_topico.setdefault(topico, []).append(c)

    for topico, classifs in classificacoes_por_topico.items():
        celulas: list[CelulaMatriz] = []
        for c in classifs:
            fonte_meta = fontes_por_id.get(c.fonte_id, {})
            celulas.append(
                CelulaMatriz(
                    fonte_id=c.fonte_id,
                    fonte_nome=fonte_meta.get("nome", c.fonte_id),
                    tipo_fonte=fonte_meta.get("tipo_fonte", "secundaria"),
                    data=None,
                    valor_texto=None,
                    trecho=c.trecho_evidencia,
                    trecho_curto=_trecho_curto(c.trecho_evidencia),
                    origem_comum_id=None,
                    confianca=c.confianca,
                    posicao_qualitativa=c.posicao,
                )
            )

        # Verifica divergencia qualitativa
        if eh_divergencia_qualitativa(classifs):
            status = StatusLinhaMatriz.DIVERGENCIA_QUALITATIVA
            opostas = posicoes_opostas(classifs)
            if opostas:
                apoiando, contestando = opostas
                linha.fontes_convergentes = [c.fonte_id for c in apoiando]
                linha.fontes_divergentes = [c.fonte_id for c in contestando]
        else:
            # Verifica se todas nao mencionam
            todas_nao_menciona = all(c.posicao == PosicaoQualitativa.NAO_MENCIONA for c in classifs)
            if todas_nao_menciona:
                status = StatusLinhaMatriz.SEM_CONTRA_PONTO
            else:
                # Tem pelo menos uma posicao, mas sem oposicao clara
                status = StatusLinhaMatriz.SEM_CONTRA_PONTO
            posicoes_apoiando = [c.fonte_id for c in classifs if c.posicao == PosicaoQualitativa.APOIA]
            if posicoes_apoiando:
                linha.fontes_convergentes = posicoes_apoiando

        linha = LinhaMatriz(
            linha_id=f"qual_{topico.replace(' ', '_')}",
            topico=topico,
            status=status,
            celulas=celulas,
            justificativa_status=f"Classificacao qualitativa: {status.value}",
        )
        linhas.append(linha)

    return linhas


def aplicar_revisao_humana(
    linha: LinhaMatriz,
    confirmada: bool,
    justificativa: str | None = None,
) -> LinhaMatriz:
    """Aplica decisao de revisao humana a uma linha da matriz."""
    linha.revisada_por_humano = True
    linha.confirmada_por_humano = confirmada
    if justificativa:
        linha.justificativa_status = justificativa
    return linha


def linhas_pendentes_revisao(linhas: list[LinhaMatriz]) -> list[LinhaMatriz]:
    """Retorna linhas que ainda precisam de revisao humana (qualitativas nao confirmadas)."""
    return [
        l for l in linhas
        if not l.revisada_por_humano and l.status == StatusLinhaMatriz.DIVERGENCIA_QUALITATIVA
    ]


def linhas_aprovadas(linhas: list[LinhaMatriz]) -> list[LinhaMatriz]:
    """Retorna linhas aprovadas (numericas automaticas + qualitativas confirmadas)."""
    aprovadas: list[LinhaMatriz] = []
    for l in linhas:
        if l.status in (StatusLinhaMatriz.CONVERGENCIA, StatusLinhaMatriz.DIVERGENCIA_NUMERICA):
            # Numericas entram automaticamente (revisaveis)
            aprovadas.append(l)
        elif l.status == StatusLinhaMatriz.DIVERGENCIA_QUALITATIVA and l.confirmada_por_humano is True:
            aprovadas.append(l)
    return aprovadas


def ranking_pontos_centrais(
    linhas: list[LinhaMatriz],
    configuracao: dict[str, Any] | None = None,
) -> list[LinhaMatriz]:
    """Ranking determinístico dos 3 pontos centrais da matriz.

    Pesos (config/triangulacao.yaml, ranking_pontos_centrais):
      - divergencia_numerica_relevante: 0.5
      - divergencia_qualitativa: 0.3
      - convergencia_importante: 0.2

    Retorna as 3 linhas com maior score, ordenadas por score decrescente.
    """
    configuracao = configuracao or load_config_triangulacao()
    pesos_cfg = configuracao.get("ranking_pontos_centrais", {})
    peso_div_num = float(pesos_cfg.get("divergencia_numerica_relevante", 0.5))
    peso_div_qual = float(pesos_cfg.get("divergencia_qualitativa", 0.3))
    peso_conv = float(pesos_cfg.get("convergencia_importante", 0.2))

    linhas_com_score: list[tuple[float, LinhaMatriz]] = []
    for linha in linhas:
        score = 0.0
        if linha.status == StatusLinhaMatriz.DIVERGENCIA_NUMERICA:
            # Divergência numérica relevante: score maior se a diferença for significativa
            if linha.diferenca_relativa is not None and linha.diferenca_relativa > 0.05:
                score += peso_div_num
            else:
                score += peso_div_num * 0.5  # divergência menor, peso reduzido
        elif linha.status == StatusLinhaMatriz.DIVERGENCIA_QUALITATIVA:
            score += peso_div_qual
        elif linha.status == StatusLinhaMatriz.CONVERGENCIA:
            score += peso_conv

        # Linhas revisadas e confirmadas pelo humano recebem bônus
        if linha.revisada_por_humano and linha.confirmada_por_humano:
            score += 0.1

        linhas_com_score.append((score, linha))

    # Ordena por score decrescente, depois por linha_id para estabilidade
    linhas_com_score.sort(key=lambda item: (-item[0], item[1].linha_id))

    top_3 = [linha for _, linha in linhas_com_score[:3]]
    return top_3


def detectar_grupos_origem_comum(
    fontes: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> list[OrigemComum]:
    """Deteta grupos de fontes de mesma origem."""
    config = config or load_config_triangulacao()
    origem_cfg = config.get("origem_comum", {})
    limiar = origem_cfg.get("limiar_sobreposicao_literal", 0.6)
    return detectar_origem_comum(fontes, limiar_sobreposicao=limiar)


def avaliar_conjunto_fontes(
    fontes: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Avalia se o conjunto permite triangulacao e identifica origens comuns."""
    config = config or load_config_triangulacao()
    grupos = detectar_grupos_origem_comum(fontes, config)
    independentes = fontes_independentes(fontes, grupos)

    fontes_cfg = config.get("fontes", {})
    minimo = fontes_cfg.get("minimo", 2)

    permite = len(independentes) >= minimo and len(fontes) >= minimo

    aviso = None
    if not permite:
        if len(fontes) < minimo:
            aviso = f"Minimo de {minimo} fontes necessario. Tem {len(fontes)}."
        elif len(independentes) < minimo:
            aviso = (
                f"Minimo de {minimo} fontes independentes necessario. "
                f"Tem {len(independentes)} independente(s) (outras compartilham origem comum)."
            )

    return {
        "valido": permite,
        "total_fontes": len(fontes),
        "fontes_independentes": len(independentes),
        "fontes_independentes_lista": independentes,
        "grupos_origem_comum": [g.model_dump() for g in grupos],
        "pode_triangular": permite,
        "aviso_sem_triangulacao": aviso,
    }