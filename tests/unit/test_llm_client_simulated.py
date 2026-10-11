import json

from src.shared.llm_client import LLMClient


def test_simulated_mode_reads_recorded_response(tmp_path):
    client = LLMClient(mode="simulated", response_dir=str(tmp_path))
    prompt = "hello"
    key = client.cache.build_key(prompt, None, "text", {})
    (tmp_path / f"{key}.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    first = client.generate(prompt, schema_name="text")
    second = client.generate(prompt, schema_name="text")

    assert first == {"ok": True}
    assert second == {"ok": True}


def test_simulated_mode_raises_for_missing_response(tmp_path):
    client = LLMClient(mode="simulated", response_dir=str(tmp_path))
    try:
        client.generate("missing", schema_name="text")
    except FileNotFoundError:
        return
    raise AssertionError("FileNotFoundError expected")