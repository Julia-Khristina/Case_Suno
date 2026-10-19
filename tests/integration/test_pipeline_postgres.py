"""Pipeline completo gravando no PostgreSQL (execução, materiais, tentativas, juiz e rastreabilidade frase → afirmação).
Pulado sem banco (ver conftest)."""
from __future__ import annotations

import psycopg

from src.persistence.database import get_database_url
from src.pipeline.deps import PipelineDeps
from src.pipeline.graph import run_pipeline
from src.pipeline.persistence import PostgresPersistence
from tests.fakes import content
from tests.fakes.llm import FakeLLMClient
from tests.integration.graph_cleanup import delete_component


def test_pipeline_persists_attempts_judge_and_sentence_links():
    conn = psycopg.connect(get_database_url(), connect_timeout=5)
    final = {}
    try:
        final = run_pipeline(content.SOURCE, ["iniciante"], origin=content.ORIGIN,
                             deps=PipelineDeps(llm_client=FakeLLMClient(), persistence=PostgresPersistence(conn)))
        assert final["errors"] == []
        material_id = final["generated_outputs"]["iniciante:texto_analitico"]["material_id"]
        with conn.cursor() as cur:
            cur.execute("SELECT estado, status_avaliacao, nivel_classificado FROM materiais WHERE id_material = %s",
                        (material_id,))
            assert cur.fetchone() == ("aguardando_revisao", "aprovado_pelo_juiz", "iniciante")
            cur.execute("SELECT COUNT(*), MAX(versao_prompt) FROM tentativas WHERE id_material = %s", (material_id,))
            count, prompt_version = cur.fetchone()
            assert count == 1 and prompt_version
            cur.execute("""SELECT j.id_modelo_juiz, j.tamanho_texto, j.aprovado FROM avaliacoes_juiz j
                           JOIN tentativas t ON t.id_tentativa = j.id_tentativa WHERE t.id_material = %s""", (material_id,))
            judge_model, length, approved = cur.fetchone()
            assert judge_model == "judge-model-x" and length > 0 and approved is True
            cur.execute("""SELECT COUNT(*) FROM arestas_grafo e JOIN nos_grafo n ON n.id_no = e.id_no_origem
                           WHERE e.tipo_relacao = 'BASEADA_EM' AND n.tipo_no = 'frase_gerada'""")
            assert cur.fetchone()[0] > 0
            cur.execute("SELECT hash_configuracao, versao_rubrica FROM execucoes WHERE id_execucao = %s",
                        (final["execution_id"],))
            assert all(cur.fetchone())
    finally:
        conn.rollback()
        if final.get("execution_id"):
            delete_execution(conn, final["execution_id"])
        conn.close()


