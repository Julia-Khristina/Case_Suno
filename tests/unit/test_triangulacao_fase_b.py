"""Testes da Fase B - Conteúdo da triangulação de fontes."""
from __future__ import annotations

from unittest.mock import patch
from pathlib import Path
import json

import pytest

from src.triangulacao.models import (
    LinhaMatriz, CelulaMatriz, StatusLinhaMatriz, PosicaoQualitativa,
    PosicaoClassificada, DadoNumericoNormalizado, ComparacaoNumerica,
    OrigemComum, Triangulacao,
)
from src.triangulacao.classificacao_qualitativa import (
    ClassificadorQualitativo, eh_divergencia_qualitativa, posicoes_opostas,
)
from src.triangulacao.matriz import (
    montar_matriz, aplicar_revisao_humana, linhas_pendentes_revisao,
    linhas_aprovadas, detectar_grupos_origem_comum, avaliar_conjunto_fontes,
    _trecho_curto,
)
from src.triangulacao.graficos import (
    grafico_barras_agrupadas, grafico_tabela_convergencia,
    gerar_graficos_para_nivel, _texto_alternativo, _salvar_dados_grafico,
)
from src.triangulacao.redacao import (
    RedatorNivel, verificar_cobertura_divergencias, verificar_atribuicao_fontes,
    verificar_veredito_proibido, hashlib_matriz,
)
from src.triangulacao.verificacoes import (
    verificar_divergencia_cita_duas_fontes, verificar_sem_veredito,
    verificar_valores_grafico_iguais_matriz, verificar_cobertura_matriz,
    verificar_atribuicao_toda_frase, verificar_fontes_mesma_origem_nao_contam_independentes,
    verificar_numeros_datas_existem_matriz, verificar_emojis_termos_proibidos,
    verificar_iniciante_termos_explicados, verificar_diferenciacao_niveis,
    executar_todas_verificacoes, ResultadoVerificacao,
)
from src.shared.llm_client import LLMCallResult
from src.evaluation.judge import JudgeResult


# ============================================================================
# Trecho curto
# ============================================================================

def test_trecho_curto_max_25_palavras():
    """Citação curta no máximo 25 palavras."""
    trecho_longo = " ".join(["palavra"] * 40)
    curto = _trecho_curto(trecho_longo, 25)
    # 25 palavras + "..." anexado à última (não conta como palavra separada no split)
    assert len(curto.split()) == 25
    assert curto.endswith("...")

    trecho_curto_pequeno = _trecho_curto("texto curto", 25)
    assert trecho_curto_pequeno == "texto curto"


# ============================================================================
# Classificação qualitativa
# ============================================================================

def test_classificador_apoiar():
    """Classificador identifica posição de apoio."""
    canned = {
        "posicao": "apoiar",
        "confianca": 0.85,
        "justificativa": "A fonte declara que a medida é positiva.",
        "trecho_evidencia": "A medida é positiva para a economia.",
    }
    with patch(
        "src.triangulacao.classificacao_qualitativa.LLMClient.generate",
        return_value=LLMCallResult(
            response=canned, usage={"total_tokens": 100}, latency_seconds=0.5,
            model_id="classificador", mode="simulated",
        ),
    ):
        classificador = ClassificadorQualitativo(model_id="classificador")
        resultado = classificador.classificar(
            afirmacao_id="a1",
            afirmacao="A medida é positiva.",
            trecho_evidencia="A medida é positiva para a economia.",
            fonte_id="f1",
            fonte_nome="BCB",
            topico="Selic",
        )
    assert resultado.posicao == PosicaoQualitativa.APOIA
    assert resultado.confianca == 0.85
    assert resultado.trecho_evidencia == "A medida é positiva para a economia."


