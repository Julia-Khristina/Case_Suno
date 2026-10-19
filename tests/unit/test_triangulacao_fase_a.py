"""Testes da Fase A - Base deterministica da triangulacao de fontes."""
from __future__ import annotations

from src.triangulacao.normalizacao import (
    load_indicadores,
    normalizar_numero,
    encontrar_indicador,
    normalizar_dados_numericos,
    comparar_valores_numericos,
    converter_escala,
    agrupar_por_indicador_unidade_periodo,
)
from src.triangulacao.origem_comum import (
    detectar_origem_comum,
    fontes_independentes,
    mesmo_identificador,
    sobreposicao_literal,
    extrair_dominio,
)
from src.triangulacao.sugestao import (
    pontuacao_candidato,
    sugerir_candidatos,
    avaliar_conjunto,
    similaridade_lexica_simples,
    proximidade_datas,
)
from src.triangulacao.models import (
    DadoNumericoNormalizado,
    ComparacaoNumerica,
    StatusLinhaMatriz,
    PosicaoQualitativa,
)


# ============================================================================
# Normalizacao numerica
# ============================================================================

def test_normalizar_numero_formatos():
    """Normalizacao de numeros em diferentes formatos."""
    assert normalizar_numero("10,50") == 10.5
    assert normalizar_numero("10.50") == 10.5
    assert normalizar_numero("1.234,56") == 1234.56
    assert normalizar_numero("R$ 1.000,00") == 1000.0
    assert normalizar_numero("4,5%") == 4.5
    assert normalizar_numero("") is None
    assert normalizar_numero("abc") is None


def test_encontrar_indicador():
    """Encontra indicador canonico por nome ou apelido."""
    indicadores = load_indicadores()["indicadores"]
    assert encontrar_indicador("Selic", indicadores) == "Selic"
    assert encontrar_indicador("taxa selic", indicadores) == "Selic"
    assert encontrar_indicador("IPCA", indicadores) == "IPCA"
    assert encontrar_indicador("inflacao oficial", indicadores) == "IPCA"
    assert encontrar_indicador("PIB", indicadores) == "PIB"
    assert encontrar_indicador("dolar", indicadores) == "cambio"
    assert encontrar_indicador("foo bar", indicadores) is None


def test_converter_escala():
    """Conversao de escalas."""
    escalas = {"unidade": 1, "mil": 1000, "milhao": 1000000, "bilhao": 1000000000}
    assert converter_escala(5.0, "unidade", escalas) == 5.0
    assert converter_escala(2.0, "mil", escalas) == 2000.0
    assert converter_escala(1.5, "milhao", escalas) == 1500000.0
    assert converter_escala(3.0, "bilhao", escalas) == 3000000000.0


def test_normalizar_dados_brutos():
    """Normalizacao de dados brutos extraidos de fontes."""
    indicadores = load_indicadores()["indicadores"]
    escalas = load_indicadores()["escalas"]

    dados = [
        {"indicador": "Selic", "valor": "10,50", "unidade": "a.a.", "reference_period": "atual",
         "fonte_id": "f1", "fonte_nome": "BCB", "trecho": "Selic em 10,50%"},
        {"indicador": "IPCA", "valor": "4,5", "unidade": "%", "reference_period": "12 meses",
         "fonte_id": "f2", "fonte_nome": "IBGE", "trecho": "IPCA em 4,5%"},
        {"indicador": "FooBar", "valor": "100", "unidade": "unidade", "reference_period": "atual",
         "fonte_id": "f3", "fonte_nome": "X", "trecho": "FooBar 100"},
    ]

    normalizados = normalizar_dados_numericos(dados, indicadores, escalas)
    assert len(normalizados) == 3

    selic = normalizados[0]
    assert selic.indicador == "Selic"
    assert selic.valor == 10.5
    assert selic.normalizado is True

    ipca = normalizados[1]
    assert ipca.indicador == "IPCA"
    assert ipca.valor == 4.5

    foobar = normalizados[2]
    assert foobar.indicador == "FooBar"
    assert foobar.normalizado is False  # nao normalizado


# ============================================================================
# Comparacao numerica
# ============================================================================

