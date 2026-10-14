import pytest

from src.evaluation.cost import CostRecord, CostTracker


@pytest.mark.offline
def test_cost_and_latency_offline():
    tracker = CostTracker()
    tracker.add(CostRecord(model_id="generator", prompt_tokens=200, completion_tokens=100, latency_ms=200))
    tracker.add(CostRecord(model_id="judge", prompt_tokens=80, completion_tokens=40, latency_ms=80))
    assert tracker.total_tokens() == 420
    assert tracker.total_latency_ms() == 280
    assert tracker.by_model()["generator"] == 300