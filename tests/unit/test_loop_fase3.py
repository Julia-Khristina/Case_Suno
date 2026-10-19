"""Loop de reflexão (seções 4.7 e 4.10) executando os nós reais: teto, feedback numérico, diff entre tentativas."""
from __future__ import annotations

from src.extraction.models import ExtractionResult
from src.pipeline.deps import PipelineDeps
from src.pipeline.nodes.evaluate_deterministic import change_metrics
from src.pipeline.reflection import run_analytical_reflection, run_reflection_loop
from tests.fakes import content
from tests.fakes.llm import FakeLLMClient

from src.extraction.extractor import Extractor  # noqa: E402

EXTRACTION: ExtractionResult = Extractor(llm_client=FakeLLMClient()).extract(content.SOURCE)


def _loop(client, level="iniciante", fmt="texto_analitico"):
    return run_reflection_loop(EXTRACTION, level, fmt, content.SOURCE, origin=content.ORIGIN,
                               deps=PipelineDeps(llm_client=client))


def _hard_beginner_text():
    """Iniciante "difícil demais": o texto Avançado entregue como Iniciante (reprova por legibilidade e jargão)."""
    return content.good_output("texto_analitico", "avancado")


def test_approved_on_first_attempt():
    result = _loop(FakeLLMClient())
    assert result["passou"] is True
    assert result["tentativas"] == 1
    assert result["avaliacao_juiz"]["aprovado"] is True


def test_beginner_too_hard_is_rewritten_with_numeric_feedback_and_approved():
    """Critério de aceitação (seção 14): Iniciante reprovado por legibilidade, reescrito com feedback numérico
    e aprovado em até duas reescritas."""
    client = FakeLLMClient(responses={"iniciante:texto_analitico": [_hard_beginner_text(),
                                                                    content.good_output("texto_analitico", "iniciante")]})
    result = _loop(client)
    first = result["historico"][0]
    assert first["avaliacao"] == "deterministica" and not first["passou"]
    codes = [f["code"] for f in first["falhas"]]
    assert "legibilidade_fora_da_faixa" in codes
    feedback = client.prompts[1]["prompt"]
    assert "legibilidade_fora_da_faixa: flesch_ptbr=" in feedback and "limiar=>= 55" in feedback
    assert result["passou"] is True and result["tentativas"] == 2


def test_exhausts_after_two_rewrites_with_warning():
    swapped = _hard_beginner_text()
    swapped["introduction"], swapped["conclusion"] = swapped["conclusion"], swapped["introduction"]
    swapped["development"], swapped["analysis"] = swapped["analysis"], swapped["development"]
    variants = [_hard_beginner_text(), content.good_output("texto_analitico", "intermediario"), swapped]
    client = FakeLLMClient(responses={"iniciante:texto_analitico": variants})
    result = _loop(client)
    assert result["tentativas"] == 3
    assert result["esgotado"] is True
    assert "Limite de reescritas" in result["aviso"]
    assert len([c for c in client.calls if c["schema"] == "analytical_text"]) == 3


def test_identical_rewrite_is_blocked():
    client = FakeLLMClient(responses={"iniciante:texto_analitico": [_hard_beginner_text()]})
    result = _loop(client)
    assert result["tentativas"] == 2
    assert result["historico"][1]["mudanca_vs_anterior"] == 1.0
    assert "repetiu a anterior" in result["aviso"]


def test_change_metrics_detect_append_only_rewrite():
    base = "O Copom manteve a Selic em 10,50%. A inflação segue acima da meta de 3%."
    padded = base + " A inflação segue acima da meta. O comitê segue atento."
    metrics = change_metrics(base, padded)
    assert metrics["apenas_acrescentou"] is True
    assert change_metrics(base, "Texto completamente diferente sobre outro tema financeiro relevante.")["apenas_acrescentou"] is False


def test_carousel_and_script_also_get_feedback():
    bad = content.good_output("carrossel", "iniciante")
    bad["slides"][2]["body"] = bad["slides"][1]["body"]
    bad["slides"][3]["body"] = bad["slides"][1]["body"]
    client = FakeLLMClient(responses={"iniciante:carrossel": [bad, content.good_output("carrossel", "iniciante")]})
    result = _loop(client, fmt="carrossel")
    assert "slides_repetidos" in client.prompts[1]["prompt"]
    assert result["passou"] is True


def test_compat_wrapper_returns_content_evaluation_and_attempts():
    text, evaluation, attempts = run_analytical_reflection(EXTRACTION, "iniciante", content.SOURCE, FakeLLMClient(),
                                                           origin=content.ORIGIN)
    assert attempts == 1 and evaluation["passed"] is True and text["title"]