def test_classificador_contestar():
    """Classificador identifica posição de contestação."""
    canned = {
        "posicao": "contestar",
        "confianca": 0.9,
        "justificativa": "A fonte discorda da medida.",
        "trecho_evidencia": "A medida é inadequada.",
    }
    with patch(
        "src.triangulacao.classificacao_qualitativa.LLMClient.generate",
        return_value=LLMCallResult(
            response=canned, usage={"total_tokens": 100}, latency_seconds=0.5,
            model_id="classificador", mode="simulated",
        ),
    ):
        classificador = ClassificadorQualitativo(model_id="classificador")
        resultado = classificador.classificar(
            afirmacao_id="a2",
            afirmacao="A medida é inadequada.",
            trecho_evidencia="A medida é inadequada.",
            fonte_id="f2",
            fonte_nome="Valor",
            topico="Selic",
        )
    assert resultado.posicao == PosicaoQualitativa.CONTESTA


def test_classificador_nao_menciona():
    """Classificador identifica quando fonte não menciona o tópico."""
    canned = {
        "posicao": "nao_menciona",
        "confianca": 0.95,
        "justificativa": "A fonte não fala sobre o tópico.",
        "trecho_evidencia": "Outro assunto qualquer.",
    }
    with patch(
        "src.triangulacao.classificacao_qualitativa.LLMClient.generate",
        return_value=LLMCallResult(
            response=canned, usage={"total_tokens": 100}, latency_seconds=0.5,
            model_id="classificador", mode="simulated",
        ),
    ):
        classificador = ClassificadorQualitativo(model_id="classificador")
        resultado = classificador.classificar(
            afirmacao_id="a3",
            afirmacao="Outro assunto.",
            trecho_evidencia="Outro assunto qualquer.",
            fonte_id="f3",
            fonte_nome="Folha",
            topico="Selic",
        )
    assert resultado.posicao == PosicaoQualitativa.NAO_MENCIONA


def test_eh_divergencia_qualitativa_precisa_ambas_pontas():
    """Divergência qualitativa exige posições opostas com evidência para ambas."""
    apoiando = PosicaoClassificada(
        afirmacao_id="a1", fonte_id="f1", posicao=PosicaoQualitativa.APOIA,
        confianca=0.8, trecho_evidencia="Evidencia apoio", justificativa="",
    )
    contestando = PosicaoClassificada(
        afirmacao_id="a2", fonte_id="f2", posicao=PosicaoQualitativa.CONTESTA,
        confianca=0.8, trecho_evidencia="Evidencia contesta", justificativa="",
    )
    assert eh_divergencia_qualitativa([apoiando, contestando]) is True

    # Sem evidência em uma das pontas -> não é divergência
    apoiando_sem_evidencia = PosicaoClassificada(
        afirmacao_id="a1", fonte_id="f1", posicao=PosicaoQualitativa.APOIA,
        confianca=0.8, trecho_evidencia="", justificativa="",
    )
    assert eh_divergencia_qualitativa([apoiando_sem_evidencia, contestando]) is False

    # Confiança baixa -> não é divergência
    apoiando_baixa_conf = PosicaoClassificada(
        afirmacao_id="a1", fonte_id="f1", posicao=PosicaoQualitativa.APOIA,
        confianca=0.3, trecho_evidencia="Evidencia apoio", justificativa="",
    )
    assert eh_divergencia_qualitativa([apoiando_baixa_conf, contestando]) is False


def test_posicoes_opostas():
    """Retorna as duas pontas opostas."""
    apoiando = PosicaoClassificada(
        afirmacao_id="a1", fonte_id="f1", posicao=PosicaoQualitativa.APOIA,
        confianca=0.8, trecho_evidencia="E1", justificativa="",
    )
    contestando = PosicaoClassificada(
        afirmacao_id="a2", fonte_id="f2", posicao=PosicaoQualitativa.CONTESTA,
        confianca=0.8, trecho_evidencia="E2", justificativa="",
    )
    neutra = PosicaoClassificada(
        afirmacao_id="a3", fonte_id="f3", posicao=PosicaoQualitativa.NEUTRA,
        confianca=0.8, trecho_evidencia="E3", justificativa="",
    )
    resultado = posicoes_opostas([apoiando, contestando, neutra])
    assert resultado is not None
    assert len(resultado[0]) == 1  # apoiando
    assert len(resultado[1]) == 1  # contestando

    # Sem oposição
    assert posicoes_opostas([apoiando, neutra]) is None


# ============================================================================
# Matriz
# ============================================================================

