"""LLM client with live, simulated and record modes for the Groq provider.

- Lê GROQ_API_KEY, GROQ_BASE_URL, GROQ_GENERATION_MODEL_ID, GROQ_JUDGE_MODEL_ID, GROQ_JUDGE_REASONING_EFFORT
  e GROQ_JUDGE_TEMPERATURE do ambiente (carrega o .env se existir).
- Modos: simulated (só respostas gravadas em tests/fixtures/llm_responses), live (chamada real) e
  record (chamada real + gravação para o modo simulado).
- Papéis: "generation", "extraction" e "judge". O juiz usa GROQ_JUDGE_MODEL_ID, que deve ser diferente do
  modelo gerador (seção 4.7).
- Limitador de tokens por janela de 60 s, nova tentativa com espera crescente em 429 e falhas de rede.
- Saída inválida (JSON ou Pydantic) levanta InvalidLLMOutput sem novas tentativas internas: conta como
  falha da tentativa no loop de reflexão (seção 4.10).
- Teto de chamadas por cliente (GROQ_MAX_CALLS_PER_RUN) contra gasto descontrolado.
- Cache por prompt, modelo, schema e versões (em disco em CACHE_DIR nos modos live/record).
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, ValidationError

from .cache import VersionedCache
from .logging import get_logger

logger = get_logger("llm_client")

try:  # o .env é lido pelo docker compose; localmente, carregamos se existir
    from dotenv import load_dotenv

    load_dotenv(override=False)
except Exception:  # noqa: BLE001
    pass


class InvalidLLMOutput(ValueError):
    """Resposta fora do JSON ou do schema esperado (conta como falha da tentativa)."""


class SimulatedResponseMissing(FileNotFoundError):
    """Modo simulado sem resposta gravada para este prompt."""


class JsonModeRejected(RuntimeError):
    """O provedor recusou a resposta no modo JSON (400 json_validate_failed)."""


class LLMBudgetExceeded(RuntimeError):
    """Teto de chamadas do cliente atingido."""


class LLMConfigError(RuntimeError):
    """Configuração de modelos inválida (ex.: juiz igual ao gerador)."""


class LLMCallResult(BaseModel):
    """Structured result of a single LLM call."""

    response: Any
    usage: dict[str, int]
    latency_seconds: float
    model_id: str
    mode: str
    cache_hit: bool = False
    attempt: int = 1
    role: str = "generation"
    prompt_hash: str = ""


class LLMClient:
    """Groq-compatible LLM client with simulated/live/record modes."""

    def __init__(
        self,
        mode: Optional[str] = None,
        response_dir: str = "tests/fixtures/llm_responses",
        max_calls: Optional[int] = None,
    ) -> None:
        self.mode = mode or os.getenv("LLM_MODE", "simulated")
        if self.mode not in {"simulated", "live", "record"}:
            raise ValueError(f"Unsupported LLM mode: {self.mode}")

        self.response_dir = Path(response_dir)
        cache_dir = os.getenv("CACHE_DIR") if self.mode in {"live", "record"} else None
        self.cache = VersionedCache(Path(cache_dir) / "llm" if cache_dir else None)
        self.last_usage: dict[str, int] = {}
        self.last_latency_seconds: float = 0.0
        self.last_cache_hit: bool = False
        self.calls: list[dict[str, Any]] = []

        self.base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
        self.api_key = os.getenv("GROQ_API_KEY")
        self.default_model = os.getenv("GROQ_GENERATION_MODEL_ID") or "llama-3.3-70b-versatile"
        self.judge_model = os.getenv("GROQ_JUDGE_MODEL_ID") or None
        self.judge_reasoning_effort = os.getenv("GROQ_JUDGE_REASONING_EFFORT") or None
        self.judge_temperature = float(os.getenv("GROQ_JUDGE_TEMPERATURE", "0"))
        self.generation_temperature = float(os.getenv("GROQ_GENERATION_TEMPERATURE", "0.3"))
        self.generation_reasoning_effort = os.getenv("GROQ_GENERATION_REASONING_EFFORT", "low") or None
        self.max_completion_tokens = int(os.getenv("GROQ_MAX_COMPLETION_TOKENS", "0") or 0)

        self.token_budget = int(os.getenv("GROQ_TPM", "8000"))
        self._token_window: list[list[float]] = []  # [timestamp, tokens]
        self._window_lock = threading.Lock()

        self.max_retries = int(os.getenv("GROQ_MAX_RETRIES", "3"))
        # 429 (limite por minuto) costuma pedir 10–60 s de espera: mais tentativas, respeitando o tempo pedido
        self.max_retries_429 = int(os.getenv("GROQ_MAX_RETRIES_429", "6"))
        self.max_rate_limit_wait = float(os.getenv("GROQ_MAX_RATE_LIMIT_WAIT", "65"))
        # Limite opcional de tokens de SAÍDA por minuto (alguns modelos têm OTPM menor que o TPM)
        self.output_token_budget = int(os.getenv("GROQ_OTPM", "0") or 0)
        self._output_window: list[list[float]] = []
        self.base_retry_delay = float(os.getenv("GROQ_BASE_RETRY_DELAY", "2.0"))
        self.max_calls = max_calls if max_calls is not None else int(os.getenv("GROQ_MAX_CALLS_PER_RUN", "60"))

        if self.mode in {"live", "record"} and not self.api_key:
            raise RuntimeError(
                "GROQ_API_KEY is required for live or record mode. "
                "Set GROQ_API_KEY in your .env or use LLM_MODE=simulated."
            )

    # ------------------------------------------------------------------ modelos
    def model_for(self, role: str, model_id: Optional[str] = None) -> str:
        if model_id:
            return model_id
        if role == "judge":
            if not self.judge_model:
                raise LLMConfigError("GROQ_JUDGE_MODEL_ID não configurado: o juiz precisa de um modelo próprio.")
            return self.judge_model
        return self.default_model

    def assert_distinct_models(self) -> None:
        """Seção 4.7: o modelo do juiz é diferente do que gerou o texto."""
        judge = self.model_for("judge")
        if judge.lower() == self.default_model.lower():
            raise LLMConfigError(f"GROQ_JUDGE_MODEL_ID ({judge}) igual ao modelo gerador; configure modelos distintos.")

    # ------------------------------------------------------------ token budget
    def _reserve_tokens(self, estimated_tokens: int, window_name: str = "_token_window",
                        budget: int | None = None) -> list[float]:
        """Bloqueia até a estimativa caber na janela de 60 s e devolve a reserva (ajustada depois da chamada)."""
        budget = self.token_budget if budget is None else budget
        while True:
            with self._window_lock:
                now = time.time()
                window = [e for e in getattr(self, window_name) if now - e[0] <= 60]
                setattr(self, window_name, window)
                used = sum(e[1] for e in window)
                if used + estimated_tokens <= budget or not window:
                    entry = [now, float(estimated_tokens)]
                    window.append(entry)
                    return entry
                sleep_for = 60 - (now - window[0][0])
            time.sleep(min(max(sleep_for, 0.5), 10))

    def _settle_tokens(self, entry: list[float], actual_tokens: int) -> None:
        with self._window_lock:
            entry[1] = float(actual_tokens)

    # ------------------------------------------------------------ live call
    def _reasoning_effort(self, model_id: str, role: str) -> str | None:
        if role == "judge":
            return self.judge_reasoning_effort
        # gpt-oss raciocina antes de responder; esforço baixo na geração/extração reduz tokens e respostas vazias
        if model_id.lower().startswith("openai/gpt-oss"):
            return self.generation_reasoning_effort
        return None

    def _live_call(self, model_id: str, messages: list[dict], temperature: float, role: str,
                   json_mode: bool = True) -> tuple[str, dict[str, int], float]:
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        effort = self._reasoning_effort(model_id, role)
        if effort:
            payload["reasoning_effort"] = effort
        if self.max_completion_tokens:
            payload["max_completion_tokens"] = self.max_completion_tokens

        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                     "User-Agent": "CaseSunoLLMClient/2.0"},
            method="POST",
        )
        last_error: Optional[Exception] = None
        attempts = max(self.max_retries, self.max_retries_429)
        for retry in range(attempts):
            started = time.time()
            try:
                with urllib.request.urlopen(request, timeout=120) as http_response:
                    response = json.loads(http_response.read().decode("utf-8"))
                latency = time.time() - started
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                if exc.code == 400 and "json_validate_failed" in detail:
                    raise JsonModeRejected(f"Groq recusou a saída no modo JSON: {detail[:300]}") from exc
                last_error = RuntimeError(f"Groq request failed ({exc.code}): {detail}")
                if exc.code == 429 and retry < self.max_retries_429 - 1:
                    delay = self._rate_limit_delay(exc, detail, retry)
                    logger.warning("Rate limited (429), retrying in %.1fs", delay)
                    time.sleep(delay)
                    continue
                raise last_error
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last_error = RuntimeError(f"Groq connection failed: {exc}")
                if retry < self.max_retries - 1:
                    time.sleep(self.base_retry_delay * (2 ** retry))
                    continue
                raise last_error
        else:
            raise last_error or RuntimeError("Groq client did not receive a response")

        text = ((response.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        usage_raw = response.get("usage") or {}
        prompt_words = sum(len(m["content"].split()) for m in messages)
        usage = {
            "prompt_tokens": int(usage_raw.get("prompt_tokens") or prompt_words),
            "completion_tokens": int(usage_raw.get("completion_tokens") or len(text.split())),
        }
        usage["total_tokens"] = int(usage_raw.get("total_tokens") or usage["prompt_tokens"] + usage["completion_tokens"])
        return text, usage, latency

    # -------------------------------------------------------------- generate
    def generate(
        self,
        prompt: str,
        schema_name: str = "text",
        model_id: Optional[str] = None,
        temperature: Optional[float] = None,
        cache_parts: Optional[Dict[str, Any]] = None,
        pydantic_schema: Optional[type[BaseModel]] = None,
        system: Optional[str] = None,
        role: str = "generation",
    ) -> LLMCallResult:
        """Executa uma chamada (ou devolve do cache/gravação) e valida o JSON.

        Raises:
            InvalidLLMOutput: JSON inválido ou fora do schema (falha da tentativa, sem nova tentativa aqui).
            SimulatedResponseMissing: modo simulado sem resposta gravada.
            LLMBudgetExceeded: teto de chamadas do cliente atingido.
        """
        cache_parts = cache_parts or {}
        effective_model = self.model_for(role, model_id)
        if temperature is None:
            temperature = self.judge_temperature if role == "judge" else self.generation_temperature
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        prompt_hash = self.hash_prompt(json.dumps(messages, ensure_ascii=False))
        key = self.cache.build_key(prompt if not system else [system, prompt], effective_model, schema_name, cache_parts)

        cached = self.cache.get(key)
        if cached is not None:
            self.last_usage, self.last_latency_seconds, self.last_cache_hit = {"total_tokens": 0}, 0.0, True
            self._log_call(role, effective_model, {"total_tokens": 0}, 0.0, True, prompt_hash)
            parsed = self._validate(cached, pydantic_schema)
            return LLMCallResult(response=parsed, usage=self.last_usage, latency_seconds=0.0, model_id=effective_model,
                                 mode=self.mode, cache_hit=True, role=role, prompt_hash=prompt_hash)

        self.last_cache_hit = False
        if len([c for c in self.calls if not c["cache_hit"]]) >= self.max_calls:
            raise LLMBudgetExceeded(f"Teto de {self.max_calls} chamadas ao modelo atingido nesta execução.")

        if self.mode == "simulated":
            raw = self._load_simulated_response(key)
            if isinstance(raw, dict) and "response" in raw:
                usage = dict(raw.get("usage", {}))
                result = raw["response"]
            else:
                usage = {"total_tokens": 0}
                result = raw
            self.last_usage, self.last_latency_seconds = usage, 0.0
            self._log_call(role, effective_model, usage, 0.0, False, prompt_hash)
            parsed = self._validate(result, pydantic_schema)
            self.cache.set(key, result)
            return LLMCallResult(response=parsed, usage=usage, latency_seconds=0.0, model_id=effective_model,
                                 mode=self.mode, role=role, prompt_hash=prompt_hash)

        estimated = sum(len(m["content"].split()) for m in messages) + int(os.getenv("GROQ_ESTIMATED_OUTPUT_TOKENS", "1200"))
        reservation = self._reserve_tokens(estimated)
        output_reservation = None
        if self.output_token_budget:
            output_estimate = min(int(os.getenv("GROQ_ESTIMATED_OUTPUT_TOKENS", "1200")), self.output_token_budget)
            output_reservation = self._reserve_tokens(output_estimate, "_output_window", self.output_token_budget)
        try:
            try:
                text, usage, latency = self._live_call(effective_model, messages, temperature, role)
            except JsonModeRejected as exc:
                # repete uma vez sem o modo JSON do servidor: o JSON é extraído e validado localmente
                logger.warning("%s — repetindo sem response_format", exc)
                text, usage, latency = self._live_call(effective_model, messages, temperature, role, json_mode=False)
        except Exception:
            self._settle_tokens(reservation, 0)
            if output_reservation is not None:
                self._settle_tokens(output_reservation, 0)
            raise
        self._settle_tokens(reservation, usage["total_tokens"])
        if output_reservation is not None:
            self._settle_tokens(output_reservation, usage.get("completion_tokens", 0))
        self.last_usage, self.last_latency_seconds = usage, latency
        self._log_call(role, effective_model, usage, latency, False, prompt_hash)
        try:
            raw = json.loads(self._strip_reasoning(text))
        except json.JSONDecodeError as exc:
            raise InvalidLLMOutput(f"Resposta não é JSON válido: {exc}") from exc
        parsed = self._validate(raw, pydantic_schema)
        if self.mode == "record":
            self._save_recorded_response(key, raw, usage)
        self.cache.set(key, raw)
        return LLMCallResult(response=parsed, usage=usage, latency_seconds=latency, model_id=effective_model,
                             mode=self.mode, role=role, prompt_hash=prompt_hash)

    # ------------------------------------------------------------ helpers
    def _rate_limit_delay(self, exc: Any, detail: str, retry: int) -> float:
        """Espera pedida pelo provedor (cabeçalho retry-after ou 'try again in 20.82s'); senão, espera crescente."""
        import re

        wait = None
        header = getattr(exc, "headers", None)
        if header is not None and header.get("retry-after"):
            try:
                wait = float(header.get("retry-after"))
            except ValueError:
                wait = None
        if wait is None:
            match = re.search(r"try again in (?:(\d+)m)?([\d.]+)(ms|s)", detail)
            if match:
                minutes = float(match.group(1) or 0)
                value = float(match.group(2))
                wait = minutes * 60 + (value / 1000 if match.group(3) == "ms" else value)
        if wait is None:
            wait = self.base_retry_delay * (2 ** retry)
        return min(self.max_rate_limit_wait, wait + 0.5)

    @staticmethod
    def _strip_reasoning(text: str) -> str:
        """Remove bloco de raciocínio (<think>…</think>) e cercas ```json que alguns modelos põem antes do JSON."""
        import re

        cleaned = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
        return fenced.group(1) if fenced else cleaned

    @staticmethod
    def _validate(raw: Any, schema: Optional[type[BaseModel]]) -> Any:
        if schema is None:
            return raw
        try:
            schema.model_validate(raw)
        except ValidationError as exc:
            raise InvalidLLMOutput(f"Resposta fora do schema {schema.__name__}: {exc}") from exc
        return raw

    def _log_call(self, role: str, model: str, usage: dict, latency: float, cache_hit: bool, prompt_hash: str) -> None:
        self.calls.append({"role": role, "model_id": model, "total_tokens": int(usage.get("total_tokens", 0)),
                           "latency_seconds": latency, "cache_hit": cache_hit, "prompt_hash": prompt_hash,
                           "timestamp": time.time()})

    def _load_simulated_response(self, key: str) -> Any:
        path = self.response_dir / (key + ".json")
        if not path.exists():
            raise SimulatedResponseMissing(
                f"Modo simulado sem resposta gravada ({path}). Grave as respostas com LLM_MODE=record "
                f"(chama o Groq) ou injete um cliente de teste."
            )
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _save_recorded_response(self, key: str, response: Any, usage: dict[str, int]) -> None:
        path = self.response_dir / (key + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump({"response": response, "usage": usage}, file, ensure_ascii=False, indent=2)

    @staticmethod
    def hash_prompt(prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    @property
    def usage(self) -> dict[str, int]:
        return dict(self.last_usage)

    @property
    def latency(self) -> float:
        return self.last_latency_seconds

    @property
    def cache_hit(self) -> bool:
        return self.last_cache_hit
