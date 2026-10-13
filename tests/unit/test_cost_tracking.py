from src.evaluation.cost import CostRecord, CostTracker

def test_cost_tracker_totals():
    tracker = CostTracker()
    tracker.add(CostRecord(model_id="generator", prompt_tokens=100, completion_tokens=50, latency_ms=120))
    tracker.add(CostRecord(model_id="judge", prompt_tokens=40, completion_tokens=20, latency_ms=40))
    assert tracker.total_tokens() == 210
    assert tracker.total_latency_ms() == 160
    assert tracker.by_model() == {"generator": 150, "judge": 60}