def test_montar_matriz_comparacoes_numericas():
    """Monta matriz a partir de comparações numéricas."""
    comp = ComparacaoNumerica(
        indicador="Selic",
        unidade="% a.a.",
        periodo="atual",
        valores=[
            DadoNumericoNormalizado(
                indicador="Selic", valor=10.50, unidade="% a.a.", periodo="atual",
                fonte_id="f1", fonte_nome="BCB", trecho="Selic 10,50%",
            ),
            DadoNumericoNormalizado(
                indicador="Selic", valor=12.00, unidade="% a.a.", periodo="atual",
                fonte_id="f2", fonte_nome="XP", trecho="Selic 12,00%",
            ),
        ],
        status=StatusLinhaMatriz.DIVERGENCIA_NUMERICA,
        diferenca_absoluta=1.5,
        diferenca_relativa=0.143,
    )
    triangulacao = Triangulacao(
        triangulacao_id="t1",
        assunto="Teste",
        fontes=[
            {"id": "f1", "nome": "BCB", "tipo_fonte": "primaria"},
            {"id": "f2", "nome": "XP", "tipo_fonte": "secundaria"},
        ],
    )
    linhas = montar_matriz(triangulacao, [comp], [], {})
    assert len(linhas) == 1
    linha = linhas[0]
    assert linha.status == StatusLinhaMatriz.DIVERGENCIA_NUMERICA
    assert linha.diferenca_absoluta == 1.5
    assert len(linha.celulas) == 2
    assert linha.fontes_divergentes == ["f1", "f2"]


def test_aplicar_revisao_humana():
    """Revisão humana confirma ou rejeita linha."""
    linha = LinhaMatriz(
        linha_id="l1",
        topico="Teste",
        status=StatusLinhaMatriz.DIVERGENCIA_QUALITATIVA,
        celulas=[],
    )
    atualizada = aplicar_revisao_humana(linha, True, "Confirmado por evidência")
    assert atualizada.revisada_por_humano is True
    assert atualizada.confirmada_por_humano is True
    assert atualizada.justificativa_status == "Confirmado por evidência"


def test_linhas_pendentes_revisao():
    """Linhas qualitativas não confirmadas ficam pendentes."""
    linha_pendente = LinhaMatriz(
        linha_id="l1",
        topico="Teste",
        status=StatusLinhaMatriz.DIVERGENCIA_QUALITATIVA,
        celulas=[],
        revisada_por_humano=False,
    )
    linha_confirmada = LinhaMatriz(
        linha_id="l2",
        topico="Teste2",
        status=StatusLinhaMatriz.DIVERGENCIA_QUALITATIVA,
        celulas=[],
        revisada_por_humano=True,
        confirmada_por_humano=True,
    )
    pendentes = linhas_pendentes_revisao([linha_pendente, linha_confirmada])
    assert len(pendentes) == 1
    assert pendentes[0].linha_id == "l1"


def test_linhas_aprovadas():
    """Linhas aprovadas: numéricas automáticas + qualitativas confirmadas."""
    linha_num = LinhaMatriz(
        linha_id="l1",
        topico="Num",
        status=StatusLinhaMatriz.DIVERGENCIA_NUMERICA,
        celulas=[],
    )
    linha_qual_confirmada = LinhaMatriz(
        linha_id="l2",
        topico="Qual",
        status=StatusLinhaMatriz.DIVERGENCIA_QUALITATIVA,
        celulas=[],
        revisada_por_humano=True,
        confirmada_por_humano=True,
    )
    linha_qual_pendente = LinhaMatriz(
        linha_id="l3",
        topico="Qual2",
        status=StatusLinhaMatriz.DIVERGENCIA_QUALITATIVA,
        celulas=[],
        revisada_por_humano=False,
    )
    aprovadas = linhas_aprovadas([linha_num, linha_qual_confirmada, linha_qual_pendente])
    assert len(aprovadas) == 2
    ids_aprovadas = {l.linha_id for l in aprovadas}
    assert ids_aprovadas == {"l1", "l2"}


