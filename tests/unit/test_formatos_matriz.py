"""Testes para geração de formatos a partir da matriz de triangulação."""
from __future__ import annotations

from src.triangulacao.formatos_matriz import (
    gerar_carrossel_matriz,
    gerar_roteiro_matriz,
    gerar_legenda_matriz,
)
from src.triangulacao.models import (
    LinhaMatriz, CelulaMatriz, StatusLinhaMatriz,
)


def _linha_divergencia(linha_id: str, topico: str) -> LinhaMatriz:
    return LinhaMatriz(
        linha_id=linha_id,
        topico=topico,
        status=StatusLinhaMatriz.DIVERGENCIA_NUMERICA,
        celulas=[
            CelulaMatriz(
                fonte_id="f1", fonte_nome="BCB", tipo_fonte="primaria",
                valor_texto="10,50%", trecho="Selic 10,50%",
            ),
            CelulaMatriz(
                fonte_id="f2", fonte_nome="Valor", tipo_fonte="secundaria",
                valor_texto="12,00%", trecho="Selic 12,00%",
            ),
        ],
        fontes_divergentes=["f1", "f2"],
    )


def _linha_convergencia(linha_id: str, topico: str) -> LinhaMatriz:
    return LinhaMatriz(
        linha_id=linha_id,
        topico=topico,
        status=StatusLinhaMatriz.CONVERGENCIA,
        celulas=[
            CelulaMatriz(
                fonte_id="f1", fonte_nome="BCB", tipo_fonte="primaria",
                valor_texto="4,5%", trecho="IPCA 4,5%",
            ),
            CelulaMatriz(
                fonte_id="f2", fonte_nome="Valor", tipo_fonte="secundaria",
                valor_texto="4,5%", trecho="IPCA 4,5%",
            ),
        ],
        fontes_convergentes=["f1", "f2"],
    )


FONTES = [
    {"nome": "BCB", "tipo_fonte": "primaria", "data": "2026-10-01"},
    {"nome": "Valor", "tipo_fonte": "secundaria", "data": "2026-10-01"},
]


def test_gerar_carrossel_5_slides():
    """Carrossel deve ter exatamente 5 slides: gancho, 3 corpo, conclusão."""
    matriz = [_linha_divergencia("d1", "Selic"), _linha_divergencia("d2", "IPCA")]
    resultado = gerar_carrossel_matriz(matriz, FONTES, "iniciante")

    slides = resultado["carousel"]["slides"]
    assert len(slides) == 5
    assert slides[0]["role"] == "gancho"
    assert slides[1]["role"] == "corpo"
    assert slides[2]["role"] == "corpo"
    assert slides[3]["role"] == "corpo"
    assert slides[4]["role"] == "conclusao"


def test_gerar_carrossel_cita_fontes():
    """Slides de corpo devem citar fontes pelo nome."""
    matriz = [_linha_divergencia("d1", "Selic")]
    resultado = gerar_carrossel_matriz(matriz, FONTES, "iniciante")

    corpo = slides = resultado["carousel"]["slides"][1]
    texto = corpo["body"] + corpo["title"]
    assert "BCB" in texto or "Valor" in texto


def test_gerar_carrossel_sem_divergencia_usa_convergencia():
    """Sem divergências, usa convergências nos slides de corpo."""
    matriz = [_linha_convergencia("c1", "IPCA")]
    resultado = gerar_carrossel_matriz(matriz, FONTES, "intermediario")

    slides = resultado["carousel"]["slides"]
    assert len(slides) == 5
    assert slides[1]["role"] == "corpo"
    assert "IPCA" in slides[1]["title"]


def test_gerar_carrossel_linha_vermelha_nivel():
    """Carrossel deve ter linha vermelha de nível."""
    matriz = [_linha_divergencia("d1", "Selic")]
    resultado = gerar_carrossel_matriz(matriz, FONTES, "avancado")

    assert resultado["carousel"]["linha_vermelha_nivel"] == "embaixo"

    resultado_i = gerar_carrossel_matriz(matriz, FONTES, "iniciante")
    assert resultado_i["carousel"]["linha_vermelha_nivel"] == "em cima"


