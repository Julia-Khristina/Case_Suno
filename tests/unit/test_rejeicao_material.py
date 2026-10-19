"""Rejeição de material (decisão de 18/10/2026): motivo obrigatório e gravado, nova versão só do nível e formato
rejeitados, na mesma execução, com o motivo levado a todas as tentativas; resumo da revisão no painel."""
from __future__ import annotations

from src.app.dashboard import review_summary
from src.pipeline.deps import PipelineDeps
from src.pipeline.graph import run_pipeline
from src.pipeline.nodes.generate import combined_feedback
from src.pipeline.nodes.human_validation import rejection_note
from src.pipeline.persistence import InMemoryPersistence
from tests.fakes import content
from tests.fakes.llm import FakeLLMClient

REASON = "[Erro factual] O texto diz que a Selic subiu, mas a fonte diz que foi mantida."


def test_rejection_note_keeps_categories_and_free_text():
    assert rejection_note(["Erro factual", "Nível errado"], " Selic errada ") == "[Erro factual; Nível errado] Selic errada"
    assert rejection_note([], "Só texto") == "Só texto"


def test_human_reason_goes_before_the_automatic_feedback_and_survives_rewrites():
    assert combined_feedback(None, "faltou o ponto 2") == "faltou o ponto 2"
    first = combined_feedback(REASON, None)
    assert first.startswith("REVISÃO HUMANA") and REASON in first and "não acrescente nada" in first
    rewrite = combined_feedback(REASON, "palavras: 120 (faixa 350-500)")
    assert rewrite.index(REASON) < rewrite.index("palavras: 120")


def test_regeneration_runs_only_the_rejected_combo_inside_the_original_execution():
    persistence = InMemoryPersistence()
    client = FakeLLMClient()
    deps = PipelineDeps(llm_client=client, persistence=persistence)
    original = run_pipeline(content.SOURCE, ["iniciante"], origin=content.ORIGIN, deps=deps)
    execution_id = original["execution_id"]
    tokens_before = persistence.executions[execution_id]["total_tokens"]
    materials_before = len(persistence.materials)

    regen_client = FakeLLMClient()
    regen = run_pipeline(content.SOURCE, ["iniciante"], origin=content.ORIGIN,
                         deps=PipelineDeps(llm_client=regen_client, persistence=persistence),
                         execution_id=execution_id, combos=["iniciante:carrossel"], human_feedback=REASON)

    assert list(regen["generated_outputs"]) == ["iniciante:carrossel"]
    assert regen["execution_id"] == execution_id and len(persistence.executions) == 1  # nenhuma execução nova
    assert len(persistence.materials) == materials_before + 1  # a versão rejeitada continua guardada
    schemas = [p["schema"] for p in regen_client.prompts]
    assert schemas == ["extraction", "carousel_with_caption", "judge"]  # só o carrossel é gerado de novo
    carousel_prompt = regen_client.prompts[1]["prompt"]
    assert "REVISÃO HUMANA" in carousel_prompt and REASON in carousel_prompt
    # o custo da nova versão soma ao da execução original
    assert persistence.executions[execution_id]["total_tokens"] == tokens_before + regen["token_count"]


def test_combos_outside_the_selected_levels_are_ignored():
    deps = PipelineDeps(llm_client=FakeLLMClient(), persistence=InMemoryPersistence())
    final = run_pipeline(content.SOURCE, ["iniciante"], origin=content.ORIGIN, deps=deps, combos=["avancado:carrossel"])
    assert sorted(final["generated_outputs"]) == ["iniciante:carrossel", "iniciante:roteiro_video",
                                                  "iniciante:texto_analitico"]


def test_review_summary_on_the_home_indicator():
    assert review_summary({"aprovado": 2, "aguardando_revisao": 4, "editado": 1, "rejeitado": 1}) == \
        "2 aprovados · 5 aguardando · 1 rejeitado"
    assert review_summary({}) == "0 aprovados · 0 aguardando · 0 rejeitados"
