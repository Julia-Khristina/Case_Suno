"""Pipeline LangGraph (seção 4.10): execução real do grafo com cliente LLM falso (sem rede)."""
from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from src.pipeline.deps import PipelineDeps
from src.pipeline.graph import build_graph, recursion_limit_for, run_pipeline
from src.pipeline.nodes.route import route_after_deterministic, route_after_human, route_after_judge
from src.pipeline.persistence import InMemoryPersistence
from src.pipeline.state import PipelineState
from src.shared.llm_client import InvalidLLMOutput
from tests.fakes import content
from tests.fakes.llm import FakeLLMClient


def _run(client, levels=("iniciante",), persistence=None):
    deps = PipelineDeps(llm_client=client, persistence=persistence or InMemoryPersistence())
    return run_pipeline(content.SOURCE, list(levels), origin=content.ORIGIN, deps=deps), deps


def _bad_text():
    """Texto Iniciante com número inventado: reprova nas métricas determinísticas."""
    bad = content.good_output("texto_analitico", "iniciante")
    bad["development"]["content"] = bad["development"]["content"].replace("4,5%", "5,8%")
    return bad


def test_state_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        PipelineState(campo_inexistente=1)


def test_graph_compiles_with_all_nodes():
    app = build_graph(deps=PipelineDeps(llm_client=FakeLLMClient()))
    nodes = set(app.get_graph().nodes)
    assert {"admit", "extract", "generate", "evaluate_deterministic", "judge", "finalize", "human_validation",
            "export"} <= nodes


def test_end_to_end_good_outputs_reach_human_validation_approved_by_judge():
    client = FakeLLMClient()
    final, deps = _run(client)
    assert final["status"] == "aguardando_revisao", final["errors"]
    assert final["errors"] == []
    statuses = {k: v["status"] for k, v in final["generated_outputs"].items()}
    assert statuses == {"iniciante:texto_analitico": "aprovado_pelo_juiz", "iniciante:carrossel": "aprovado_pelo_juiz",
                        "iniciante:roteiro_video": "aprovado_pelo_juiz"}
    # 1 extração + 3 gerações + 3 juízes
    assert [c["schema"] for c in client.calls].count("judge") == 3
    assert len(client.calls) == 7
    assert final["token_count"] == 7 * client.tokens_per_call


def test_rewrite_receives_numeric_feedback_and_counter_increments():
    client = FakeLLMClient(responses={"iniciante:texto_analitico": [_bad_text(), content.good_output("texto_analitico", "iniciante")]})
    final, _ = _run(client)
    text_prompts = [p["prompt"] for p in client.prompts if p["schema"] == "analytical_text"]
    assert len(text_prompts) == 2
    assert "(primeira tentativa)" in text_prompts[0]
    assert "numero_ou_data_sem_origem" in text_prompts[1] and "5,8%" in text_prompts[1]
    assert "limiar=0" in text_prompts[1]
    assert final["generated_outputs"]["iniciante:texto_analitico"]["status"] == "aprovado_pelo_juiz"
    assert final["generated_outputs"]["iniciante:texto_analitico"]["tentativas"] == 2


def test_loop_has_a_ceiling_of_two_rewrites_and_warns_human():
    variants = []
    for n in ("5,1%", "5,2%", "5,3%", "5,4%", "5,5%"):
        bad = content.good_output("texto_analitico", "iniciante")
        bad["development"]["content"] = bad["development"]["content"].replace("4,5%", n) + f" Variação {n}."
        variants.append(bad)
    client = FakeLLMClient(responses={"iniciante:texto_analitico": variants})
    final, _ = _run(client)
    text_calls = [c for c in client.calls if c["schema"] == "analytical_text"]
    assert len(text_calls) == 3  # 1 tentativa + 2 reescritas, nunca mais
    output = final["generated_outputs"]["iniciante:texto_analitico"]
    assert output["status"] == "reprovado_nas_metricas"
    assert "Limite de reescritas" in output["aviso"]
    assert final["status"] == "aguardando_revisao"


def test_judge_runs_only_after_deterministic_pass():
    client = FakeLLMClient(responses={"iniciante:texto_analitico": [_bad_text(), content.good_output("texto_analitico", "iniciante")]})
    final, _ = _run(client)
    schemas = [c["schema"] for c in client.calls]
    first_text, second_text = [i for i, s in enumerate(schemas) if s == "analytical_text"][:2]
    assert "judge" not in schemas[first_text:second_text]  # tentativa reprovada não vai ao juiz
    assert schemas[second_text + 1] == "judge"