def test_gerar_carrossel_legenda_cta_verbo():
    """Legenda deve ter cta_verb da lista."""
    matriz = [_linha_divergencia("d1", "Selic")]
    resultado = gerar_carrossel_matriz(matriz, FONTES, "iniciante")

    caption = resultado["caption"]
    assert caption["cta_verb"] in ("compartilhar", "curtir", "comentar", "salvar")
    assert caption["source_block"].startswith("Fonte:")


def test_gerar_carrossel_legenda_max_2000_chars():
    """Legenda não excede 2.000 caracteres."""
    matriz = [_linha_divergencia("d1", "Selic")]
    resultado = gerar_carrossel_matriz(matriz, FONTES, "iniciante")

    caption = resultado["caption"]
    total = len(caption["opening"] + caption["short_context"] + caption["cta_sentence"])
    assert total <= 2000


def test_gerar_roteiro_5_cenas():
    """Roteiro deve ter exatamente 5 cenas."""
    matriz = [_linha_divergencia("d1", "Selic"), _linha_divergencia("d2", "IPCA")]
    resultado = gerar_roteiro_matriz(matriz, FONTES, "iniciante")

    scenes = resultado["scenes"]
    assert len(scenes) == 5
    assert scenes[0]["role"] == "gancho"
    assert scenes[4]["role"] == "conclusao"


def test_gerar_roteiro_duracao_maximo_60s():
    """Roteiro deve ter duração total até 60 segundos."""
    matriz = [_linha_divergencia("d1", "Selic")]
    resultado = gerar_roteiro_matriz(matriz, FONTES, "iniciante")

    assert resultado["total_duration_sec"] <= 60


def test_gerar_roteiro_fala_escrita_e_falada():
    """Cada cena deve ter fala escrita e fala falada separadas."""
    matriz = [_linha_divergencia("d1", "Selic")]
    resultado = gerar_roteiro_matriz(matriz, FONTES, "iniciante")

    for cena in resultado["scenes"]:
        assert "fala_escrita" in cena
        assert "fala_falada" in cena
        assert cena["fala_escrita"] != "" or cena["fala_falada"] != ""


def test_gerar_roteiro_enquadramento_controlado():
    """Enquadramento deve ser close, plano_medio ou plano_aberto."""
    matriz = [_linha_divergencia("d1", "Selic")]
    resultado = gerar_roteiro_matriz(matriz, FONTES, "iniciante")

    validos = {"close", "plano_medio", "plano_aberto"}
    for cena in resultado["scenes"]:
        assert cena["enquadramento"] in validos


def test_gerar_legenda_matriz():
    """Legenda deve ter abertura, contexto, fonte, CTA."""
    matriz = [_linha_divergencia("d1", "Selic")]
    resultado = gerar_legenda_matriz(matriz, FONTES)

    assert "opening" in resultado
    assert "short_context" in resultado
    assert "source_block" in resultado
    assert "cta_verb" in resultado
    assert "cta_sentence" in resultado
    assert resultado["cta_verb"] in ("compartilhar", "curtir", "comentar", "salvar")


def test_gerar_legenda_matriz_max_2000():
    """Legenda da matriz não excede 2.000 caracteres."""
    matriz = [_linha_divergencia("d1", "Selic")]
    resultado = gerar_legenda_matriz(matriz, FONTES)

    total = len(resultado["opening"] + resultado["short_context"] + resultado["cta_sentence"])
    assert total <= 2000


def test_formatos_usam_mesmo_conjunto_divergencias():
    """Carrossel e roteiro usam as mesmas linhas de divergência da matriz."""
    matriz = [
        _linha_divergencia("d1", "Selic"),
        _linha_divergencia("d2", "IPCA"),
        _linha_divergencia("d3", "PIB"),
    ]

    carrossel = gerar_carrossel_matriz(matriz, FONTES, "iniciante")
    roteiro = gerar_roteiro_matriz(matriz, FONTES, "iniciante")

    # Ambos devem ter 3 slides/cenas de corpo com divergências
    slides_corpo = [s for s in carrossel["carousel"]["slides"] if s["role"] == "corpo"]
    cenas_corpo = [c for c in roteiro["scenes"] if c["role"] == "corpo"]

    assert len(slides_corpo) == 3
    assert len(cenas_corpo) == 3
