"""Testes do LLMClient: modos, validação, juiz com modelo próprio, limitador de tokens, teto de chamadas, cache."""
from __future__ import annotations

import json
import time
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from src.shared.llm_client import (
    InvalidLLMOutput,
    LLMBudgetExceeded,
    LLMCallResult,
    LLMClient,
    LLMConfigError,
    SimulatedResponseMissing,
)


class _TestSchema(BaseModel):
    titulo: str
    valor: int


@pytest.fixture
def env(monkeypatch):
    def apply(**values):
        for key, value in values.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, str(value))
    monkeypatch.setenv("CACHE_DIR", "")
    return apply


def _record(tmp_path, client, prompt, response, schema="text", system=None, extra=None):
    key = client.cache.build_key(prompt if not system else [system, prompt], client.default_model, schema, extra or {})
    (tmp_path / f"{key}.json").write_text(json.dumps({"response": response, "usage": {"total_tokens": 10}}), encoding="utf-8")


class TestModes:
    def test_simulated_returns_recorded_response(self, tmp_path):
        client = LLMClient(mode="simulated", response_dir=str(tmp_path))
        _record(tmp_path, client, "test prompt", {"ok": True})
        result = client.generate("test prompt", schema_name="text")
        assert isinstance(result, LLMCallResult)
        assert result.response == {"ok": True}
        assert result.cache_hit is False

    def test_simulated_cache_hit_on_second_call(self, tmp_path):
        client = LLMClient(mode="simulated", response_dir=str(tmp_path))
        _record(tmp_path, client, "cache test", {"ok": True})
        assert client.generate("cache test").cache_hit is False
        assert client.generate("cache test").cache_hit is True

    def test_simulated_missing_response_raises_clear_error(self, tmp_path):
        client = LLMClient(mode="simulated", response_dir=str(tmp_path))
        with pytest.raises(SimulatedResponseMissing) as exc:
            client.generate("nonexistent", schema_name="text")
        assert "LLM_MODE=record" in str(exc.value)

    def test_system_message_is_part_of_the_key(self, tmp_path):
        client = LLMClient(mode="simulated", response_dir=str(tmp_path))
        _record(tmp_path, client, "p", {"ok": 1}, system="sys")
        assert client.generate("p", system="sys").response == {"ok": 1}
        with pytest.raises(SimulatedResponseMissing):
            client.generate("p", system="outro sistema")

    @pytest.mark.parametrize("mode", ["live", "record"])
    def test_live_and_record_without_api_key_raise(self, monkeypatch, mode):
        monkeypatch.setenv("GROQ_API_KEY", "")
        with pytest.raises(RuntimeError) as exc:
            LLMClient(mode=mode)
        assert "GROQ_API_KEY" in str(exc.value)


class TestValidation:
    def test_valid_response_passes(self, tmp_path):
        client = LLMClient(mode="simulated", response_dir=str(tmp_path))
        _record(tmp_path, client, "ok", {"titulo": "X", "valor": 42}, schema="test")
        assert client.generate("ok", schema_name="test", pydantic_schema=_TestSchema).response["valor"] == 42

    def test_invalid_response_is_attempt_failure_without_hidden_retries(self, tmp_path, env):
        env(GROQ_API_KEY="k", GROQ_TPM="100000")
        client = LLMClient(mode="live", response_dir=str(tmp_path))
        with patch.object(client, "_live_call", return_value=('{"titulo": "X", "valor": "x"}', {"total_tokens": 5}, 0.1)) as call:
            with pytest.raises(InvalidLLMOutput):
                client.generate("p", schema_name="test", pydantic_schema=_TestSchema)
        assert call.call_count == 1  # a reescrita é decisão do loop de reflexão, não do cliente

    def test_reasoning_block_and_code_fence_are_stripped(self, tmp_path, env):
        env(GROQ_API_KEY="k", GROQ_TPM="100000")
        client = LLMClient(mode="live", response_dir=str(tmp_path))
        raw = '<think>vou pensar</think>\n```json\n{"titulo": "X", "valor": 1}\n```'
        with patch.object(client, "_live_call", return_value=(raw, {"total_tokens": 5}, 0.1)):
            assert client.generate("p", schema_name="test", pydantic_schema=_TestSchema).response["valor"] == 1

    def test_non_json_response_is_invalid_output(self, tmp_path, env):
        env(GROQ_API_KEY="k", GROQ_TPM="100000")
        client = LLMClient(mode="live", response_dir=str(tmp_path))
        with patch.object(client, "_live_call", return_value=("isto não é json", {"total_tokens": 5}, 0.1)):
            with pytest.raises(InvalidLLMOutput):
                client.generate("p")


