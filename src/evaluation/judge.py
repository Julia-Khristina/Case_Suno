"""Structured LLM-as-a-judge (seção 4.7).

- Modelo próprio (GROQ_JUDGE_MODEL_ID), diferente do gerador; temperatura do juiz e reasoning_effort.
- Rubrica versionada em src/evaluation/rubric.yaml, enviada com descrição e âncoras de cada critério.
- Recebe o material, as afirmações da fonte (com id e trecho) e as métricas determinísticas — não o documento inteiro.
- Saída validada por Pydantic: todos os critérios, nota 0–10, justificativa e ao menos uma evidência por critério.
  Saída inválida levanta InvalidLLMOutput.
- Aprovação, tamanho do texto e modelo são calculados/registrados pelo código, não informados pelo juiz.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from src.evaluation.text_utils import word_count
from src.evaluation.thresholds import as_thresholds
from src.shared.llm_client import InvalidLLMOutput, LLMClient


class PatchSuggestion(BaseModel):
    """Sugestão de alteração para gerar diff colorido com hover."""
    trecho_antes: str = Field(description="Texto original que deve ser alterado")
    trecho_depois: str = Field(description="Texto proposto para substituição")
    posicao_inicial: int = Field(description="Posição inicial do trecho no texto (índice de caractere)")
    tipo: str = Field(description="Tipo: 'insercao', 'remocao' ou 'substituicao'")


class JudgeCriterionScore(BaseModel):
    nome: str
    nota: float = Field(ge=0, le=10)
    justificativa: str = Field(min_length=1)
    evidencias: list[str] = Field(min_length=1)

    @field_validator("evidencias")
    @classmethod
    def _non_empty(cls, value: list[str]) -> list[str]:
        cleaned = [v for v in (str(x).strip() for x in value) if v]
        if not cleaned:
            raise ValueError("cada critério precisa de ao menos uma evidência")
        return cleaned


class JudgeLLMOutput(BaseModel):
    criterios: list[JudgeCriterionScore]
    resumo: str = ""


class JudgeResult(BaseModel):
    rubric_version: str
    judge_model_id: str
    scores: dict[str, float]
    justification: str
    text_length: int
    evidence: list[str] = []
    aprovado: bool = False
    patch_sugerido: list[PatchSuggestion] = Field(default_factory=list)
    criterios: list[JudgeCriterionScore] = Field(default_factory=list)
    media_ponderada: float = 0.0
    criterios_abaixo_do_minimo: list[str] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
    latency_seconds: float = 0.0

    def feedback(self, media_minima: float | None = None, nota_minima: float | None = None) -> str:
        """Feedback numérico do juiz para a reescrita: critério, nota, mínimo, justificativa e evidência."""
        header = (f"Avaliação do juiz (rubrica {self.rubric_version}): média ponderada {self.media_ponderada:.2f}"
                  + (f" (mínimo {media_minima})" if media_minima is not None else "") + ".")
        lines = [header]
        for c in sorted(self.criterios, key=lambda c: c.nota):
            if nota_minima is not None and c.nota >= max(nota_minima, 8):
                continue
            lines.append(f"- {c.nome}: nota={c.nota:.1f}" + (f" | mínimo={nota_minima}" if nota_minima is not None else "")
                         + f" | {c.justificativa} | evidências={'; '.join(c.evidencias[:3])}")
        return "\n".join(lines)


class LLMJudge:
    """Juiz LLM com rubrica versionada e saída estruturada. Roda só depois das métricas determinísticas passarem."""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        model_id: str | None = None,
        rubric_path: str | Path = "src/evaluation/rubric.yaml",
        thresholds: dict | None = None,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.model_id = model_id
        self.rubric = self._load_rubric(rubric_path)
        self.rubric_version = str(self.rubric.get("versao", "0"))
        self.thresholds = as_thresholds(thresholds)
        self.last_usage: dict[str, int] = {}

    @staticmethod
    def _load_rubric(path: str | Path) -> dict:
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Rubrica do juiz não encontrada: {file_path}")
        return yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}

    @property
    def criteria(self) -> list[dict]:
        return list(self.rubric.get("criterios") or [])

    def _criteria_block(self) -> str:
        lines = []
        for c in self.criteria:
            anchors = "; ".join(f"{k}: {v}" for k, v in (c.get("ancoras") or {}).items())
            lines.append(f"- {c['nome']} (peso {c.get('peso', 1.0)}): {c.get('descricao', '')}"
                         + (f" Âncoras — {anchors}" if anchors else ""))
        return "\n".join(lines)

    def evaluate(
        self,
        generated_text: str,
        source_text: str = "",
        level: str | None = None,
        formato: str | None = None,
        main_points: list[str] | None = None,
        glossary_terms: list[str] | None = None,
        forbidden_terms: list[str] | None = None,
        evidence: list[str] | None = None,
        assertions_block: str | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> JudgeResult:
        afirmacoes = assertions_block or "\n".join(f"- {p}" for p in (main_points or [])) or "(sem afirmações)"
        metric_lines = "\n".join(f"- {k}: {v}" for k, v in (metrics or {}).items()) or "(não informadas)"
        prompt = str(self.rubric.get("prompt", "")).format(
            rubric_version=self.rubric_version,
            nivel_alvo=level or "nao_informado",
            formato=formato or "texto_analitico",
            afirmacoes=afirmacoes,
            metricas=metric_lines,
            texto_gerado=generated_text,
            criterios=self._criteria_block(),
        )
        call = self.llm_client.generate(
            prompt,
            schema_name="judge",
            model_id=self.model_id,
            role="judge",
            cache_parts={"rubric_version": self.rubric_version, "level": level, "formato": formato},
        )
        self.last_usage = call.usage
        try:
            parsed = JudgeLLMOutput.model_validate(call.response)
        except ValidationError as exc:
            raise InvalidLLMOutput(f"Saída do juiz fora do contrato: {exc}") from exc

        expected = [c["nome"] for c in self.criteria]
        by_name = {c.nome: c for c in parsed.criterios}
        missing = [n for n in expected if n not in by_name]
        if missing:
            raise InvalidLLMOutput(f"Juiz não avaliou os critérios: {missing}")
        scored = [by_name[n] for n in expected]

        weights = {c["nome"]: float(c.get("peso", 1.0)) for c in self.criteria}
        weighted = sum(c.nota * weights[c.nome] for c in scored) / sum(weights.values())
        media_minima = float(self.thresholds.req("juiz_media_minima"))
        nota_minima = float(self.thresholds.req("juiz_nota_minima_criterio"))
        below = [c.nome for c in scored if c.nota < nota_minima]

        return JudgeResult(
            rubric_version=self.rubric_version,
            judge_model_id=call.model_id,
            scores={c.nome: c.nota for c in scored},
            justification=parsed.resumo or " | ".join(f"{c.nome}: {c.justificativa}" for c in scored),
            text_length=word_count(generated_text),
            evidence=[e for c in scored for e in c.evidencias],
            aprovado=weighted >= media_minima and not below,
            criterios=scored,
            media_ponderada=round(weighted, 3),
            criterios_abaixo_do_minimo=below,
            usage=call.usage,
            latency_seconds=call.latency_seconds,
        )
