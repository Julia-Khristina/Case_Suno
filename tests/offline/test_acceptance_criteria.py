from pathlib import Path

import pytest

from src.evaluation.offline_metrics import acceptance_checklist


@pytest.mark.offline
def test_acceptance_checklist_files_exist():
    checks = acceptance_checklist()
    assert checks
    assert all(ok for _, ok in checks), checks


@pytest.mark.offline
def test_reference_days_minimum():
    root = Path(__file__).resolve().parents[2]
    reference_days = list((root / "data" / "reference_days").glob("dia_*.json"))
    assert len(reference_days) >= 12


@pytest.mark.offline
def test_required_configuration_files():
    root = Path(__file__).resolve().parents[2]
    for name in ["glossario.yaml", "limiares.yaml", "guia_estilo.yaml", "estrutura_texto.yaml", "coleta_fontes.yaml"]:
        assert (root / "config" / name).exists(), name