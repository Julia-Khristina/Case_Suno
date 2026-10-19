"""Regressão do caso Brent.

A versão anterior destes testes validava um TEMPLATE fixo sobre o Brent (src/app/level_selection.py), que era
devolvido para qualquer documento. Agora os testes garantem que:
- não existe template de conteúdo na interface;
- os gates reprovam as frases de preenchimento e a regra inventada do template antigo;
- o pipeline sobre uma fonte do Brent produz saídas no contrato (sem objeto impresso nem HTML) e os
  números fora da fonte são barrados.
"""
from __future__ import annotations

import copy
import inspect
from pathlib import Path

from src.evaluation.deterministic import EvaluationContext, evaluate, text_for_metrics
from src.evaluation.format_checks import load_forbidden_terms
from src.evaluation.thresholds import load_thresholds
from src.generation import rules
from src.glossary.reader import load_glossary
from src.pipeline.deps import PipelineDeps
from src.pipeline.graph import run_pipeline
from tests.fakes import content
from tests.fakes.llm import FakeLLMClient

BRENT_DIR = Path(__file__).parent


def _body(name: str) -> str:
    text = (BRENT_DIR / name).read_text(encoding="utf-8")
    return text.split("Conteúdo:", 1)[1].strip()


FONTE_01 = _body("source_01_infomoney.txt")
ORIGIN = {"instituicao": "InfoMoney", "titulo": "Brent fecha acima de US$ 110, maior desde 2014", "data": "2026-10-15"}

TEMPLATE_ANTIGO = {
    "introduction": "Contexto inicial: O petróleo Brent fechou em alta. O material mantém a leitura dos fatos relatados, "
                    "preservando dados, datas e números da fonte.",
    "development": "Os principais dados e fatos relatados devem ser verificados diretamente na origem antes de publicação. "
                   "A geração resume apenas os pontos explicitamente informados pela fonte.",
    "analysis": "Na análise, são consideradas apenas as afirmações da fonte e seus impactos prováveis; hipóteses não "
                "confirmadas são tratadas como projeções ou eventos futuros.",
    "conclusion": "Em resumo, o acompanhamento segue a fonte em sua versão mais recente. Consulte a origem para números, "
                  "datas e afirmações exatas.",
}
POINTS = [{"id": "p1", "title": "Brent fecha acima de US$ 110, maior patamar desde 2014", "assertions": []},
          {"id": "p2", "title": "Contrato para dezembro subiu 2,3% com tensões geopolíticas e cortes da Opep+", "assertions": []},
          {"id": "p3", "title": "WTI fecha em queda de 0,5%", "assertions": []}]


def test_interface_has_no_content_template():
    import src.app.level_selection as level_selection
    import src.app.components.news_cards as news_cards

    assert not hasattr(level_selection, "_generate_manual_materials_demo")
    assert not hasattr(level_selection, "_generate_manual_materials")
    for module in (level_selection, news_cards):
        source = inspect.getsource(module)
        assert "110 dólares" not in source and "Brent" not in source
        assert "_generate_manual_materials" not in source


def test_old_template_text_is_rejected_by_the_gates():
    sections = {k: {"title": k, "content": v, "ponto_ids": ["p1", "p2", "p3"]} for k, v in TEMPLATE_ANTIGO.items()}
    old = {"title": "Relatório analítico — Brent", "subtitle": "Notícia", **sections,
           "fonte_bloco": rules.source_block(ORIGIN), "caixa_entenda_os_termos": None}
    ctx = EvaluationContext(level="iniciante", fmt="texto_analitico", source_text=FONTE_01, glossary=load_glossary(),
                            thresholds=load_thresholds(), main_points=POINTS, forbidden_terms=load_forbidden_terms(),
                            origin=ORIGIN)
    report = evaluate(old, ctx)
    assert not report.passed
    assert {"frases_sem_respaldo_na_fonte", "cobertura_de_pontos_centrais_insuficiente"} <= set(report.failure_codes)


def test_pipeline_on_brent_source_keeps_contract_and_blocks_invented_numbers():
    brent_text = copy.deepcopy(content.good_output("texto_analitico", "iniciante"))  # texto sobre a Selic: não é da fonte
    client = FakeLLMClient(
        responses={"extraction": [{
            "main_points": [{"id": "p1", "order": 1, "title": "Brent acima de US$ 110", "assertion_ids": ["a1"]}],
            "assertions": [{"id": "a1", "text": "O Brent fechou acima de US$ 110, o maior patamar desde 2014.",
                            "type": "fato", "role": "nenhum",
                            "source_span": {"text": "cotado acima de US$ 110 o barril, o maior patamar desde 2014"}}],
            "numeric_data": [], "entities": [], "events": [], "detected_terms": []}],
            "texto_analitico": [brent_text]})
    final = run_pipeline(FONTE_01 + " " + FONTE_01, ["iniciante"], origin=ORIGIN, deps=PipelineDeps(llm_client=client))
    output = final["generated_outputs"]["iniciante:texto_analitico"]
    text = text_for_metrics(output["conteudo"], "texto_analitico")
    assert "title='" not in text and "ponto_ids=" not in text and "<" not in text
    first = next(a for a in final["attempt_history"] if a["combo"] == "iniciante:texto_analitico")
    assert "numero_ou_data_sem_origem" in first["motivo_reprovacao"]  # 10,50%, 4,5%… não existem na fonte do Brent
    assert output["status"] != "aprovado_pelo_juiz"