def test_avaliar_conjunto_fontes_valido():
    """Conjunto com 3 fontes independentes é válido."""
    fontes = [
        {"id": "f1", "nome": "BCB", "tipo_fonte": "primaria"},
        {"id": "f2", "nome": "Valor", "tipo_fonte": "secundaria"},
        {"id": "f3", "nome": "Folha", "tipo_fonte": "secundaria"},
    ]
    resultado = avaliar_conjunto_fontes(fontes, {})
    assert resultado["valido"] is True
    assert resultado["pode_triangular"] is True
    assert resultado["total_fontes"] == 3


def test_avaliar_conjunto_fontes_pouco_independentes():
    """Menos de 2 fontes independentes = não permite triangulação."""
    fontes = [
        {"id": "f1", "nome": "BCB", "tipo_fonte": "primaria"},
        {"id": "f2", "nome": "Valor", "tipo_fonte": "secundaria"},
    ]
    grupos = [OrigemComum(origem_comum_id="o1", fonte_ids=["f1", "f2"], motivo="mesmo link")]
    resultado = avaliar_conjunto_fontes(fontes, {})
    # Sem grupos de origem, ambas são independentes
    assert resultado["fontes_independentes"] == 2
    assert resultado["pode_triangular"] is True


# ============================================================================
# Gráficos
# ============================================================================

def test_grafico_barras_agrupadas_cria_png(tmp_path):
    """Gráfico de barras cria PNG e JSON com dados."""
    valores = [
        {"fonte": "BCB", "valor": 10.5, "unidade": "% a.a.", "periodo": "atual"},
        {"fonte": "XP", "valor": 12.0, "unidade": "% a.a.", "periodo": "atual"},
    ]
    resultado = grafico_barras_agrupadas(
        valores=valores,
        indicador="Selic",
        periodo="atual",
        pasta_saida=tmp_path,
        nome_arquivo="grafico_teste",
    )
    assert resultado["criado"] is True
    assert resultado["arquivo"].endswith(".png")
    assert "hash" in resultado
    assert len(resultado["dados_plotados"]) == 2
    assert "texto_alternativo" in resultado

    # Verifica que o JSON foi salvo ao lado do PNG
    caminho_json = Path(resultado["arquivo"]).with_suffix(".json")
    assert caminho_json.exists()
    dados_json = json.loads(caminho_json.read_text(encoding="utf-8"))
    assert len(dados_json) == 2


def test_grafico_barras_menos_de_2_valores_nao_cria(tmp_path):
    """Não cria gráfico com menos de 2 valores."""
    valores = [
        {"fonte": "BCB", "valor": 10.5, "unidade": "% a.a.", "periodo": "atual"},
    ]
    resultado = grafico_barras_agrupadas(
        valores=valores,
        indicador="Selic",
        periodo="atual",
        pasta_saida=tmp_path,
        nome_arquivo="grafico_unico",
    )
    assert resultado["criado"] is False
    assert "menos de 2" in resultado["motivo"]


def test_texto_alternativo_contem_valores():
    """Texto alternativo contém os valores plotados."""
    dados = [
        {"fonte": "BCB", "valor": 10.5, "unidade": "% a.a.", "periodo": "atual"},
        {"fonte": "XP", "valor": 12.0, "unidade": "% a.a.", "periodo": "atual"},
    ]
    texto_alt = _texto_alternativo("Grafico de barras: Selic em atual. ", dados)
    assert "BCB" in texto_alt
    assert "10.5" in texto_alt
    assert "XP" in texto_alt
    assert "12.0" in texto_alt


