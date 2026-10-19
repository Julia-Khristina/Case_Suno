"""Diff colorido com hover entre tentativas (o juiz em si é testado em tests/unit/test_judge.py)."""
from __future__ import annotations

from src.evaluation.judge import PatchSuggestion
from src.evaluation.diff_utils import gerar_diff_html, gerar_lista_alteracoes, css_diff


# ---------------------------------------------------------------------------
# Diff colorido com hover
# ---------------------------------------------------------------------------

def test_diff_html_insercao():
    """Inserção é mostrada com destaque."""
    antes = "O Copom decidiu manter a Selic."
    depois = "O Copom decidiu manter a Selic em 10,50%."
    html_diff = gerar_diff_html(antes, depois)
    # SequenceMatcher pode tratar como substituição ou inserção, mas deve conter o novo texto
    assert "10,50%" in html_diff


def test_diff_html_remocao():
    """Remoção é mostrada com destaque."""
    antes = "O Copom decidiu manter a Selic em 10,50%."
    depois = "O Copom decidiu manter a Selic."
    html_diff = gerar_diff_html(antes, depois)
    # "em 10,50%." foi removido
    assert "Selic" in html_diff


def test_diff_html_substituicao_com_hover():
    """Substituição mostra depois com hover mostrando o antes."""
    antes = "A taxa era de 10,50%."
    depois = "A taxa era de 10,75%."
    html_diff = gerar_diff_html(antes, depois)
    assert "data-original" in html_diff
    assert "10,50%" in html_diff  # antes aparece no hover
    assert "10,75%" in html_diff  # depois aparece no texto


def test_diff_lista_alteracoes():
    """Lista estruturada de alterações."""
    antes = "O Copom decidiu manter a Selic em 10,50%."
    depois = "O Copom decidiu elevar a Selic para 10,75%."
    alteracoes = gerar_lista_alteracoes(antes, depois)
    assert len(alteracoes) > 0
    for alt in alteracoes:
        assert "trecho_antes" in alt
        assert "trecho_depois" in alt
        assert "tipo" in alt
        assert "diff_html" in alt


def test_css_diff_contem_classes():
    """O CSS contém as classes para diff colorido."""
    css = css_diff()
    assert "diff-insercao" in css
    assert "diff-remocao" in css
    assert "diff-substituicao" in css


# ---------------------------------------------------------------------------
# PatchSuggestion model
# ---------------------------------------------------------------------------

def test_patch_suggestion_model():
    """PatchSuggestion valida campos obrigatórios."""
    p = PatchSuggestion(
        trecho_antes="texto antigo",
        trecho_depois="texto novo",
        posicao_inicial=5,
        tipo="substituicao",
    )
    assert p.trecho_antes == "texto antigo"
    assert p.trecho_depois == "texto novo"
    assert p.posicao_inicial == 5
    assert p.tipo == "substituicao"