def test_comparacao_convergencia():
    """Valores dentro da tolerancia = convergencia."""
    valores = [
        DadoNumericoNormalizado(indicador="Selic", valor=10.50, unidade="% a.a.", periodo="atual",
                                fonte_id="f1", fonte_nome="BCB", trecho="Selic 10,50%"),
        DadoNumericoNormalizado(indicador="Selic", valor=10.55, unidade="% a.a.", periodo="atual",
                                fonte_id="f2", fonte_nome="XP", trecho="Selic 10,55%"),
    ]
    ind_config = {"tolerancia_absoluta": 0.25, "tolerancia_relativa": 0.02}
    resultado = comparar_valores_numericos(valores, ind_config, {})
    assert resultado.status == StatusLinhaMatriz.CONVERGENCIA
    assert resultado.diferenca_absoluta == 0.05


def test_comparacao_divergencia_numerica():
    """Valores fora da tolerancia = divergencia numerica."""
    valores = [
        DadoNumericoNormalizado(indicador="Selic", valor=10.50, unidade="% a.a.", periodo="atual",
                                fonte_id="f1", fonte_nome="BCB", trecho="Selic 10,50%"),
        DadoNumericoNormalizado(indicador="Selic", valor=12.00, unidade="% a.a.", periodo="atual",
                                fonte_id="f2", fonte_nome="XP", trecho="Selic 12,00%"),
    ]
    ind_config = {"tolerancia_absoluta": 0.25, "tolerancia_relativa": 0.02}
    resultado = comparar_valores_numericos(valores, ind_config, {})
    assert resultado.status == StatusLinhaMatriz.DIVERGENCIA_NUMERICA
    assert resultado.diferenca_absoluta == 1.5


def test_comparacao_escala_diferente():
    """Escala diferente (milhão vs bilhão) - conversao pela configuracao."""
    valores = [
        DadoNumericoNormalizado(indicador="PIB", valor=2.0, unidade="milhao", periodo="2026",
                                fonte_id="f1", fonte_nome="BCB", trecho="PIB 2 milhoes", escala="milhao"),
        DadoNumericoNormalizado(indicador="PIB", valor=0.002, unidade="bilhao", periodo="2026",
                                fonte_id="f2", fonte_nome="IBGE", trecho="PIB 0,002 bilhoes", escala="bilhao"),
    ]
    ind_config = {"tolerancia_absoluta": 0.01, "tolerancia_relativa": 0.01}
    escalas = {"unidade": 1, "mil": 1000, "milhao": 1000000, "bilhao": 1000000000}
    normalizados = [
        DadoNumericoNormalizado(indicador="PIB", valor=2.0 * 1000000, unidade="unidade", periodo="2026",
                                fonte_id="f1", fonte_nome="BCB", trecho="PIB 2 milhoes", escala="milhao", normalizado=True),
        DadoNumericoNormalizado(indicador="PIB", valor=0.002 * 1000000000, unidade="unidade", periodo="2026",
                                fonte_id="f2", fonte_nome="IBGE", trecho="PIB 0,002 bilhoes", escala="bilhao", normalizado=True),
    ]
    # Ambos sao 2.000.000 em unidade canonica
    resultado = comparar_valores_numericos(normalizados, ind_config, {})
    assert resultado.status == StatusLinhaMatriz.CONVERGENCIA


def test_comparacao_percentual_vs_ponto_percentual():
    """Percentual versus ponto percentual = nao comparavel."""
    valores = [
        DadoNumericoNormalizado(indicador="Selic", valor=10.50, unidade="percentual", periodo="atual",
                                fonte_id="f1", fonte_nome="BCB", trecho="10,50%"),
        DadoNumericoNormalizado(indicador="Selic", valor=0.5, unidade="ponto percentual", periodo="atual",
                                fonte_id="f2", fonte_nome="XP", trecho="+0,5 pp"),
    ]
    resultado = comparar_valores_numericos(valores, None, {})
    assert resultado.status == StatusLinhaMatriz.NAO_COMPARAVEL
    assert "percentual" in (resultado.motivo_nao_comparavel or "")


def test_comparacao_periodos_diferentes():
    """Periodos diferentes = nao comparavel."""
    valores = [
        DadoNumericoNormalizado(indicador="IPCA", valor=4.5, unidade="%", periodo="12 meses",
                                fonte_id="f1", fonte_nome="IBGE", trecho="IPCA 4,5%"),
        DadoNumericoNormalizado(indicador="IPCA", valor=4.5, unidade="%", periodo="mensal",
                                fonte_id="f2", fonte_nome="BCB", trecho="IPCA mensal 4,5%"),
    ]
    resultado = comparar_valores_numericos(valores, None, {})
    assert resultado.status == StatusLinhaMatriz.NAO_COMPARAVEL
    assert "periodos diferentes" in (resultado.motivo_nao_comparavel or "")


