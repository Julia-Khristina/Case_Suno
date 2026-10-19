"""O relatório experimental do README é gerado por script; o benchmark roda sem banco e sem LLM."""
import pytest

from scripts.relatorio_experimental import LEVELS, benchmark, matrix_md, summarize
from src.evaluation.thresholds import load_thresholds
from src.glossary.reader import load_glossary


@pytest.mark.offline
def test_benchmark_classifies_good_outputs_at_their_level_and_level_swaps_as_indistinct():
    result = benchmark(load_glossary(), load_thresholds())
    rows = {r["id"]: r for r in result["casos"] if r["caso_de_nivel"]}
    for good in ("g1_iniciante", "g2_intermediario", "g3_avancado"):
        assert rows[good]["classificado"] == rows[good]["esperado"]
    # nível trocado não vira "outro nível": cai em indistinto, que reprova no gate do nível pedido
    assert rows["b08_iniciante_jargao_sem_explicacao"]["classificado"] == "indistinto"
    assert rows["b09_avancado_sem_jargao"]["classificado"] == "indistinto"
    assert result["resumo_casos_de_nivel"]["n"] == 5


@pytest.mark.offline
def test_precision_is_undefined_when_a_level_is_never_predicted():
    summary = summarize(["iniciante", "avancado"], ["iniciante", "indistinto"])
    assert summary["por_nivel"]["avancado"]["precisao"] is None
    assert summary["por_nivel"]["iniciante"]["precisao"] == 1.0
    table = matrix_md(summary)
    assert "Avançado —" in table and all(level.capitalize()[:3] in table for level in LEVELS)
