# -*- coding: utf-8 -*-
"""Cliente LLM falso, determinístico, com a mesma interface do LLMClient (sem rede).

Respostas programáveis por papel/formato em fila: cada chamada consome o próximo item; o último se repete.
Registra cada chamada (papel, schema, modelo, prompt) para os testes inspecionarem feedback e contagem.
"""
from __future__ import annotations

import copy
from typing import Any, Callable

from pydantic import ValidationError

from src.shared.llm_client import InvalidLLMOutput, LLMCallResult, LLMConfigError
from tests.fakes import content

SCHEMA_TO_FORMAT = {"analytical_text": "texto_analitico", "analytical_text_triangulated": "texto_analitico", "carousel_with_caption": "carrossel", "script": "roteiro_video"}


class FakeLLMClient:
    mode = "simulated"

    def __init__(self, responses: dict[str, list[Any]] | None = None, level_of: Callable[[str], str] | None = None,
                 judge_model: str = "judge-model-x", generation_model: str = "gen-model-y", tokens_per_call: int = 1000):
        self.responses = {k: list(v) for k, v in (responses or {}).items()}
        self.default_model = generation_model
        self.judge_model = judge_model
        self.tokens_per_call = tokens_per_call
        self.calls: list[dict[str, Any]] = []
        self.prompts: list[dict[str, Any]] = []

    def model_for(self, role: str, model_id: str | None = None) -> str:
        if model_id:
            return model_id
        return self.judge_model if role == "judge" else self.default_model

    def assert_distinct_models(self) -> None:
        if self.judge_model == self.default_model:
            raise LLMConfigError("juiz igual ao gerador")

    @staticmethod
    def _level_from_prompt(prompt: str) -> str:
        for marker, level in (("nível INICIANTE", "iniciante"), ("nível INTERMEDIÁRIO", "intermediario"),
                              ("nível AVANÇADO", "avancado")):
            if marker in prompt:
                return level
        return "iniciante"

    def _next(self, key: str, default: Any) -> Any:
        queue = self.responses.get(key)
        if not queue:
            return default
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def generate(self, prompt: str, schema_name: str = "text", model_id: str | None = None, temperature=None,
                 cache_parts=None, pydantic_schema=None, system: str | None = None, role: str = "generation") -> LLMCallResult:
        model = self.model_for(role, model_id)
        level = self._level_from_prompt(prompt)
        fmt = SCHEMA_TO_FORMAT.get(schema_name)
        if schema_name == "extraction":
            response = self._next("extraction", copy.deepcopy(content.EXTRACTION))
        elif schema_name == "judge":
            triangulated = "fidelidade_atribuicao" in prompt  # rubrica do texto triangulado
            default = content.judge_output(rubric_path="src/evaluation/rubric_triangulado.yaml") if triangulated \
                else content.judge_output()
            key = "judge_triangulado" if triangulated else "judge"
            response = self._next(f"{key}:{level}", self._next(key, default))
        elif fmt:
            response = self._next(f"{level}:{fmt}", self._next(fmt, content.good_output(fmt, level)))
        else:
            response = self._next(schema_name, {})
        if callable(response):
            response = response(prompt)
        self.prompts.append({"role": role, "schema": schema_name, "level": level, "prompt": prompt, "system": system})
        self.calls.append({"role": role, "model_id": model, "total_tokens": self.tokens_per_call, "latency_seconds": 0.01,
                           "cache_hit": False, "schema": schema_name})
        if isinstance(response, Exception):
            raise response
        if pydantic_schema is not None:
            try:
                pydantic_schema.model_validate(response)
            except ValidationError as exc:
                raise InvalidLLMOutput(str(exc)) from exc
        return LLMCallResult(response=copy.deepcopy(response), usage={"total_tokens": self.tokens_per_call},
                             latency_seconds=0.01, model_id=model, mode="fake", role=role)

    @property
    def usage(self) -> dict:
        return {"total_tokens": self.tokens_per_call}

    @property
    def latency(self) -> float:
        return 0.01