def test_rejected_material_is_regenerated_in_the_same_execution_with_the_reason():
    from src.pipeline.nodes.human_validation import RegenerationUnavailable, apply_human_decision, regenerate_rejected

    conn = psycopg.connect(get_database_url(), connect_timeout=5)
    final = {}
    try:
        final = run_pipeline(content.SOURCE, ["iniciante"], origin=content.ORIGIN,
                             deps=PipelineDeps(llm_client=FakeLLMClient(), persistence=PostgresPersistence(conn)))
        rejected_id = final["generated_outputs"]["iniciante:carrossel"]["material_id"]
        try:
            regenerate_rejected(conn, rejected_id)
            raise AssertionError("material não rejeitado não deveria ser gerado de novo")
        except RegenerationUnavailable:
            pass
        apply_human_decision(conn, rejected_id, "rejeitar", note="[Texto confuso] slide 2 repete o slide 1")

        client = FakeLLMClient()
        result = regenerate_rejected(conn, rejected_id,
                                     deps=PipelineDeps(llm_client=client, persistence=PostgresPersistence(conn)))
        new_id = result["id_material_novo"]
        assert new_id and new_id != rejected_id and result["erros"] == []
        assert "slide 2 repete o slide 1" in client.prompts[1]["prompt"]
        with conn.cursor() as cur:
            cur.execute("SELECT id_execucao::text, nivel, formato, estado FROM materiais WHERE id_material = %s", (new_id,))
            assert cur.fetchone() == (final["execution_id"], "iniciante", "carrossel", "aguardando_revisao")
            cur.execute("SELECT estado FROM materiais WHERE id_material = %s", (rejected_id,))
            assert cur.fetchone()[0] == "rejeitado"  # a versão rejeitada continua guardada
            cur.execute("SELECT decisao, observacao FROM decisoes_humanas WHERE id_material = %s ORDER BY criado_em",
                        (rejected_id,))
            assert cur.fetchall() == [("rejeitar", "[Texto confuso] slide 2 repete o slide 1"),
                                      ("regenerar", f"nova versão: {new_id}")]
            cur.execute("SELECT COUNT(*) FROM execucoes WHERE hash_documento = (SELECT hash_documento FROM execucoes "
                        "WHERE id_execucao = %s) AND criado_em >= (SELECT criado_em FROM execucoes WHERE id_execucao = %s)",
                        (final["execution_id"], final["execution_id"]))
            assert cur.fetchone()[0] == 1  # nenhuma execução nova
    finally:
        conn.rollback()
        if final.get("execution_id"):
            delete_execution(conn, final["execution_id"])
        conn.close()


def delete_execution(conn, execution_id: str) -> None:
    """Remove o que o teste gravou (execução, materiais, tentativas, juiz, decisões e nós do grafo: material, frases
    e a extração do documento de teste), para não deixar restos no banco de desenvolvimento."""
    _delete_extraction_graph(conn, execution_id)
    with conn.cursor() as cur:
        cur.execute("SELECT id_material FROM materiais WHERE id_execucao = %s", (execution_id,))
        materials = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT id_no FROM nos_grafo WHERE tipo_no = 'material' AND propriedades->>'id_material' = ANY(%s)",
                    ([str(m) for m in materials],))
        nodes = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT id_no_destino FROM arestas_grafo WHERE id_no_origem = ANY(%s) AND tipo_relacao = 'TEM_FRASE'",
                    (nodes,))
        nodes += [r[0] for r in cur.fetchall()]
        cur.execute("DELETE FROM arestas_grafo WHERE id_no_origem = ANY(%s) OR id_no_destino = ANY(%s)", (nodes, nodes))
        cur.execute("DELETE FROM nos_grafo WHERE id_no = ANY(%s)", (nodes,))
        cur.execute("DELETE FROM avaliacoes_juiz WHERE id_tentativa IN "
                    "(SELECT id_tentativa FROM tentativas WHERE id_material = ANY(%s))", (materials,))
        cur.execute("DELETE FROM tentativas WHERE id_material = ANY(%s)", (materials,))
        cur.execute("DELETE FROM decisoes_humanas WHERE id_material = ANY(%s)", (materials,))
        cur.execute("DELETE FROM materiais WHERE id_material = ANY(%s)", (materials,))
        cur.execute("DELETE FROM execucoes WHERE id_execucao = %s", (execution_id,))
    conn.commit()


def _delete_extraction_graph(conn, execution_id: str) -> None:
    """Nós da extração gravados por esta execução: tudo ligado (em qualquer direção) ao nó `documento` do documento
    de teste criado a partir do início da execução. Nós anteriores ou de outros documentos não são tocados."""
    with conn.cursor() as cur:
        cur.execute("SELECT hash_documento, criado_em FROM execucoes WHERE id_execucao = %s", (execution_id,))
        row = cur.fetchone()
        if row is None:
            return
        doc_hash, started = row
        cur.execute("SELECT id_no FROM nos_grafo WHERE tipo_no = 'documento' AND propriedades->>'hash' = %s "
                    "AND criado_em >= %s - INTERVAL '5 seconds'", (doc_hash, started))
        documents = [r[0] for r in cur.fetchall()]
    delete_component(conn, documents, since=started)
