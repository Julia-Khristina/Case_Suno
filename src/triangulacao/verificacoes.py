"""Verificacoes determinísticas novas para triangulacao."""
from __future__ import annotations

from typing import Any
import re

from src.triangulacao.models import LinhaMatriz, StatusLinhaMatriz


class ResultadoVerificacao:
    """Resultado de uma verificacao determinística."""
    def __init__(self, nome: str, passou: bool, detalhe: str = "", evidencia: list[str] | None = None):
        self.nome = nome
        self.passou = passou
        self.detalhe = detalhe
        self.evidencia = evidencia or []


def verificar_divergencia_cita_duas_fontes(
    texto: str,
    linhas_divergencia: list[LinhaMatriz],
    fonte_informacoes: list[dict[str, Any]],
) -> ResultadoVerificacao:
    """1. Toda frase de divergência cita pelo menos 2 fontes."""
    nomes_fontes = [f.get("nome", "").lower() for f in fonte_informacoes if f.get("nome")]
    frases = [f.strip() for f in texto.replace("!", ".").replace("?", ".").split(".") if f.strip()]
    falhas = []
    for frase in frases:
        frase_lower = frase.lower()
        # Detecta se é frase de divergência (contém palavras como 'porém', 'contudo', 'diferente', 'diverge')
        palavras_divergencia = {"porém", "contudo", "entretanto", "diferente", "diverge", "oposto", "contrario", "enquanto"}
        eh_divergencia = any(p in frase_lower for p in palavras_divergencia)
        if eh_divergencia:
            fontes_citadas = sum(1 for n in nomes_fontes if n in frase_lower)
            if fontes_citadas < 2:
                falhas.append(f"Frase de divergencia cita menos de 2 fontes: '{frase[:80]}...'")
    passou = len(falhas) == 0
    return ResultadoVerificacao(
        "divergencia_cita_duas_fontes",
        passou,
        f"{len(falhas)} falhas" if falhas else "Todas as frases de divergencia citam >= 2 fontes",
        falhas,
    )


def verificar_sem_veredito(
    texto: str,
    padroes_proibidos: list[str] | None = None,
) -> ResultadoVerificacao:
    """2. Nenhum veredito: lista configurável de padrões proibidos."""
    padroes = padroes_proibidos or [
        "na verdade",
        "o correto e",
        "quem esta certo",
        "esta errado",
        "erro da fonte",
        "a versao verdadeira",
    ]
    encontrados = []
    texto_lower = texto.lower()
    for padrao in padroes:
        if padrao in texto_lower:
            encontrados.append(padrao)
    passou = len(encontrados) == 0
    return ResultadoVerificacao(
        "sem_veredito",
        passou,
        f"Padrões proibidos encontrados: {encontrados}" if encontrados else "Sem veredito proibido",
        encontrados,
    )


def verificar_valores_grafico_iguais_matriz(
    graficos: list[dict[str, Any]],
    comparacoes: list[Any],
) -> ResultadoVerificacao:
    """3. Os valores plotados são iguais aos da matriz (comparar JSON do gráfico com a matriz)."""
    falhas = []
    for g in graficos:
        dados_plotados = g.get("dados_plotados", [])
        # Busca a comparação correspondente
        for comp in comparacoes:
            if comp.indicador == g.get("indicador") and comp.periodo == g.get("periodo"):
                for dp in dados_plotados:
                    for v in comp.valores:
                        if v.fonte_nome == dp.get("fonte") and abs(v.valor - float(dp.get("valor", 0))) > 0.001:
                            falhas.append(
                                f"Grafico {g.get('arquivo')}: valor plotado {dp.get('valor')} != matriz {v.valor}"
                            )
    passou = len(falhas) == 0
    return ResultadoVerificacao(
        "valores_grafico_iguais_matriz",
        passou,
        f"{len(falhas)} falhas" if falhas else "Valores do grafico coincidem com a matriz",
        falhas,
    )