class TestJudgeModel:
    def test_judge_uses_its_own_model_and_reasoning_effort(self, tmp_path, env):
        env(GROQ_API_KEY="k", GROQ_TPM="100000", GROQ_GENERATION_MODEL_ID="gen-model",
            GROQ_JUDGE_MODEL_ID="judge-model", GROQ_JUDGE_REASONING_EFFORT="medium", GROQ_JUDGE_TEMPERATURE="0")
        client = LLMClient(mode="live", response_dir=str(tmp_path))
        with patch("urllib.request.urlopen") as urlopen:
            body = json.dumps({"choices": [{"message": {"content": "{}"}}], "usage": {"total_tokens": 3}}).encode()
            urlopen.return_value.__enter__.return_value.read.return_value = body
            client.generate("avalie", schema_name="judge", role="judge")
            payload = json.loads(urlopen.call_args[0][0].data)
        assert payload["model"] == "judge-model"
        assert payload["reasoning_effort"] == "medium"
        assert payload["temperature"] == 0

    def test_generation_does_not_send_reasoning_effort(self, tmp_path, env):
        env(GROQ_API_KEY="k", GROQ_TPM="100000", GROQ_GENERATION_MODEL_ID="gen-model",
            GROQ_JUDGE_MODEL_ID="judge-model", GROQ_JUDGE_REASONING_EFFORT="medium")
        client = LLMClient(mode="live", response_dir=str(tmp_path))
        with patch("urllib.request.urlopen") as urlopen:
            body = json.dumps({"choices": [{"message": {"content": "{}"}}], "usage": {"total_tokens": 3}}).encode()
            urlopen.return_value.__enter__.return_value.read.return_value = body
            client.generate("gere", system="sys")
            payload = json.loads(urlopen.call_args[0][0].data)
        assert payload["model"] == "gen-model"
        assert "reasoning_effort" not in payload
        assert payload["messages"][0] == {"role": "system", "content": "sys"}

    def test_same_model_for_judge_and_generator_is_rejected(self, env):
        env(GROQ_GENERATION_MODEL_ID="mesmo", GROQ_JUDGE_MODEL_ID="mesmo")
        with pytest.raises(LLMConfigError):
            LLMClient(mode="simulated").assert_distinct_models()

    def test_missing_judge_model_is_config_error(self, env):
        env(GROQ_JUDGE_MODEL_ID=None)
        with pytest.raises(LLMConfigError):
            LLMClient(mode="simulated").model_for("judge")


class TestTokenBudget:
    def test_usage_comes_from_provider(self, tmp_path, env):
        env(GROQ_API_KEY="k", GROQ_TPM="100000")
        client = LLMClient(mode="live", response_dir=str(tmp_path))
        with patch.object(client, "_live_call", return_value=("{}", {"prompt_tokens": 100, "completion_tokens": 50,
                                                                     "total_tokens": 150}, 0.2)):
            result = client.generate("test")
        assert result.usage["total_tokens"] == 150
        assert result.latency_seconds == 0.2

    def test_reservation_is_replaced_by_actual_usage(self, tmp_path, env):
        env(GROQ_API_KEY="k", GROQ_TPM="100000", GROQ_ESTIMATED_OUTPUT_TOKENS="1000")
        client = LLMClient(mode="live", response_dir=str(tmp_path))
        with patch.object(client, "_live_call", return_value=("{}", {"total_tokens": 2}, 0.1)):
            client.generate("a")
        now = time.time()
        used = sum(n for t, n in client._token_window if now - t <= 60)
        assert used == 2  # a estimativa (1001) não fica somada ao uso real (bug da versão anterior)