def test_judge_rejection_feeds_criteria_back_and_rewrites():
    low = content.judge_output(score=8.5, low={"fidelidade_semantica": 3.0})
    client = FakeLLMClient(responses={"judge:iniciante": [low, content.judge_output(), content.judge_output()]})
    final, _ = _run(client)
    text_prompts = [p["prompt"] for p in client.prompts if p["schema"] == "analytical_text"]
    assert len(text_prompts) == 2
    assert "fidelidade_semantica: nota=3.0" in text_prompts[1]
    assert final["generated_outputs"]["iniciante:texto_analitico"]["status"] == "aprovado_pelo_juiz"


def test_judge_failure_goes_to_human_without_spending_rewrites():
    client = FakeLLMClient(responses={"judge": [InvalidLLMOutput("juiz devolveu lixo")]})
    final, _ = _run(client)
    assert [c["schema"] for c in client.calls].count("analytical_text") == 1
    output = final["generated_outputs"]["iniciante:texto_analitico"]
    assert output["status"] == "juiz_falhou"
    assert "juiz não avaliou" in " ".join(final["warnings"])


def test_invalid_generation_counts_as_failed_attempt():
    client = FakeLLMClient(responses={"iniciante:texto_analitico": [{"title": "sem seções"},
                                                                    content.good_output("texto_analitico", "iniciante")]})
    final, _ = _run(client)
    attempts = [a for a in final["attempt_history"] if a["combo"] == "iniciante:texto_analitico" and a["avaliacao"] == "deterministica"]
    assert attempts[0]["falhas"][0]["code"] == "saida_invalida_do_modelo"
    assert final["generated_outputs"]["iniciante:texto_analitico"]["status"] == "aprovado_pelo_juiz"


def test_identical_rewrite_stops_the_loop():
    client = FakeLLMClient(responses={"iniciante:texto_analitico": [_bad_text()]})  # sempre a mesma saída
    final, _ = _run(client)
    assert [c["schema"] for c in client.calls].count("analytical_text") == 2
    assert "repetiu a anterior" in final["generated_outputs"]["iniciante:texto_analitico"]["aviso"]


def test_persistence_records_every_attempt_judge_and_traceability():
    client = FakeLLMClient(responses={"iniciante:texto_analitico": [_bad_text(), content.good_output("texto_analitico", "iniciante")]})
    persistence = InMemoryPersistence()
    final, _ = _run(client, persistence=persistence)
    assert len(persistence.executions) == 1
    assert len(persistence.materials) == 3
    text_material = final["generated_outputs"]["iniciante:texto_analitico"]["material_id"]
    text_attempts = [a for a in persistence.attempts if a["id_material"] == text_material]
    assert [a["tentativa"] for a in text_attempts] == [1, 2]
    assert text_attempts[0]["motivo_reprovacao"] == "numero_ou_data_sem_origem"
    for field in ("conteudo", "metricas", "falhas", "tokens", "latencia", "modelo", "versao_prompt", "tamanho_texto",
                  "nivel_classificado", "feedback_usado"):
        assert field in text_attempts[1]
    assert text_attempts[1]["feedback_usado"]  # a 2ª tentativa registra o feedback recebido
    judged = [j for j in persistence.judge_evaluations if j["id_tentativa"] == text_attempts[1]["id_tentativa"]]
    assert judged and judged[0]["judge_model_id"] == client.judge_model != client.default_model
    assert judged[0]["text_length"] > 0 and judged[0]["evidence"]
    assert persistence.materials[text_material]["estado"] == "aguardando_revisao"
    links = persistence.sentence_links[text_material]
    assert links and any(link["afirmacao_id"] for link in links)
    assert set(final["config_versions"]) >= {"glossario", "prompts", "limiares", "rubrica", "estilo", "modelo_geracao",
                                             "modelo_juiz"}


def test_blocked_document_stops_at_admission():
    client = FakeLLMClient()
    deps = PipelineDeps(llm_client=client)
    final = run_pipeline("Assine para continuar lendo", ["iniciante"], deps=deps)
    assert final["status"] == "bloqueado"
    assert client.calls == []


def test_three_levels_generate_nine_outputs_within_recursion_limit():
    client = FakeLLMClient()
    final, _ = _run(client, levels=("iniciante", "intermediario", "avancado"))
    assert len(final["generated_outputs"]) == 9
    assert recursion_limit_for(3, 2) >= 3 * 3 * 10


def test_routers_read_the_decision_of_the_evaluating_node():
    assert route_after_deterministic({"next_action": "judge"}) == "judge"
    assert route_after_deterministic({"next_action": "generate"}) == "generate"
    assert route_after_deterministic({"next_action": None}) == "finalize"
    assert route_after_judge(PipelineState(next_action="generate")) == "generate"
    assert route_after_human({"human_decision": "aprovar"}) == "export"
    assert route_after_human({"human_decision": None}) == "end"  # pausa, sem laço sobre si mesmo