def verificar_cobertura_matriz(
    texto: str,
    linhas_divergencia: list[LinhaMatriz],
) -> ResultadoVerificacao:
    """4. Toda linha com divergência calculada aparece no texto (cobertura da matriz)."""
    faltando = []
    texto_lower = texto.lower()
    for l in linhas_divergencia:
        if l.linha_id.lower() not in texto_lower and l.topico.lower() not in texto_lower:
            faltando.append(l.linha_id)
    passou = len(faltando) == 0
    return ResultadoVerificacao(
        "cobertura_matriz",
        passou,
        f"Linhas nao cobertas: {faltando}" if faltando else "Todas as linhas de divergencia cobertas",
        faltando,
    )


def verificar_atribuicao_toda_frase(
    texto: str,
    fonte_informacoes: list[dict[str, Any]],
) -> ResultadoVerificacao:
    """5. Toda afirmação do texto tem atribuição de fonte."""
    sem_atribuicao = []
    nomes_fontes = [f.get("nome", "").lower() for f in fonte_informacoes if f.get("nome")]
    frases = [f.strip() for f in texto.replace("!", ".").replace("?", ".").split(".") if f.strip()]
    for frase in frases:
        if len(frase.split()) > 5:
            frase_lower = frase.lower()
            if not any(n in frase_lower for n in nomes_fontes):
                sem_atribuicao.append(frase[:80])
    passou = len(sem_atribuicao) == 0
    return ResultadoVerificacao(
        "atribuicao_fonte",
        passou,
        f"{len(sem_atribuicao)} frases sem atribuicao" if sem_atribuicao else "Todas as frases tem atribuicao",
        sem_atribuicao,
    )


def verificar_fontes_mesma_origem_nao_contam_independentes(
    fontes_independentes: list[dict[str, Any]],
    grupos_origem: list[Any],
) -> ResultadoVerificacao:
    """6. Fontes de mesma origem não são contadas como independentes."""
    ids_independentes = {f.get("id") for f in fontes_independentes}
    ids_em_grupo = set()
    for g in grupos_origem:
        ids_em_grupo.update(g.fonte_ids if hasattr(g, "fonte_ids") else g.get("fonte_ids", []))
    sobreposicao = ids_independentes & ids_em_grupo
    passou = len(sobreposicao) == 0
    return ResultadoVerificacao(
        "origem_comum_nao_conta_independente",
        passou,
        f"Sobreposicao: {sobreposicao}" if sobreposicao else "Nenhuma fonte de mesma origem contada como independente",
        list(sobreposicao),
    )


def verificar_numeros_datas_existem_matriz(
    texto: str,
    matriz: list[LinhaMatriz],
    fontes: list[dict[str, Any]],
) -> ResultadoVerificacao:
    """7. Todo número e data do texto existe na matriz ou nas fontes."""
    numeros_texto = re.findall(r"\d[\d.,]*%?", texto)
    valores_matriz = set()
    for l in matriz:
        for c in l.celulas:
            if c.valor_texto:
                nums = re.findall(r"\d[\d.,]*", c.valor_texto)
                valores_matriz.update(nums)
            if c.trecho:
                nums = re.findall(r"\d[\d.,]*", c.trecho)
                valores_matriz.update(nums)
    # Verifica se numeros do texto estao na matriz (verificação simplificada)
    falhas = []
    for n in numeros_texto:
        n_normalizado = n.replace(",", ".").replace("%", "")
        if n_normalizado not in valores_matriz:
            # Pode ser numero de palavras (não é dado), ignora se for muito pequeno
            try:
                if float(n_normalizado) > 1:
                    falhas.append(f"Numero '{n}' nao encontrado na matriz ou fontes")
            except ValueError:
                pass
    passou = len(falhas) == 0
    return ResultadoVerificacao(
        "numeros_datas_existem_matriz",
        passou,
        f"{len(falhas)} numeros sem origem" if falhas else "Todos os numeros tem origem",
        falhas,
    )


