import json

from src.shared.llm_client import LLMClient, LLMCallResult


def test_simulated_mode_reads_recorded_response(tmp_path):
    client = LLMClient(mode="simulated", response_dir=str(tmp_path))
    prompt = "hello"
    # generate() uses effective_model (default_model when model_id is None) for the cache key
    key = client.cache.build_key(prompt, client.default_model, "text", {})
    (tmp_path / f"{key}.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    first = client.generate(prompt, schema_name="text")
    second = client.generate(prompt, schema_name="text")

    assert isinstance(first, LLMCallResult)
    assert first.response == {"ok": True}
    assert first.cache_hit is False
    assert second.response == {"ok": True}
    assert second.cache_hit is True


def test_simulated_mode_raises_for_missing_response(tmp_path):
    client = LLMClient(mode="simulated", response_dir=str(tmp_path))
    try:
        client.generate("missing", schema_name="text")
    except FileNotFoundError:
        return
    raise AssertionError("FileNotFoundError expected")


def test_live_mode_without_api_key_raises_clear_error(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("LLM_MODE", "live")
    try:
        LLMClient(mode="live")
    except RuntimeError as exc:
        assert "GROQ_API_KEY" in str(exc)
        return
    raise AssertionError("RuntimeError expected for live mode without API key")