def test_comparacao_indicador_nao_normalizado():
    """Indicador nao normalizado so entra se coincidencia exata."""
    valores = [
        DadoNumericoNormalizado(indicador="FooBar", valor=100.0, unidade="unidade", periodo="atual",
                                fonte_id="f1", fonte_nome="A", trecho="FooBar 100", normalizado=False),
        DadoNumericoNormalizado(indicador="FooBar", valor=100.0, unidade="unidade", periodo="atual",
                                fonte_id="f2", fonte_nome="B", trecho="FooBar 100", normalizado=False),
    ]
    resultado = comparar_valores_numericos(valores, None, {})
    assert resultado.status == StatusLinhaMatriz.CONVERGENCIA


def test_comparacao_somente_um_valor():
    """Apenas um valor = sem contraponto."""
    valores = [
        DadoNumericoNormalizado(indicador="Selic", valor=10.50, unidade="% a.a.", periodo="atual",
                                fonte_id="f1", fonte_nome="BCB", trecho="Selic 10,50%"),
    ]
    resultado = comparar_valores_numericos(valores, None, {})
    assert resultado.status == StatusLinhaMatriz.SEM_CONTRA_PONTO


def test_agrupar_por_indicador_unidade_periodo():
    """Agrupamento correto por indicador, unidade e periodo."""
    valores = [
        DadoNumericoNormalizado(indicador="Selic", valor=10.5, unidade="% a.a.", periodo="atual",
                                fonte_id="f1", fonte_nome="A", trecho="a"),
        DadoNumericoNormalizado(indicador="Selic", valor=11.0, unidade="% a.a.", periodo="atual",
                                fonte_id="f2", fonte_nome="B", trecho="b"),
        DadoNumericoNormalizado(indicador="IPCA", valor=4.5, unidade="%", periodo="12 meses",
                                fonte_id="f3", fonte_nome="C", trecho="c"),
    ]
    grupos = agrupar_por_indicador_unidade_periodo(valores)
    assert len(grupos) == 2
    assert len(grupos[("Selic", "% a.a.", "atual")]) == 2
    assert len(grupos[("IPCA", "%", "12 meses")]) == 1


# ============================================================================
# Origem comum
# ============================================================================

def test_detectar_origem_mesmo_comunicado():
    """Duas noticias do mesmo comunicado = mesma origem."""
    fontes = [
        {"id": "f1", "nome": "BCB", "tipo_fonte": "primaria", "url": "https://bcb.gov.br/ata-copom",
         "titulo": "Ata do Copom nº 200", "descricao": "Copom mantem Selic em 10,50%"},
        {"id": "f2", "nome": "Valor", "tipo_fonte": "secundaria", "url": "https://valor.com.br/copom",
         "titulo": "Ata do Copom nº 200", "descricao": "Copom mantem Selic em 10,50% por unanimidade"},
    ]
    grupos = detectar_origem_comum(fontes, limiar_sobreposicao=0.6)
    assert len(grupos) == 1
    assert grupos[0].fonte_ids == ["f1", "f2"]


def test_detectar_origem_fontes_independentes():
    """Duas fontes independentes = grupos separados."""
    fontes = [
        {"id": "f1", "nome": "BCB", "tipo_fonte": "primaria", "url": "https://bcb.gov.br/ata",
         "titulo": "Ata Copom", "descricao": "Selic em 10,50%"},
        {"id": "f2", "nome": "IBGE", "tipo_fonte": "primaria", "url": "https://ibge.gov.br/ipca",
         "titulo": "IPCA mensal", "descricao": "Inflacao em 4,5%"},
    ]
    grupos = detectar_origem_comum(fontes, limiar_sobreposicao=0.6)
    assert len(grupos) == 0


def test_fontes_independentes_contagem():
    """Contagem de fontes independentes."""
    fontes = [
        {"id": "f1", "nome": "BCB", "tipo_fonte": "primaria"},
        {"id": "f2", "nome": "Valor", "tipo_fonte": "secundaria"},
        {"id": "f3", "nome": "Folha", "tipo_fonte": "secundaria"},
    ]
    grupos = [
        # f1 e f2 sao mesma origem
    ]
    from src.triangulacao.origem_comum import OrigemComum
    grupos_obj = [OrigemComum(origem_comum_id="o1", fonte_ids=["f1", "f2"], motivo="mesmo link")]
    independentes = fontes_independentes(fontes, grupos_obj)
    assert len(independentes) == 1
    assert independentes[0]["id"] == "f3"


