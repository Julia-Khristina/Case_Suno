from src.evaluation.concordance import decision_agreement, length_score_correlation

def test_decision_agreement():
    assert decision_agreement(["aprovar", "editar"], ["aprovar", "editar"]) == 1.0
    assert decision_agreement(["aprovar", "editar"], ["aprovar", "rejeitar"]) == 0.5

def test_length_score_correlation():
    assert abs(length_score_correlation([100, 200, 300], [5, 6, 7]) - 1.0) < 1e-9
    assert length_score_correlation([100, 100], [5, 6]) == 0.0