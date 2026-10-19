"""Pipeline state definition (seção 4.10).

Todos os campos que os nós leem ou escrevem estão declarados aqui; `extra="forbid"` faz um campo
desconhecido falhar alto, em vez de ser descartado em silêncio entre os nós (bug da versão anterior).
Objetos não serializáveis (cliente LLM, glossário, persistência) ficam em `PipelineDeps`, fora do estado.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PipelineState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Execução e documento
    execution_id: str | None = None
    document: dict[str, Any] | None = None          # {"content", "origin": {instituicao, titulo, data, url}, "hash"}
    selected_levels: list[str] = Field(default_factory=list)
    config_versions: dict[str, str] = Field(default_factory=dict)
    thresholds: dict[str, Any] = Field(default_factory=dict)
    admission: dict[str, Any] | None = None

    # Extração (no modo triangulado: extração combinada das fontes, com os 3 pontos centrais da matriz)
    extraction: dict[str, Any] | None = None
    # Triangulação: dossiê das fontes, matriz, pontos centrais e gráficos; None no modo fonte única
    triangulacao: dict[str, Any] | None = None
    # Gráficos gerados por regra a partir dos dados da fonte (modo fonte única)
    graficos: list[dict[str, Any]] = Field(default_factory=list)

    # Fila de combinações nível:formato e combinação atual
    combos: list[str] = Field(default_factory=list)
    combo_index: int = 0
    current_level: str | None = None
    current_format: str | None = None
    material_ids: dict[str, str] = Field(default_factory=dict)

    # Saídas finais por "nivel:formato" e histórico de todas as tentativas
    generated_outputs: dict[str, Any] = Field(default_factory=dict)
    attempt_history: list[dict[str, Any]] = Field(default_factory=list)

    # Tentativa atual
    last_generation: dict[str, Any] | None = None
    deterministic_evaluation: dict[str, Any] | None = None
    judge_evaluation: dict[str, Any] | None = None

    # Loop de reflexão: duas reescritas por padrão (até 3 tentativas por nível e formato)
    retry_count: int = 0
    max_retries: int = 2
    feedback: str | None = None
    # Motivo da revisora ao rejeitar a versão anterior ("Rejeitar e gerar de novo"): vale para todas as tentativas
    human_feedback: str | None = None

    # Roteamento: decidido pelo nó que avaliou (generate | judge | finalize | human_validation | export | end)
    next_action: str | None = None
    stop_reason: str | None = None  # por que a combinação foi encerrada antes do teto (ex.: reescrita sem mudança)
    human_decision: str | None = None
    status: str = "em_andamento"
    last_node: str | None = None

    # Métricas acumuladas
    token_count: int = 0
    latency_total: float = 0.0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def output_key(self) -> str | None:
        if self.current_level and self.current_format:
            return f"{self.current_level}:{self.current_format}"
        return None

    @property
    def retries_exhausted(self) -> bool:
        return self.retry_count >= self.max_retries
