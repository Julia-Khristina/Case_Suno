"""Testes para ranking determinístico dos 3 pontos centrais da matriz."""
from __future__ import annotations

from src.triangulacao.matriz import ranking_pontos_centrais
from src.triangulacao.models import (
    LinhaMatriz, CelulaMatriz, StatusLinhaMatriz,
)


def _linha_divergencia_numerica(linha_id: str, topico: str, diferenca_relativa: float = 0.1) -> LinhaMatriz:
    return LinhaMatriz(
        linha_id=linha_id,
        topico=topico,
        status=StatusLinhaMatriz.DIVERGENCIA_NUMERICA,
        celulas=[
            CelulaMatriz(fonte_id="f1", fonte_nome="BCB", tipo_fonte="primaria",
                         valor_texto="10,50%", trecho="Selic 10,50%"),
            CelulaMatriz(fonte_id="f2", fonte_nome="Valor", tipo_fonte="secundaria",
                         valor_texto="12,00%", trecho="Selic 12,00%"),
        ],
        fontes_divergentes=["f1", "f2"],
        diferenca_relativa=diferenca_relativa,
    )


def _linha_divergencia_qualitativa(linha_id: str, topico: str) -> LinhaMatriz:
    return LinhaMatriz(
        linha_id=linha_id,
        topico=topico,
        status=StatusLinhaMatriz.DIVERGENCIA_QUALITATIVA,
        celulas=[
            CelulaMatriz(fonte_id="f1", fonte_nome="BCB", tipo_fonte="primaria",
                         valor_texto="aposenta aos 65", trecho="idade 65"),
            CelulaMatriz(fonte_id="f2", fonte_nome="Valor", tipo_fonte="secundaria",
                         valor_texto="aposenta aos 60", trecho="idade 60"),
        ],
        fontes_divergentes=["f1", "f2"],
    )


def _linha_convergencia(linha_id: str, topico: str) -> LinhaMatriz:
    return LinhaMatriz(
        linha_id=linha_id,
        topico=topico,
        status=StatusLinhaMatriz.CONVERGENCIA,
        celulas=[
            CelulaMatriz(fonte_id="f1", fonte_nome="BCB", tipo_fonte="primaria",
                         valor_texto="4,5%", trecho="IPCA 4,5%"),
            CelulaMatriz(fonte_id="f2", fonte_nome="Valor", tipo_fonte="secundaria",
                         valor_texto="4,5%", trecho="IPCA 4,5%"),
        ],
        fontes_convergentes=["f1", "f2"],
    )


def test_ranking_retorna_no_maximo_3():
    """Ranking deve retornar no máximo 3 pontos centrais."""
    linhas = [
        _linha_divergencia_numerica("d1", "Selic", 0.15),
        _linha_divergencia_qualitativa("d2", "IPCA"),
        _linha_convergencia("c1", "PIB"),
        _linha_divergencia_numerica("d3", "Câmbio", 0.08),
    ]
    resultado = ranking_pontos_centrais(linhas)
    assert len(resultado) <= 3


def test_ranking_divergencia_numerica_alta_tem_maior_peso():
    """Divergência numérica com alta diferença relativa deve ter maior score."""
    alta = _linha_divergencia_numerica("d_alta", "Selic", 0.20)
    baixa = _linha_divergencia_numerica("d_baixa", "IPCA", 0.01)
    resultado = ranking_pontos_centrais([alta, baixa])
    assert resultado[0].linha_id == "d_alta"


def test_ranking_divergencia_qualitativa_segundo_peso():
    """Divergência qualitativa tem peso 0.3, menor que divergência numérica relevante (0.5)."""
    div_num = _linha_divergencia_numerica("dn", "Selic", 0.15)
    div_qual = _linha_divergencia_qualitativa("dq", "IPCA")
    resultado = ranking_pontos_centrais([div_num, div_qual])
    assert resultado[0].linha_id == "dn"


def test_ranking_convergencia_terceiro_peso():
    """Convergência tem peso 0.2, menor que divergências."""
    conv = _linha_convergencia("c1", "PIB")
    div_num = _linha_divergencia_numerica("dn", "Selic", 0.15)
    resultado = ranking_pontos_centrais([conv, div_num])
    assert resultado[0].linha_id == "dn"


def test_ranking_ordena_por_score_decrescente():
    """Resultado deve estar ordenado por score decrescente."""
    linhas = [
        _linha_convergencia("c1", "PIB"),
        _linha_divergencia_qualitativa("dq", "IPCA"),
        _linha_divergencia_numerica("dn", "Selic", 0.15),
    ]
    resultado = ranking_pontos_centrais(linhas)
    assert resultado[0].linha_id == "dn"  # divergência numérica (0.5)
    assert resultado[1].linha_id == "dq"  # divergência qualitativa (0.3)
    assert resultado[2].linha_id == "c1"  # convergência (0.2)


def test_ranking_linha_confirmada_humano_recebe_bonus():
    """Linha revisada e confirmada pelo humano recebe bônus de 0.1."""
    sem_bonus = _linha_divergencia_qualitativa("sem", "IPCA")
    com_bonus = _linha_divergencia_qualitativa("com", "IPCA")
    com_bonus.revisada_por_humano = True
    com_bonus.confirmada_por_humano = True

    # Mesmo tipo, com bônus deve vir primeiro
    resultado = ranking_pontos_centrais([sem_bonus, com_bonus])
    assert resultado[0].linha_id == "com"


def test_ranking_lista_vazia_retorna_vazia():
    """Lista vazia deve retornar lista vazia."""
    resultado = ranking_pontos_centrais([])
    assert resultado == []


def test_ranking_menos_de_3_retorna_todas():
    """Menos de 3 linhas retorna todas ordenadas."""
    linhas = [_linha_divergencia_numerica("d1", "Selic", 0.15)]
    resultado = ranking_pontos_centrais(linhas)
    assert len(resultado) == 1
    assert resultado[0].linha_id == "d1"
