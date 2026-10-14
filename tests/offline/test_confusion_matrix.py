import pytest

from src.evaluation.offline_metrics import build_confusion_matrix, f1_for, precision_for, recall_for


@pytest.mark.offline
def test_confusion_matrix_structure():
    actual = ["iniciante", "intermediario", "avancado", "iniciante"]
    predicted = ["iniciante", "iniciante", "avancado", "iniciante"]
    matrix = build_confusion_matrix(actual, predicted)
    assert matrix["labels"] == ["avancado", "iniciante", "intermediario"]
    assert matrix["matrix"]["iniciante"]["iniciante"] == 2
    assert precision_for(matrix, "iniciante") == 2 / 3
    assert recall_for(matrix, "iniciante") == 1.0
    assert f1_for(matrix, "avancado") == 1.0