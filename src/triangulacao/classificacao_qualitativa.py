"""Classificacao qualitativa assistida por modelo para triangulacao."""
from __future__ import annotations

from typing import Any
from pathlib import Path
import yaml

from src.shared.llm_client import LLMClient, LLMCallResult
from src.triangulacao.models import PosicaoClassificada, PosicaoQualitativa


def load_config_triangulacao(path: str = "config/triangulacao.yaml") -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


class ClassificadorQualitativo:
    """Classifica afirmacoes qualitativas em posicoes controladas (apoiar, contestar, neutra, nao menciona).

    Usa LLM em modo simulado/live/record com rubrica versionada.
    Uma 'divergencia qualitativa' exige posicoes opostas com evidencia para as duas pontas.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        model_id: str | None = None,
        rubric_path: str = "src/evaluation/rubric_triangulacao.yaml",
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.model_id = model_id or "juiz-modelo"
        self.rubric_path = rubric_path
        self.rubrica = self._carregar_rubrica(rubric_path)

    def _carregar_rubrica(self, path: str) -> dict[str, Any]:
        file_path = Path(path)
        if not file_path.exists():
            return {"versao": "1.0", "criterios": [], "prompt": ""}
        with file_path.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {}

    def _montar_prompt(
        self,
        afirmacao: str,
        trecho_evidencia: str,
        fonte_nome: str,
        topico: str,
        lista_controlada: list[str],
    ) -> str:
        return (
            f"Voce e um classificador de afirmacoes financeiras para triangulacao de fontes.\n"
            f"Topico: {topico}\n"
            f"Fonte: {fonte_nome}\n"
            f"Afirmacao: {afirmacao}\n"
            f"Trecho de evidencia: {trecho_evidencia}\n\n"
            f"Classifique a posicao da fonte em relação a este topico em UMA das categorias:\n"
            f"- apoiar: a fonte apoia/concorda com o topico\n"
            f"- contestar: a fonte contesta/discorda do topico\n"
            f"- neutra: a fonte apresenta informacao sem posicao clara\n"
            f"- nao_menciona: a fonte nao menciona o topico\n\n"
            f"Retorne JSON com: posicao (uma das 4 categorias), confianca (0.0 a 1.0), "
            f"justificativa (curta), trecho_evidencia (trecho que sustenta a classificacao).\n"
            f"Se nao houver evidencia suficiente para apoiar ou contestar, classifique como 'neutra'.\n"
            f"Nunca invente informacao que nao esteja no trecho de evidencia."
        )

    def classificar(
        self,
        afirmacao_id: str,
        afirmacao: str,
        trecho_evidencia: str,
        fonte_id: str,
        fonte_nome: str,
        topico: str,
    ) -> PosicaoClassificada:
        """Classifica uma afirmacao qualitativa."""
        lista_controlada = ["apoiar", "contestar", "neutra", "nao_menciona"]
        prompt = self._montar_prompt(afirmacao, trecho_evidencia, fonte_nome, topico, lista_controlada)

        resultado = self.llm_client.generate(
            prompt,
            schema_name="classificacao_qualitativa",
            model_id=self.model_id,
            cache_parts={
                "afirmacao_id": afirmacao_id,
                "fonte_id": fonte_id,
                "topico": topico,
                "rubrica_versao": self.rubrica.get("versao", "1.0"),
            },
        )

        resposta = resultado.response
        posicao_texto = str(resposta.get("posicao", "neutra")).lower().strip()
        try:
            posicao = PosicaoQualitativa(posicao_texto)
        except ValueError:
            posicao = PosicaoQualitativa.NEUTRA

        confianca = float(resposta.get("confianca", 0.5))
        confianca = max(0.0, min(1.0, confianca))

        return PosicaoClassificada(
            afirmacao_id=afirmacao_id,
            fonte_id=fonte_id,
            posicao=posicao,
            confianca=confianca,
            trecho_evidencia=trecho_evidencia,
            justificativa=str(resposta.get("justificativa", "")),
        )


def eh_divergencia_qualitativa(
    classificacoes: list[PosicaoClassificada],
    limiar_confianca: float = 0.6,
) -> bool:
    """Verifica se ha divergencia qualitativa entre classificacoes.

    Exige posicoes opostas (apoiar vs contestar) com evidencia para as duas pontas
    e confianca acima do limiar.
    """
    apoiando = [c for c in classificacoes if c.posicao == PosicaoQualitativa.APOIA and c.confianca >= limiar_confianca]
    contestando = [c for c in classificacoes if c.posicao == PosicaoQualitativa.CONTESTA and c.confianca >= limiar_confianca]

    if apoiando and contestando:
        # Verifica se ambas tem trecho de evidencia
        tem_evidencia_apoiar = all(c.trecho_evidencia for c in apoiando)
        tem_evidencia_contestar = all(c.trecho_evidencia for c in contestando)
        return tem_evidencia_apoiar and tem_evidencia_contestar

    return False


def posicoes_opostas(
    classificacoes: list[PosicaoClassificada],
) -> tuple[list[PosicaoClassificada], list[PosicaoClassificada]] | None:
    """Retorna as duas pontas opostas se existirem, ou None."""
    apoiando = [c for c in classificacoes if c.posicao == PosicaoQualitativa.APOIA]
    contestando = [c for c in classificacoes if c.posicao == PosicaoQualitativa.CONTESTA]
    if apoiando and contestando:
        return apoiando, contestando
    return None