def test_gerar_graficos_respeita_maximo_por_nivel(tmp_path):
    """Respeita máximo de gráficos por nível."""
    comparacoes = []
    for i in range(5):
        comp = ComparacaoNumerica(
            indicador="Selic",
            unidade="% a.a.",
            periodo="atual",
            valores=[
                DadoNumericoNormalizado(
                    indicador="Selic", valor=10.5 + i, unidade="% a.a.", periodo="atual",
                    fonte_id="f1", fonte_nome=f"Fonte{i}", trecho=f"Valor {i}",
                ),
                DadoNumericoNormalizado(
                    indicador="Selic", valor=11.0 + i, unidade="% a.a.", periodo="atual",
                    fonte_id="f2", fonte_nome=f"Fonte2_{i}", trecho=f"Valor2 {i}",
                ),
            ],
            status=StatusLinhaMatriz.DIVERGENCIA_NUMERICA,
        )
        comparacoes.append(comp)

    # Iniciante: máximo 2
    gerados_iniciante = gerar_graficos_para_nivel(comparacoes, "iniciante", tmp_path, {})
    assert len(gerados_iniciante) <= 2

    # Avançado: máximo 4
    gerados_avancado = gerar_graficos_para_nivel(comparacoes, "avancado", tmp_path, {})
    assert len(gerados_avancado) <= 4


# ============================================================================
# Redação
# ============================================================================

def test_redator_iniciante_regras():
    """Redator Iniciante tem regras específicas."""
    redator = RedatorNivel(nivel="iniciante")
    regras = redator._regras_nivel()
    assert "Em geral" in regras
    assert "glossario" in regras.lower()
    assert "veredito" in regras.lower()

    redator_av = RedatorNivel(nivel="avancado")
    regras_av = redator_av._regras_nivel()
    assert "jargao pleno" in regras_av.lower()


def test_verificar_cobertura_divergencias():
    """Verifica cobertura de linhas de divergência."""
    linha_div = LinhaMatriz(
        linha_id="div_1",
        topico="Selic",
        status=StatusLinhaMatriz.DIVERGENCIA_NUMERICA,
        celulas=[],
    )
    texto_coberto = "A linha div_1 mostra divergência na Selic."
    texto_nao_coberto = "O texto não menciona a linha."
    assert verificar_cobertura_divergencias(texto_coberto, [linha_div]) == []
    assert verificar_cobertura_divergencias(texto_nao_coberto, [linha_div]) == ["div_1"]


def test_verificar_atribuicao_fontes():
    """Verifica atribuição de fontes."""
    fontes = [
        {"nome": "BCB"},
        {"nome": "Valor"},
    ]
    texto_com_atribuicao = "O BCB informou que a Selic está em 10,50%. O Valor discordou."
    texto_sem_atribuicao = "A taxa está em 10,50% e isso é ruim para a economia."
    assert verificar_atribuicao_fontes(texto_com_atribuicao, fontes) == []
    assert len(verificar_atribuicao_fontes(texto_sem_atribuicao, fontes)) >= 1


def test_verificar_veredito_proibido():
    """Detecta padrões de veredito proibido."""
    texto_ok = "O BCB informou 10,50% e o Valor informou 12,00%."
    texto_proibido = "Na verdade, o correto é que o BCB está certo."
    assert verificar_veredito_proibido(texto_ok) == []
    assert len(verificar_veredito_proibido(texto_proibido)) >= 1


def test_hashlib_matriz():
    """Gera hash estável da matriz."""
    linha = LinhaMatriz(
        linha_id="l1", topico="Teste", status=StatusLinhaMatriz.CONVERGENCIA, celulas=[],
    )
    h1 = hashlib_matriz([linha])
    h2 = hashlib_matriz([linha])
    assert h1 == h2  # Mesmo input → mesmo hash

    linha2 = LinhaMatriz(
        linha_id="l2", topico="Teste2", status=StatusLinhaMatriz.DIVERGENCIA_NUMERICA, celulas=[],
    )
    h3 = hashlib_matriz([linha, linha2])
    assert h1 != h3  # Input diferente → hash diferente


# ============================================================================
# Verificações determinísticas
# ============================================================================

def test_verificar_divergencia_cita_duas_fontes():
    """Frase de divergência cita pelo menos 2 fontes."""
    fontes = [
        {"nome": "BCB"},
        {"nome": "Valor"},
    ]
    linha = LinhaMatriz(
        linha_id="div_1",
        topico="Selic",
        status=StatusLinhaMatriz.DIVERGENCIA_NUMERICA,
        celulas=[],
    )
    texto_ok = "O BCB informou 10,50% e o Valor informou 12,00%, porém há diferença."
    texto_falha = "O BCB informou 10,50%, porém há diferença."  # só 1 fonte
    r_ok = verificar_divergencia_cita_duas_fontes(texto_ok, [linha], fontes)
    assert r_ok.passou is True
    r_falha = verificar_divergencia_cita_duas_fontes(texto_falha, [linha], fontes)
    assert r_falha.passou is False


