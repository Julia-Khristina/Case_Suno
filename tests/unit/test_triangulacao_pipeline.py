"""Texto analítico triangulado (decisão de 17/10/2026): dossiê, matriz, gráficos, geração, checagens e juiz."""
from __future__ import annotations

import copy

import pytest

from src.evaluation.deterministic import EvaluationContext, evaluate
from src.evaluation.thresholds import load_thresholds
from src.extraction.extractor import Extractor
from src.generation import rules
from src.glossary.reader import load_glossary
from src.pipeline.deps import PipelineDeps
from src.pipeline.graph import run_pipeline
from src.triangulacao.alinhamento import _Alinhamento, build_matrix, rank_rows
from src.triangulacao.dossie import build_dossie, parse_quantity, quantity_label
from src.triangulacao.graficos_matriz import charts_for_matrix
from tests.fakes import triangulacao as T
from tests.fakes.llm import FakeLLMClient
from tests.fakes.triangulacao_texto import good_triangulated_text


def _client(text=None, alignment=None):
    return FakeLLMClient(responses={"extraction": [T.EXTRACTION_F1, T.EXTRACTION_F2, T.EXTRACTION_F3],
                                    "triangulacao_alinhamento": [alignment or T.ALINHAMENTO],
                                    "iniciante:texto_analitico": [text or good_triangulated_text()]})


def _dossie_with_matrix():
    dossie = build_dossie(T.FONTES)
    for fonte, raw in zip(dossie.fontes, [T.EXTRACTION_F1, T.EXTRACTION_F2, T.EXTRACTION_F3]):
        fonte.extraction = Extractor(llm_client=FakeLLMClient(responses={"extraction": [raw]})).extract(
            fonte.conteudo).model_dump(mode="json")
    return dossie, build_matrix(dossie, _Alinhamento.model_validate(T.ALINHAMENTO))


# --------------------------------------------------------------------------------------- dossiê e matriz

def test_copy_of_same_note_counts_as_one_independent_source():
    dossie = build_dossie(T.FONTES)
    assert dossie.independentes == 2  # f1 e f3 são a mesma nota
    assert {"f1", "f3"} <= set(dossie.grupos_origem[0]["fonte_ids"])


def test_quantities_are_read_with_scale_and_currency():
    assert parse_quantity("12", "R$ bilhões") == (12e9, "R$")
    assert parse_quantity("12.000", "R$ milhões") == (12e9, "R$")
    assert parse_quantity("4,5", "%") == (4.5, "%")
    assert parse_quantity("110,45", "US$ por barril")[1] == "US$ por barril"
    assert quantity_label("12", "R$ bilhões") == "R$ 12 bilhões"


def test_status_is_computed_by_code_not_by_the_model():
    _dossie, result = _dossie_with_matrix()
    status = {row.linha_id: row.status.value for row in result.linhas}
    assert status == {"L1": "divergencia_numerica", "L2": "divergencia_qualitativa", "L3": "convergencia",
                      "L4": "sem_contraponto"}
    l1 = result.linhas[0]
    assert l1.diferenca_absoluta == 3e9 and set(l1.fontes_divergentes) == {"f1", "f2"}
    assert any("f9" in w for w in result.avisos)  # id inventado pelo alinhador é descartado
    assert [r.linha_id for r in rank_rows(result.linhas)] == ["L1", "L2", "L3"]


def test_same_origin_sources_never_converge_alone():
    alignment = copy.deepcopy(T.ALINHAMENTO)
    alignment["topicos"] = [{"id": "t1", "titulo": "Custo total", "tipo": "numerico", "referencia": None,
                             "itens": [{"fonte": "f1", "ids": ["f1:n1"]}, {"fonte": "f3", "ids": ["f3:n1"]}]}]
    dossie, _ = _dossie_with_matrix()
    row = build_matrix(dossie, _Alinhamento.model_validate(alignment)).linhas[0]
    assert row.status.value == "sem_contraponto"
    assert "compartilham origem" in row.justificativa_status


def test_charts_use_source_labels_and_save_plotted_data(tmp_path):
    dossie, result = _dossie_with_matrix()
    charts = charts_for_matrix(result.linhas, [f.model_dump() for f in dossie.fontes], tmp_path, 4)
    kinds = [c["tipo"] for c in charts]
    assert kinds[0] == "mapa_posicoes" and "valores_por_fonte" in kinds
    bars = next(c for c in charts if c["id"] == "valores_L1")
    assert [d["valor_fonte"] for d in bars["dados"]] == ["R$ 12 bilhões", "R$ 15 bilhões", "R$ 12 bilhões"]
    assert (tmp_path / "valores_L1.png").exists() and (tmp_path / "valores_L1.json").exists()
    assert "Agência Gov: R$ 12 bilhões" in bars["texto_alternativo"]


# ------------------------------------------------------------------------------------------- pipeline

