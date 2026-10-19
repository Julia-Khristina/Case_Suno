"""Redacao de texto analítico por nível para triangulacao."""
from __future__ import annotations

from typing import Any
from pathlib import Path
import yaml

from src.shared.llm_client import LLMClient, LLMCallResult
from src.triangulacao.models import LinhaMatriz, StatusLinhaMatriz, Triangulacao


def load_config_triangulacao(path: str = "config/triangulacao.yaml") -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_guia_estilo(path: str = "config/guia_estilo.yaml") -> str:
    file_path = Path(path)
    if not file_path.exists():
        return "sobria e factual, portugues do Brasil, sem emojis"
    with file_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    return ", ".join(f"{k}: {v}" for k, v in data.items())


class RedatorNivel:
    """Redator de texto analítico por nível para triangulacao.

    Recebe a MATRIZ (linhas com ids, status, células e diferenças já calculadas),
    os 3 pontos centrais, as entradas do glossário e as regras do nível e do estilo.
    Não recebe os documentos inteiros.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        model_id: str | None = None,
        nivel: str = "iniciante",
        config: dict[str, Any] | None = None,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.model_id = model_id or "gerador-modelo"
        self.nivel = nivel
        self.config = config or load_config_triangulacao()
        self.guia_estilo = load_guia_estilo()
        self.max_graficos = {
            "iniciante": 2,
            "intermediario": 3,
            "avancado": 4,
        }.get(nivel, 2)

    def _regras_nivel(self) -> str:
        regras = {
            "iniciante": (
                "Nivel INICIANTE: linguagem simples, ate 2 graficos, explicacoes de termos pelo glossario. "
                "Marcador 'Em geral,' SOMENTE com frases do glossario. "
                "Intervalo de palavras igual aos outros niveis. "
                "Todas as linhas com status de divergencia devem ser cobertas. "
                "Cada frase sobre uma linha cita o id da linha. "
                "Frase de divergencia cita pelo menos duas fontes pelo nome. "
                "Nunca use veredito ('na verdade', 'o correto e', 'quem esta certo', etc.). "
                "Nunca use emojis. Nunca use linguagem de recomendacao de compra ou venda."
            ),
            "intermediario": (
                "Nivel INTERMEDIARIO: vocabulario padrao de mercado, tabela de comparacao. "
                "Intervalo de palavras igual aos outros niveis. "
                "Todas as linhas com status de divergencia devem ser cobertas. "
                "Cada frase sobre uma linha cita o id da linha. "
                "Frase de divergencia cita pelo menos duas fontes pelo nome. "
                "Nunca use veredito. Nunca use emojis. Nunca use linguagem de recomendacao."
            ),
            "avancado": (
                "Nivel AVANCADO: jargao pleno, diferencas metodologicas (periodos, bases de calculo, definicoes) "
                "e o que nao foi comparavel. "
                "Intervalo de palavras igual aos outros niveis. "
                "Todas as linhas com status de divergencia devem ser cobertas. "
                "Cada frase sobre uma linha cita o id da linha. "
                "Frase de divergencia cita pelo menos duas fontes pelo nome. "
                "Nunca use veredito. Nunca use emojis. Nunca use linguagem de recomendacao."
            ),
        }
        return regras.get(self.nivel, regras["iniciante"])

    def _montar_prompt(
        self,
        matriz: list[LinhaMatriz],
        pontos_centrais: list[str],
        glossario_termos: list[str],
        termos_proibidos: list[str],
        fonte_informacoes: list[dict[str, Any]],
        graficos_referenciados: list[dict[str, Any]],
        feedback: str | None = None,
    ) -> str:
        # Filtra apenas linhas aprovadas (divergencias e convergencias relevantes)
        linhas_divergencia = [l for l in matriz if l.status in ("divergencia_numerica", "divergencia_qualitativa")]
        linhas_convergencia = [l for l in matriz if l.status == "convergencia"]

        # Monta texto das linhas para o prompt
        linhas_texto = []
        for l in matriz:
            celulas_txt = []
            for c in l.celulas:
                celulas_txt.append(f"  - {c.fonte_nome}: {c.valor_texto or c.trecho_curto or ''} [id:{c.fonte_id}]")
            linhas_texto.append(
                f"Linha {l.linha_id} | Topico: {l.topico} | Status: {l.status}\n"
                + "\n".join(celulas_txt)
            )

        graficos_txt = ""
        if graficos_referenciados:
            graficos_txt = "Graficos disponíveis:\n"
            for g in graficos_referenciados:
                graficos_txt += f"  - {g.get('tipo', '')}: {g.get('texto_alternativo', '')}\n"

        fontes_txt = "Fontes comparadas:\n"
        for f in fonte_informacoes:
            fontes_txt += f"  - {f.get('nome', '')} ({f.get('tipo_fonte', '')}, {f.get('data', '')})\n"

        if fonte_informacoes:
            # Verifica origem comum
            tem_origem_comum = any(f.get("origem_comum_id") for f in fonte_informacoes)
            if tem_origem_comum:
                fontes_txt += "\nAVISO: Algumas fontes compartilham origem comum (mesmo documento primario).\n"

        prompt = (
            f"Gere um texto analítico em JSON para o nível {self.nivel.upper()} sobre triangulação de fontes.\n\n"
            f"GUIA DE ESTILO: {self.guia_estilo}\n\n"
            f"{self._regras_nivel()}\n\n"
            f"PONTOS CENTRAIS (3):\n"
            + "\n".join(f"- {p}" for p in pontos_centrais)
            + f"\n\nLINHAS DA MATRIZ (citar id da linha em cada frase):\n"
            + "\n\n".join(linhas_texto)
            + f"\n\n{graficos_txt}"
            + f"\n{fontes_txt}"
            + f"\nTERMOS DO GLOSSÁRIO: {', '.join(glossario_termos)}\n"
            + f"TERMOS PROIBIDOS: {', '.join(termos_proibidos)}\n"
            + f"\nESTRUTURA OBRIGATÓRIA (4 seções):\n"
            + "1. Introdução: o assunto e as fontes comparadas (tipo, data), com aviso de origem comum se houver.\n"
            + "2. Desenvolvimento: convergências e dados, com os gráficos referenciados.\n"
            + "3. Análise: divergências e lados opostos, causas e riscos declarados pelas fontes.\n"
            + "4. Conclusão: síntese sem veredito, com os fatores que as fontes indicam acompanhar.\n\n"
            + f"\nINTERVALO DE PALAVRAS: mesmo para os 3 níveis (matriz, apêndices e legendas de gráfico não entram na contagem).\n"
            + f"\nRELATÓRIO DE FALHAS ANTERIORES (se houver): {feedback or '(nenhum)'}\n\n"
            + "Responda APENAS com JSON válido contendo: title, subtitle, introduction, development, analysis, conclusion, "
            + "covered_main_points, word_count_total, word_count_by_section, fonte_bloco, verso_prompt."
        )
        return prompt

    def gerar(
        self,
        matriz: list[LinhaMatriz],
        pontos_centrais: list[str],
        glossario_termos: list[str],
        termos_proibidos: list[str],
        fonte_informacoes: list[dict[str, Any]],
        graficos_referenciados: list[dict[str, Any]] | None = None,
        feedback: str | None = None,
    ) -> dict[str, Any]:
        """Gera texto analítico para o nível."""
        graficos_referenciados = graficos_referenciados or []
        glossario_termos = glossario_termos or []
        termos_proibidos = termos_proibidos or []

        prompt = self._montar_prompt(
            matriz=matriz,
            pontos_centrais=pontos_centrais,
            glossario_termos=glossario_termos,
            termos_proibidos=termos_proibidos,
            fonte_informacoes=fonte_informacoes,
            graficos_referenciados=graficos_referenciados,
            feedback=feedback,
        )

        resultado = self.llm_client.generate(
            prompt,
            schema_name="redacao_nivel",
            model_id=self.model_id,
            cache_parts={
                "nivel": self.nivel,
                "matriz_hash": hashlib_matriz(matriz),
                "versao_prompt": "1.0",
            },
        )
        return resultado.response


def hashlib_matriz(matriz: list[LinhaMatriz]) -> str:
    """Gera hash da matriz para cache."""
    import hashlib
    dados = [l.model_dump() for l in matriz]
    return hashlib.sha256(str(dados).encode("utf-8")).hexdigest()[:16]


def verificar_cobertura_divergencias(
    texto: str,
    linhas_divergencia: list[LinhaMatriz],
) -> list[str]:
    """Verifica se todas as linhas de divergencia estao cobertas no texto."""
    faltando = []
    texto_lower = texto.lower()
    for l in linhas_divergencia:
        if l.linha_id.lower() not in texto_lower:
            # Tenta buscar por topico
            if l.topico.lower() not in texto_lower:
                faltando.append(l.linha_id)
    return faltando


def verificar_atribuicao_fontes(
    texto: str,
    fonte_informacoes: list[dict[str, Any]],
) -> list[str]:
    """Verifica se toda frase tem atribuicao de fonte (verificacao heurística)."""
    nomes_fontes = [f.get("nome", "").lower() for f in fonte_informacoes if f.get("nome")]
    frases = [f.strip() for f in texto.replace("!", ".").replace("?", ".").split(".") if f.strip()]
    sem_atribuicao = []
    for frase in frases:
        frase_lower = frase.lower()
        tem_nome = any(nome in frase_lower for nome in nomes_fontes)
        # Frases curtas ou de conector podem não ter atribuição
        if len(frase.split()) > 5 and not tem_nome:
            sem_atribuicao.append(frase[:80])
    return sem_atribuicao


def verificar_veredito_proibido(
    texto: str,
    padroes_proibidos: list[str] | None = None,
) -> list[str]:
    """Verifica se o texto contem padroes de veredito proibido."""
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
    return encontrados