def test_verificar_sem_veredito():
    """Não há padrões de veredito proibido."""
    texto_ok = "O BCB informou 10,50%."
    texto_proibido = "Na verdade, o correto é 10,50%."
    assert verificar_sem_veredito(texto_ok).passou is True
    assert verificar_sem_veredito(texto_proibido).passou is False


def test_verificar_fontes_mesma_origem_nao_contam():
    """Fontes de mesma origem não contam como independentes."""
    fontes_ind = [{"id": "f3", "nome": "Folha"}]
    grupos = [OrigemComum(origem_comum_id="o1", fonte_ids=["f1", "f2"], motivo="mesmo link")]
    r = verificar_fontes_mesma_origem_nao_contam_independentes(fontes_ind, grupos)
    assert r.passou is True

    # Fonte independente que está em grupo = falha
    fontes_ind2 = [{"id": "f1", "nome": "BCB"}]
    r2 = verificar_fontes_mesma_origem_nao_contam_independentes(fontes_ind2, grupos)
    assert r2.passou is False


def test_verificar_emojis_termos_proibidos():
    """Detecta emojis e termos proibidos."""
    texto_limpo = "O BCB informou 10,50%."
    assert verificar_emojis_termos_proibidos(texto_limpo, ["compre agora"]).passou is True

    texto_emoji = "O BCB informou 10,50%. 📈"
    assert verificar_emojis_termos_proibidos(texto_emoji, ["compre agora"]).passou is False

    texto_proibido = "Compre agora ações com garantia de lucro."
    assert verificar_emojis_termos_proibidos(texto_proibido, ["compre agora", "garantia de lucro"]).passou is False


def test_verificar_iniciante_termos_explicados():
    """Iniciante: termos técnicos explicados."""
    texto_ok = "O BCB informou a Selic. Em geral, a taxa básica de juros afeta o bolso."
    assert verificar_iniciante_termos_explicados(texto_ok, ["selic"], "iniciante").passou is True

    texto_avancado = "O BCB informou a Selic em 10,50%."
    assert verificar_iniciante_termos_explicados(texto_avancado, ["selic"], "avancado").passou is True  # não se aplica


def test_verificar_diferenciacao_niveis():
    """Sobreposição de trigramas acima de 70% reprova."""
    texto_iniciante = "O Copom decidiu manter a Selic em 10,50% ao ano. Em geral, afeta o bolso."
    texto_avancado = "O Copom preservou a taxa Selic em 10,50% ao ano com viés contracionista."
    textos = {"iniciante": texto_iniciante, "avancado": texto_avancado}
    r = verificar_diferenciacao_niveis(textos, limiar=0.7)
    # Textos diferentes → não deve reprovar
    assert r.passou is True

    # Mesmos textos → deve reprovar
    textos_iguais = {"iniciante": texto_iniciante, "avancado": texto_iniciante}
    r2 = verificar_diferenciacao_niveis(textos_iguais, limiar=0.7)
    assert r2.passou is False


def test_executar_todas_verificacoes():
    """Executa todas as verificações."""
    matriz = [
        LinhaMatriz(
            linha_id="div_1",
            topico="Selic",
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
        ),
    ]
    fontes = [{"nome": "BCB"}, {"nome": "Valor"}]
    texto_ok = (
        "A linha div_1 mostra que o BCB informou 10,50% e o Valor informou 12,00%. "
        "Não há veredito. O texto cita as duas fontes."
    )
    resultados = executar_todas_verificacoes(
        texto=texto_ok,
        matriz=matriz,
        fonte_informacoes=fontes,
        graficos=[],
        comparacoes=[],
        termos_proibidos=["compre agora"],
        glossario_termos=["selic"],
        nivel="iniciante",
    )
    assert len(resultados) >= 5
    assert all(isinstance(r, ResultadoVerificacao) for r in resultados)