def verificar_emojis_termos_proibidos(
    texto: str,
    termos_proibidos: list[str],
) -> ResultadoVerificacao:
    """8. Sem emojis, sem termos proibidos."""
    import re as _re
    emoji_pattern = _re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "]+",
        flags=_re.UNICODE,
    )
    tem_emoji = bool(emoji_pattern.search(texto))
    encontrados_proibidos = [t for t in termos_proibidos if t in texto.lower()]
    falhas = []
    if tem_emoji:
        falhas.append("Emoji encontrado")
    if encontrados_proibidos:
        falhas.append(f"Termos proibidos: {encontrados_proibidos}")
    passou = len(falhas) == 0
    return ResultadoVerificacao(
        "sem_emojis_termos_proibidos",
        passou,
        "; ".join(falhas) if falhas else "Sem emojis nem termos proibidos",
        falhas,
    )


def verificar_iniciante_termos_explicados(
    texto: str,
    glossario_termos: list[str],
    nivel: str,
) -> ResultadoVerificacao:
    """Iniciante: todos os termos técnicos explicados."""
    if nivel != "iniciante":
        return ResultadoVerificacao("iniciante_termos_explicados", True, "Nao se aplica a nivel != iniciante")
    falhas = []
    texto_lower = texto.lower()
    for termo in glossario_termos:
        if termo.lower() in texto_lower:
            # Verifica se há explicação próxima (heurística simples)
            if "em geral" not in texto_lower and "explica" not in texto_lower:
                falhas.append(f"Termo '{termo}' usado sem explicacao")
    passou = len(falhas) == 0
    return ResultadoVerificacao(
        "iniciante_termos_explicados",
        passou,
        f"{len(falhas)} termos sem explicacao" if falhas else "Todos os termos do glossario explicados",
        falhas,
    )


def verificar_diferenciacao_niveis(
    textos_por_nivel: dict[str, str],
    limiar: float = 0.7,
) -> ResultadoVerificacao:
    """Diferenciação entre níveis: sobreposição de trigramas acima do limiar reprova."""
    from src.evaluation.differentiation import trigram_overlap_ratio
    niveis = list(textos_por_nivel.keys())
    falhas = []
    for i in range(len(niveis)):
        for j in range(i + 1, len(niveis)):
            n1, n2 = niveis[i], niveis[j]
            t1, t2 = textos_por_nivel[n1], textos_por_nivel[n2]
            overlap = trigram_overlap_ratio(t1, t2)
            if overlap > limiar:
                falhas.append(f"Sobreposicao {n1}x{n2}: {overlap:.2f} > {limiar}")
    passou = len(falhas) == 0
    return ResultadoVerificacao(
        "diferenciacao_niveis",
        passou,
        "; ".join(falhas) if falhas else "Niveis diferenciados adequadamente",
        falhas,
    )


def executar_todas_verificacoes(
    texto: str,
    matriz: list[LinhaMatriz],
    fonte_informacoes: list[dict[str, Any]],
    graficos: list[dict[str, Any]],
    comparacoes: list[Any],
    termos_proibidos: list[str],
    glossario_termos: list[str],
    nivel: str,
    textos_por_nivel: dict[str, str] | None = None,
    padroes_proibidos: list[str] | None = None,
) -> list[ResultadoVerificacao]:
    """Executa todas as verificações determinísticas novas."""
    linhas_divergencia = [l for l in matriz if l.status in ("divergencia_numerica", "divergencia_qualitativa")]

    resultados = [
        verificar_divergencia_cita_duas_fontes(texto, linhas_divergencia, fonte_informacoes),
        verificar_sem_veredito(texto, padroes_proibidos),
        verificar_cobertura_matriz(texto, linhas_divergencia),
        verificar_atribuicao_toda_frase(texto, fonte_informacoes),
        verificar_numeros_datas_existem_matriz(texto, matriz, fonte_informacoes),
        verificar_emojis_termos_proibidos(texto, termos_proibidos),
        verificar_iniciante_termos_explicados(texto, glossario_termos, nivel),
    ]

    # Verificação de gráficos (se houver)
    if graficos and comparacoes:
        resultados.append(verificar_valores_grafico_iguais_matriz(graficos, comparacoes))

    # Verificação de diferenciação (se houver textos por nível)
    if textos_por_nivel:
        resultados.append(verificar_diferenciacao_niveis(textos_por_nivel))

    return resultados