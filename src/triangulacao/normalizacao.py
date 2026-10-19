"""Normalizacao de indicadores numericos para comparacao entre fontes."""
from __future__ import annotations

import re
from typing import Any
from pathlib import Path
import yaml

from src.triangulacao.models import DadoNumericoNormalizado, ComparacaoNumerica, StatusLinhaMatriz


def load_indicadores(path: str = "config/indicadores.yaml") -> dict[str, Any]:
    """Carrega configuracao de indicadores."""
    file_path = Path(path)
    if not file_path.exists():
        return {"indicadores": [], "escalas": {"unidade": 1, "mil": 1000, "milhao": 1000000, "bilhao": 1000000000}}
    with file_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_triangulacao(path: str = "config/triangulacao.yaml") -> dict[str, Any]:
    """Carrega configuracao de triangulacao."""
    file_path = Path(path)
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def normalizar_numero(valor_texto: str) -> float | None:
    """Converte texto para numero float, removendo simbolos monetarios e espacos."""
    if not valor_texto:
        return None
    limpo = valor_texto.strip()
    # Remove simbolos monetarios e espacos
    limpo = re.sub(r"[R$\s\xa0]", "", limpo)
    # Remove simbolo de percentual (será recolocado se necessário, mas o valor numerico é o mesmo)
    tem_percentual = "%" in limpo
    limpo = limpo.replace("%", "")
    # Estrategia para formato brasileiro:
    # Se tem virgula: ponto eh separador de milhar, virgula eh decimal
    # Ex: 1.234,56 -> 1234.56
    if "," in limpo:
        partes = limpo.split(",")
        if len(partes) == 2:
            inteiro = partes[0].replace(".", "")  # remove pontos de milhar
            decimal = partes[1]
            limpo = f"{inteiro}.{decimal}"
        else:
            # Mais de uma virgula, invalido
            return None
    else:
        # Sem virgula: ponto pode ser decimal (formato americano) ou invalido
        # Se tem ponto, tenta interpretar como decimal americano
        pass
    try:
        valor = float(limpo)
        return valor
    except ValueError:
        return None


def converter_escala(valor: float, escala_origem: str, escalas: dict[str, int]) -> float:
    """Converte um valor de uma escala para a escala canonica (unidade)."""
    multiplicador = escalas.get(escala_origem, 1)
    return valor * multiplicador


def encontrar_indicador(texto: str, indicadores_config: list[dict]) -> str | None:
    """Tenta encontrar qual indicador canônico corresponde ao texto."""
    texto_lower = texto.lower().strip()
    for ind in indicadores_config:
        nome = ind.get("nome", "").lower()
        apelidos = [a.lower() for a in ind.get("apelidos", [])]
        if texto_lower == nome or texto_lower in apelidos:
            return ind["nome"]
        # Verifica se o texto contém o nome ou algum apelido como palavra inteira
        for termo in [nome] + apelidos:
            if re.search(rf"\b{re.escape(termo)}\b", texto_lower):
                return ind["nome"]
    return None


def normalizar_dados_numericos(
    dados_brutos: list[dict[str, Any]],
    indicadores_config: list[dict],
    escalas: dict[str, int],
) -> list[DadoNumericoNormalizado]:
    """Normaliza uma lista de dados numericos brutos extraidos das fontes."""
    normalizados: list[DadoNumericoNormalizado] = []
    for dado in dados_brutos:
        indicador_texto = dado.get("indicador", "")
        valor_texto = dado.get("valor", "")
        unidade = dado.get("unidade", "")
        periodo = dado.get("reference_period", "") or dado.get("periodo", "")
        fonte_id = dado.get("fonte_id", "")
        fonte_nome = dado.get("fonte_nome", "")
        trecho = dado.get("trecho", "")

        # Tenta encontrar o indicador canonico
        indicador_canonico = encontrar_indicador(indicador_texto, indicadores_config)
        if not indicador_canonico:
            # Indicador nao normalizado - so entra se houver coincidencia exata de texto, unidade e periodo
            normalizados.append(
                DadoNumericoNormalizado(
                    indicador=indicador_texto,
                    valor=normalizar_numero(valor_texto) or 0.0,
                    unidade=unidade,
                    periodo=periodo,
                    fonte_id=fonte_id,
                    fonte_nome=fonte_nome,
                    trecho=trecho,
                    escala="unidade",
                    normalizado=False,
                )
            )
            continue

        # Pega configuracao do indicador
        ind_config = next((i for i in indicadores_config if i.get("nome") == indicador_canonico), {})
        escala_texto = dado.get("escala", ind_config.get("escala", "unidade"))

        valor_num = normalizar_numero(valor_texto)
        if valor_num is None:
            continue

        valor_convertido = converter_escala(valor_num, escala_texto, escalas)
        unidade_canonica = ind_config.get("unidade_canonica", unidade)

        normalizados.append(
            DadoNumericoNormalizado(
                indicador=indicador_canonico,
                valor=valor_convertido,
                unidade=unidade_canonica,
                periodo=periodo,
                fonte_id=fonte_id,
                fonte_nome=fonte_nome,
                trecho=trecho,
                escala=escala_texto,
                normalizado=True,
            )
        )
    return normalizados


