"""Suíte offline (seções 4.7 e 14): ponta a ponta nos 3 níveis com cliente falso, matriz de confusão e custo."""
from __future__ import annotations

import pytest

from src.evaluation.deterministic import EvaluationContext, evaluate
from src.evaluation.offline_metrics import build_confusion_matrix
from src.evaluation.thresholds import load_thresholds
from src.generation import rules
from src.glossary.reader import load_glossary
from src.pipeline.deps import PipelineDeps
from src.pipeline.graph import run_pipeline
from src.pipeline.persistence import InMemoryPersistence
from tests.fakes import content
from tests.fakes.llm import FakeLLMClient


def _syllable_soup(count: int) -> str:
    vowels, consonants = "aeiou", "bcdfghjklmnpqrstvwxyz"
    return " ".join(f"{vowels[i % 5]}{consonants[(i // 5) % 21]}." for i in range(count))


@pytest.mark.offline
def test_meaningless_text_no_longer_passes_the_gates():
    """Regressão: o teste antigo aprovava 400 'palavras' sem sentido ("ab. eb. ib.") como Iniciante."""
    soup = {"title": "Titulo", "subtitle": "Subtitulo", "fonte_bloco": rules.source_block(content.ORIGIN),
            "caixa_entenda_os_termos": None}
    for name, n in (("introduction", 60), ("development", 140), ("analysis", 120), ("conclusion", 80)):
        soup[name] = {"title": name, "content": _syllable_soup(n) + " Ponto central.", "ponto_ids": ["p1"]}
    ctx = EvaluationContext(level="iniciante", fmt="texto_analitico", source_text=content.SOURCE,
                            glossary=load_glossary(), thresholds=load_thresholds(),
                            main_points=[{"id": "p1", "title": "Copom mantém a Selic em 10,50% ao ano", "assertions": []}],
                            origin=content.ORIGIN)
    report = evaluate(soup, ctx)
    assert not report.passed
    assert {"frases_repetidas", "cobertura_de_pontos_centrais_insuficiente"} & set(report.failure_codes)


@pytest.mark.offline
def test_offline_suite_three_levels_confusion_matrix_and_cost():
    client = FakeLLMClient(responses={
        "intermediario:carrossel": [content.good_output("carrossel", "iniciante")],
        "avancado:carrossel": [content.good_output("carrossel", "iniciante")],
    })
    persistence = InMemoryPersistence()
    final = run_pipeline(content.SOURCE, ["iniciante", "intermediario", "avancado"], origin=content.ORIGIN,
                         deps=PipelineDeps(llm_client=client, persistence=persistence))
    outputs = final["generated_outputs"]
    assert len(outputs) == 9

    texts = {k: v for k, v in outputs.items() if v["formato"] == "texto_analitico"}
    targets = [v["nivel"] for v in texts.values()]
    predicted = [v["nivel_classificado"] for v in texts.values()]
    matrix = build_confusion_matrix(targets, predicted, labels=["iniciante", "intermediario", "avancado", "indistinto"])
    for level in ("iniciante", "intermediario", "avancado"):
        assert matrix["matrix"][level][level] == 1  # textos bons classificados no nível-alvo

    # carrossel Iniciante entregue como Avançado: nível não atendido, reescrito até o teto e marcado para revisão
    assert outputs["avancado:carrossel"]["status"] == "reprovado_nas_metricas"
    assert outputs["avancado:carrossel"]["aviso"]

    # custo e latência por chamada registrados e somados
    assert final["token_count"] == len(client.calls) * client.tokens_per_call
    assert persistence.executions[final["execution_id"]]["total_tokens"] == final["token_count"]