def test_mesmo_identificador():
    """Detecao de mesmo identificador."""
    assert mesmo_identificador("Ata Copom nº 200", "Copom nº 200 mantem juros") is True
    assert mesmo_identificador("IPCA outubro", "Selic novembro") is False


def test_sobreposicao_literal():
    """Sobreposicao literal de trechos."""
    texto_a = "O Banco Central decidiu manter a taxa Selic em 10,50% ao ano"
    texto_b = "O Banco Central decidiu manter a taxa Selic em 10,50% ao ano por unanimidade"
    assert sobreposicao_literal(texto_a, texto_b, 0.6) is True

    texto_c = "Inflacao sobe no Brasil"
    texto_d = "O mercado de acoes fecha em alta"
    assert sobreposicao_literal(texto_c, texto_d, 0.6) is False


def test_extrair_dominio():
    """Extracao de dominio de URL."""
    assert extrair_dominio("https://www.bcb.gov.br/ata") == "www.bcb.gov.br"
    assert extrair_dominio("http://ibge.gov.br/ipca") == "ibge.gov.br"
    assert extrair_dominio("") == ""


# ============================================================================
# Sugestao de conjunto
# ============================================================================

def test_avaliar_conjunto_valido():
    """Conjunto valido para triangulacao."""
    fontes = [{"id": f"f{i}"} for i in range(3)]
    resultado = avaliar_conjunto(fontes, {})
    assert resultado["valido"] is True
    assert resultado["pode_triangular"] is True


def test_avaliar_conjunto_pouco_fontes():
    """Menos de 2 fontes = invalido."""
    fontes = [{"id": "f1"}]
    resultado = avaliar_conjunto(fontes, {})
    assert resultado["valido"] is False
    assert resultado["pode_triangular"] is False


def test_avaliar_conjunto_muitas_fontes():
        """Mais de 5 fontes = invalido."""
        fontes = [{"id": f"f{i}"} for i in range(6)]
        resultado = avaliar_conjunto(fontes, {})
        assert resultado["valido"] is False
        assert resultado["pode_triangular"] is False


def test_similaridade_lexica_simples():
    """Similaridade lexical entre textos."""
    s1 = similaridade_lexica_simples("O Copom decidiu manter a Selic", "O Copom manteve a taxa Selic")
    assert 0.0 < s1 <= 1.0
    s2 = similaridade_lexica_simples("O Copom decidiu", "Inflacao no Brasil sobe")
    assert s2 == 0.0  # nenhuma palavra em comum


def test_proximidade_datas():
    """Proximidade entre datas."""
    from datetime import datetime
    hoje = datetime.now().strftime("%Y-%m-%d")
    assert proximidade_datas(hoje, hoje, 3) == 1.0
    assert proximidade_datas("2026-01-01", "2026-01-05", 3) == 0.0  # fora da janela


def test_pontuacao_candidato():
    """Pontuacao de candidato para triangulacao."""
    fonte = {"id": "f1", "nome": "BCB", "titulo": "Copom mantem Selic", "descricao": "Selic em 10,50%"}
    referencia = {"id": "f2", "nome": "Valor", "titulo": "Copom mantem taxa", "descricao": "Selic em 10,50% por unanimidade"}
    apelidos = {"copom": ["copom", "comite"], "selic": ["selic", "taxa"]}
    resultado = pontuacao_candidato(fonte, [referencia], apelidos, {})
    assert "score" in resultado
    assert "motivos" in resultado
    assert 0.0 <= resultado["score"] <= 1.0


def test_sugerir_candidatos():
    """Sugestao de candidatos."""
    fonte_ref = {"id": "f1", "nome": "BCB", "titulo": "Copom mantem Selic"}
    pool = [
        {"id": "f2", "nome": "Valor", "titulo": "Copom mantem taxa Selic"},
        {"id": "f3", "nome": "Folha", "titulo": "Inflacao sobe no Brasil"},
    ]
    sugestoes = sugerir_candidatos(fonte_ref, pool, {}, {}, maximo_sugestoes=5)
    assert len(sugestoes) <= 5
    if sugestoes:
        assert "score" in sugestoes[0]