def comparar_valores_numericos(
    valores: list[DadoNumericoNormalizado],
    indicador_config: dict | None,
    config_triangulacao: dict | None,
) -> ComparacaoNumerica:
    """Compara valores numericos de forma deterministica."""
    if not valores:
        return ComparacaoNumerica(
            indicador="",
            unidade="",
            periodo="",
            status=StatusLinhaMatriz.NAO_COMPARAVEL,
            motivo_nao_comparavel="sem valores",
        )

    # Agrupa por indicador, unidade e periodo
    grupos: dict[tuple[str, str, str], list[DadoNumericoNormalizado]] = {}
    for v in valores:
        chave = (v.indicador, v.unidade, v.periodo)
        grupos.setdefault(chave, []).append(v)

    # Se so um grupo com valores, comparar dentro dele
    resultado = ComparacaoNumerica(
        indicador=valores[0].indicador,
        unidade=valores[0].unidade,
        periodo=valores[0].periodo,
        valores=valores,
    )

    # Verifica se ha mais de um grupo com mesma indicador mas unidades/periodos diferentes
    # -> nao comparavel
    indicadores_distintos = set(v.indicador for v in valores)
    unidades_distintas = set(v.unidade for v in valores)
    periodos_distintos = set(v.periodo for v in valores)

    if len(unidades_distintas) > 1:
        # Verifica se é percentual vs ponto percentual
        unidades_lower = {u.lower() for u in unidades_distintas}
        if {"percentual", "ponto percentual"} & unidades_lower and len(unidades_lower) == 2:
            resultado.status = StatusLinhaMatriz.NAO_COMPARAVEL
            resultado.motivo_nao_comparavel = "unidades incompatíveis: percentual versus ponto percentual"
            return resultado
        resultado.status = StatusLinhaMatriz.NAO_COMPARAVEL
        resultado.motivo_nao_comparavel = f"unidades diferentes: {', '.join(sorted(unidades_distintas))}"
        return resultado

    if len(periodos_distintos) > 1:
        resultado.status = StatusLinhaMatriz.NAO_COMPARAVEL
        resultado.motivo_nao_comparavel = f"periodos diferentes: {', '.join(sorted(periodos_distintos))}"
        return resultado

    # So um grupo - comparar valores
    grupo_valores = list(grupos.values())[0]
    if len(grupo_valores) < 2:
        resultado.status = StatusLinhaMatriz.SEM_CONTRA_PONTO
        return resultado

    # Pega tolerancia
    tolerancia_absoluta = 0.5
    tolerancia_relativa = 0.02
    if indicador_config:
        tolerancia_absoluta = indicador_config.get("tolerancia_absoluta", tolerancia_absoluta)
        tolerancia_relativa = indicador_config.get("tolerancia_relativa", tolerancia_relativa)
    elif config_triangulacao:
        cn = config_triangulacao.get("comparacao_numerica", {})
        tolerancia_absoluta = cn.get("tolerancia_absoluta_default", 0.5)
        tolerancia_relativa = cn.get("tolerancia_relativa_default", 0.02)

    vals = [v.valor for v in grupo_valores]
    vmin, vmax = min(vals), max(vals)
    diferenca_absoluta = vmax - vmin
    diferenca_relativa = diferenca_absoluta / abs(vmin) if vmin != 0 else (1.0 if diferenca_absoluta > 0 else 0.0)

    resultado.diferenca_absoluta = round(diferenca_absoluta, 4)
    resultado.diferenca_relativa = round(diferenca_relativa, 4)
    resultado.tolerancia_usada = {
        "absoluta": tolerancia_absoluta,
        "relativa": tolerancia_relativa,
    }

    if diferenca_absoluta <= tolerancia_absoluta and diferenca_relativa <= tolerancia_relativa:
        resultado.status = StatusLinhaMatriz.CONVERGENCIA
    else:
        resultado.status = StatusLinhaMatriz.DIVERGENCIA_NUMERICA

    return resultado


def agrupar_por_indicador_unidade_periodo(
    normalizados: list[DadoNumericoNormalizado],
) -> dict[tuple[str, str, str], list[DadoNumericoNormalizado]]:
    """Agrupa dados normalizados por (indicador, unidade, periodo)."""
    grupos: dict[tuple[str, str, str], list[DadoNumericoNormalizado]] = {}
    for v in normalizados:
        chave = (v.indicador, v.unidade, v.periodo)
        grupos.setdefault(chave, []).append(v)
    return grupos