class TestRateLimit:
    def test_wait_follows_provider_message(self, tmp_path, env):
        env(GROQ_API_KEY="k")
        client = LLMClient(mode="live", response_dir=str(tmp_path))
        detail = '{"error":{"message":"Rate limit reached ... Please try again in 20.82s. Need more tokens?"}}'
        assert client._rate_limit_delay(None, detail, 0) == pytest.approx(21.32)
        assert client._rate_limit_delay(None, "try again in 1m5.5s", 0) == 65  # limitado a GROQ_MAX_RATE_LIMIT_WAIT
        assert client._rate_limit_delay(None, "try again in 577ms", 0) == pytest.approx(1.077)

    def test_429_is_retried_until_success(self, tmp_path, env, monkeypatch):
        import io
        import urllib.error

        env(GROQ_API_KEY="k", GROQ_TPM="100000")
        client = LLMClient(mode="live", response_dir=str(tmp_path))
        sleeps = []
        monkeypatch.setattr("src.shared.llm_client.time.sleep", lambda s: sleeps.append(s))
        body = json.dumps({"choices": [{"message": {"content": "{}"}}], "usage": {"total_tokens": 3}}).encode()
        ok = type("R", (), {"__enter__": lambda s: s, "__exit__": lambda s, *a: False, "read": lambda s: body})()
        def error():
            return urllib.error.HTTPError("u", 429, "rate", {}, io.BytesIO(b"Please try again in 2.5s"))
        calls = iter([error(), error(), ok])

        def fake_urlopen(*_a, **_k):
            item = next(calls)
            if isinstance(item, Exception):
                raise item
            return item
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        assert client.generate("p").response == {}
        assert sleeps == [3.0, 3.0]

    def test_output_tokens_per_minute_budget_is_tracked(self, tmp_path, env):
        env(GROQ_API_KEY="k", GROQ_TPM="100000", GROQ_OTPM="1000", GROQ_ESTIMATED_OUTPUT_TOKENS="1200")
        client = LLMClient(mode="live", response_dir=str(tmp_path))
        with patch.object(client, "_live_call", return_value=("{}", {"completion_tokens": 400, "total_tokens": 900}, 0.1)):
            client.generate("a")
        assert sum(n for _t, n in client._output_window) == 400


class TestJsonModeFallback:
    @staticmethod
    def _urlopen_sequence(monkeypatch, items):
        import io
        import urllib.error

        payloads = []
        iterator = iter(items)

        def fake_urlopen(request, *_a, **_k):
            payloads.append(json.loads(request.data))
            item = next(iterator)
            if isinstance(item, int):
                raise urllib.error.HTTPError("u", item, "bad", {}, io.BytesIO(
                    b'{"error":{"code":"json_validate_failed","failed_generation":""}}'))
            body = json.dumps({"choices": [{"message": {"content": item}}], "usage": {"total_tokens": 3}}).encode()
            return type("R", (), {"__enter__": lambda s: s, "__exit__": lambda s, *a: False, "read": lambda s: body})()
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        return payloads

    def test_json_validate_failed_retries_once_without_response_format(self, tmp_path, env, monkeypatch):
        env(GROQ_API_KEY="k", GROQ_TPM="100000")
        client = LLMClient(mode="live", response_dir=str(tmp_path))
        payloads = self._urlopen_sequence(monkeypatch, [400, '```json\n{"titulo": "X", "valor": 2}\n```'])
        result = client.generate("p", schema_name="test", pydantic_schema=_TestSchema)
        assert result.response["valor"] == 2
        assert "response_format" in payloads[0] and "response_format" not in payloads[1]

    def test_gpt_oss_generation_uses_low_reasoning_effort(self, tmp_path, env, monkeypatch):
        env(GROQ_API_KEY="k", GROQ_TPM="100000", GROQ_GENERATION_MODEL_ID="openai/gpt-oss-20b",
            GROQ_JUDGE_MODEL_ID="openai/gpt-oss-120b", GROQ_JUDGE_REASONING_EFFORT="medium",
            GROQ_GENERATION_REASONING_EFFORT=None)
        client = LLMClient(mode="live", response_dir=str(tmp_path))
        payloads = self._urlopen_sequence(monkeypatch, ["{}", "{}"])
        client.generate("gerar")
        client.generate("julgar", role="judge")
        assert payloads[0]["reasoning_effort"] == "low"
        assert payloads[1]["reasoning_effort"] == "medium" and payloads[1]["model"] == "openai/gpt-oss-120b"


class TestCallCeiling:
    def test_client_stops_after_max_calls(self, tmp_path, env):
        env(GROQ_API_KEY="k", GROQ_TPM="100000")
        client = LLMClient(mode="live", response_dir=str(tmp_path), max_calls=2)
        with patch.object(client, "_live_call", return_value=("{}", {"total_tokens": 1}, 0.0)):
            client.generate("1")
            client.generate("2")
            with pytest.raises(LLMBudgetExceeded):
                client.generate("3")


class TestCacheKey:
    def test_cache_key_includes_model_and_versions(self):
        client = LLMClient()
        key1 = client.cache.build_key("prompt A", "model-1", "schema", {"v": "1"})
        assert key1 != client.cache.build_key("prompt A", "model-2", "schema", {"v": "1"})
        assert key1 != client.cache.build_key("prompt A", "model-1", "schema", {"v": "2"})
        assert key1 == client.cache.build_key("prompt A", "model-1", "schema", {"v": "1"})