def test_triangulated_pipeline_produces_attributed_text_with_matrix_and_charts():
    client = _client()
    final = run_pipeline("", ["iniciante"], deps=PipelineDeps(llm_client=client), fontes=T.FONTES)
    output = final["generated_outputs"]["iniciante:texto_analitico"]
    assert output["status"] == "aprovado_pelo_juiz", output["aviso"]
    content = output["conteudo"]
    assert content["triangulacao"]["pontos_centrais"] == ["L1", "L2", "L3"]
    assert [g["id"] for g in content["graficos"]] == ["mapa_posicoes", "valores_L1"]  # Iniciante: até 2 gráficos
    assert content["fonte_bloco"].startswith("Fontes: Agência Gov")
    assert any(r["tipo"] == "projecao" and r["fonte"] == "Jornal Econômico" for r in content["rastreio"])
    schemas = [c["schema"] for c in client.calls]
    assert schemas[:5] == ["extraction"] * 3 + ["triangulacao_alinhamento", "analytical_text_triangulated"]
    prompt = next(p["prompt"] for p in client.prompts if p["schema"] == "analytical_text_triangulated")
    assert "[L1] Custo total do programa em três anos — status: Divergência numérica" in prompt
    assert "R$ 3 bilhões" not in prompt  # a diferença calculada não vai ao gerador
    judge_prompt = next(p["prompt"] for p in client.prompts if p["schema"] == "judge")
    assert "fidelidade_atribuicao" in judge_prompt and "R$ 3 bilhões" in judge_prompt


def test_without_two_independent_sources_falls_back_to_single_source():
    client = FakeLLMClient()
    fontes = [T.FONTES[0], T.FONTES[2]]  # mesma origem
    final = run_pipeline("", ["iniciante"], deps=PipelineDeps(llm_client=client), fontes=fontes)
    assert final["triangulacao"] is None
    assert any("Sem triangulação" in w for w in final["warnings"])
    assert "triangulacao_alinhamento" not in [c["schema"] for c in client.calls]


def test_alignment_failure_falls_back_to_single_source():
    client = FakeLLMClient(responses={"extraction": [T.EXTRACTION_F1, T.EXTRACTION_F2, T.EXTRACTION_F3, T.EXTRACTION_F1],
                                      "triangulacao_alinhamento": [{"topicos": "inválido"}]})
    final = run_pipeline("", ["iniciante"], deps=PipelineDeps(llm_client=client), fontes=T.FONTES)
    assert final["triangulacao"] is None
    assert any("Triangulação não concluída" in w for w in final["warnings"])


# ------------------------------------------------------------------------------- checagens do triangulado

def _evaluate_text(content: dict):
    dossie, result = _dossie_with_matrix()
    tri = {"matriz": [r.model_dump(mode="json") for r in result.linhas],
           "fontes": [f.model_dump(exclude={"extraction", "conteudo"}) for f in dossie.fontes],
           "pontos_centrais": ["L1", "L2", "L3"]}
    origin = {"fontes": [{"nome": f.nome, "titulo": f.titulo, "data": f.data, "url": f.url} for f in dossie.fontes]}
    content = {**content, "fonte_bloco": rules.source_block(origin), "caixa_entenda_os_termos": None}
    points = [{"id": r["linha_id"], "title": r["topico"], "assertions": [c["valor_texto"] for c in r["celulas"]]}
              for r in tri["matriz"] if r["linha_id"] in tri["pontos_centrais"]]
    ctx = EvaluationContext(level="iniciante", fmt="texto_analitico", source_text=dossie.texto_combinado(),
                            glossary=load_glossary(), thresholds=load_thresholds(), main_points=points, origin=origin,
                            triangulacao=tri)
    return evaluate(content, ctx)


def test_good_triangulated_text_passes():
    report = _evaluate_text(good_triangulated_text())
    assert report.passed, [f.line() for f in report.failures]


def _mutate(section: str, old: str, new: str) -> dict:
    text = good_triangulated_text()
    assert old in text[section]["content"]
    text[section]["content"] = text[section]["content"].replace(old, new)
    return text


@pytest.mark.parametrize("section,old,new,code", [
    ("analysis", "O Jornal Econômico apresenta o lado oposto. Segundo o jornal, economistas",
     "Economistas", "divergencia_sem_os_dois_lados"),
    ("conclusion", "Nenhuma das duas fontes diz qual conta vai se confirmar.",
     "Na verdade, a conta do governo é a correta.", "veredito_entre_fontes"),
    ("development", "Há um ponto em que as fontes concordam.",
     "O dado foi confirmado por duas fontes.", "veredito_entre_fontes"),
    ("development", "A Agência Gov e o Jornal Econômico informam que o novo limite",
     "O novo limite", "numero_sem_atribuicao_de_fonte"),
])
def test_bad_triangulated_texts_fail_for_the_right_reason(section, old, new, code):
    text = _mutate(section, old, new)
    if code == "divergencia_sem_os_dois_lados":  # a análise passa a ser o único lugar da divergência L2
        text[section]["content"] = text[section]["content"].replace("Jornal Econômico", "outro veículo")
        text["conclusion"]["linha_ids"] = ["L1", "L3", "L4"]
        text["conclusion"]["ponto_ids"] = ["L1", "L3"]
    report = _evaluate_text(text)
    assert code in report.failure_codes, report.failure_codes


def test_cited_row_must_exist():
    text = good_triangulated_text()
    text["analysis"]["linha_ids"] = ["L2", "L99"]
    assert "linha_da_matriz_inexistente" in _evaluate_text(text).failure_codes
