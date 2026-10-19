"""Blocos do leitor: exportação HTML com gráficos e matriz, selos de fato/projeção e sugestão de cards relacionados."""
from __future__ import annotations

from src.app.components.material_extras import annotated_markdown
from src.app.components.triangulation import related_score, suggestions
from src.export.text_export import to_html, to_markdown
from src.generation.models import AnalyticalText
from src.pipeline.deps import PipelineDeps
from src.pipeline.graph import run_pipeline
from tests.fakes import triangulacao as T
from tests.fakes.llm import FakeLLMClient
from tests.fakes.triangulacao_texto import good_triangulated_text


def _triangulated_text() -> AnalyticalText:
    client = FakeLLMClient(responses={"extraction": [T.EXTRACTION_F1, T.EXTRACTION_F2, T.EXTRACTION_F3],
                                      "triangulacao_alinhamento": [T.ALINHAMENTO],
                                      "iniciante:texto_analitico": [good_triangulated_text()]})
    final = run_pipeline("", ["iniciante"], deps=PipelineDeps(llm_client=client), fontes=T.FONTES)
    return AnalyticalText.model_validate(final["generated_outputs"]["iniciante:texto_analitico"]["conteudo"])


def test_standalone_html_embeds_charts_matrix_and_projection_badges():
    page = to_html(_triangulated_text(), standalone=True)
    assert page.startswith("<!DOCTYPE html>")
    assert page.count("data:image/png;base64,") == 2  # mapa de posições + valores de L1
    assert "Matriz de triangulação" in page and "Divergência numérica" in page and "R$ 15 bilhões" in page
    assert '<span class="selo"' in page and "projeção" in page
    assert "https://" not in page.split("<h3>Fontes</h3>")[0].split("<style>")[0]  # nada carregado de fora


def test_markdown_has_matrix_table_and_chart_alt_text():
    markdown = to_markdown(_triangulated_text())
    assert "## Matriz de triangulação" in markdown and "| L1 | Custo total do programa em três anos |" in markdown
    assert "![Mapa de posições por fonte" in markdown
    assert "## Fontes" in markdown


def test_annotated_markdown_marks_projection_sentences_only():
    content = {"rastreio": [{"texto": "A Fazenda estima custo.", "tipo": "projecao"},
                            {"texto": "O programa foi lançado.", "tipo": "fato"}]}
    out = annotated_markdown(content, "O programa foi lançado. A Fazenda estima custo.")
    assert "A Fazenda estima custo. `projeção`" in out and "lançado. `" not in out


def test_related_cards_are_suggested_by_shared_subject():
    chosen = {"1": {"id_card": "1", "titulo": "Governo lança Prospera MEI com perdão de dívidas",
                    "descricao": "Programa para microempreendedores", "data_card": "2026-10-16"}}
    cards = [chosen["1"],
             {"id_card": "2", "titulo": "Prospera MEI piora risco fiscal, dizem economistas",
              "descricao": "Microempreendedores e perdão de dívidas", "data_card": "2026-10-16"},
             {"id_card": "3", "titulo": "Petrobras sobe 6% e Ibovespa recua", "descricao": "Bolsa", "data_card": "2026-10-16"}]
    ranked = suggestions(cards, chosen)
    assert [c["id_card"] for c, _s in ranked] == ["2"]
    assert related_score(cards[1], [chosen["1"]]) > related_score(cards[2], [chosen["1"]])
