"""Avaliador determinístico (seções 4.6 e 4.7): casos adversariais B6 e métricas individuais."""
from __future__ import annotations

import pytest

from src.evaluation.deterministic import EvaluationContext, evaluate
from src.evaluation.flesch_ptbr import count_syllables, flesch_reading_ease_pt
from src.evaluation.format_checks import has_emoji, load_forbidden_terms, recommendation_language
from src.evaluation.grounding import dates_without_origin, numbers_without_origin
from src.evaluation.level_classifier import classify_level
from src.evaluation.thresholds import MissingThreshold, Thresholds, load_thresholds
from src.generation import rules
from src.glossary.reader import Glossary, GlossaryEntry, load_glossary
from tests.audit.audit_b6_cases import APPROVED_IMPACT, MAIN_POINTS, build_cases
from tests.fakes import content

ORIGIN = content.ORIGIN
SOURCE = content.SOURCE


def _glossary_with_approved_impact() -> Glossary:
    base = load_glossary()
    extra = GlossaryEntry(termo="juros altos", nivel="iniciante", status="aprovado", explicacao_impacto=APPROVED_IMPACT[0])
    return Glossary(versao=base.versao, termos=[*base.termos, extra], hash=base.hash)


GLOSSARY = _glossary_with_approved_impact()
POINTS = [{"id": f"mp{i + 1}", "title": t, "assertions": []} for i, t in enumerate(MAIN_POINTS)]


def _prepare(case: dict) -> dict:
    c = case["conteudo"]
    if case["formato"] == "texto_analitico":
        c = dict(c, fonte_bloco=rules.source_block(ORIGIN))
        body = " ".join(c[s]["content"] for s in ("introduction", "development", "analysis", "conclusion"))
        c["caixa_entenda_os_termos"] = rules.understand_terms_box(f"{c['title']} {body}", GLOSSARY) \
            if case["nivel"] == "iniciante" else None
        return c
    caption = dict(c["caption"], source_block=rules.source_block(ORIGIN))
    caption["texto_final"] = rules.caption_final_text(caption["opening"], caption["short_context"],
                                                      caption["source_block"], caption["cta_sentence"], None, [])
    return {**c["carousel"], "linha_vermelha_nivel": rules.level_line(case["nivel"]), "legenda": caption}


def _evaluate(case: dict):
    ctx = EvaluationContext(level=case["nivel"], fmt=case["formato"], source_text=SOURCE, glossary=GLOSSARY,
                            thresholds=load_thresholds(), main_points=POINTS, forbidden_terms=load_forbidden_terms(),
                            origin=ORIGIN)
    return evaluate(_prepare(case), ctx)


CASES = {c["id"]: c for c in build_cases()}
EXPECTED = {
    "b01_padding_repetido": "frases_repetidas",
    "b02_numero_inventado": "numero_ou_data_sem_origem",
    "b03_data_inventada": "numero_ou_data_sem_origem",
    "b04_comparacao_entre_documentos": "variacao_nao_declarada_pela_fonte",
    "b05_recomendacao_de_compra": "linguagem_de_recomendacao",
    "b06a_emoji_coberto": "emoji_encontrado",
    "b06b_emoji_fora_da_regex": "emoji_encontrado",
    "b07_termo_proibido": "termo_proibido_encontrado",
    "b08_iniciante_jargao_sem_explicacao": "termo_tecnico_sem_explicacao",
    "b09_avancado_sem_jargao": "densidade_fora_da_faixa",
    "b10_ponto_central_ausente": "cobertura_de_pontos_centrais_insuficiente",
    "b11_excesso_de_palavras": "tamanho_fora_do_intervalo",
    "b12_slides_repetidos": "slides_repetidos",
    "b13_em_geral_fora_do_glossario": "marcador_em_geral_fora_do_glossario",
    "b14_padding_contra_os_gates": "frases_repetidas",
}


@pytest.mark.parametrize("case_id", ["g1_iniciante", "g2_intermediario", "g3_avancado"])
def test_good_outputs_pass_and_are_classified_at_target_level(case_id):
    report = _evaluate(CASES[case_id])
    assert report.passed, [f.line() for f in report.failures]
    assert report.classified_level == CASES[case_id]["nivel"]


@pytest.mark.parametrize("case_id,code", sorted(EXPECTED.items()))
def test_bad_outputs_fail_for_the_right_reason(case_id, code):
    report = _evaluate(CASES[case_id])
    assert not report.passed
    assert code in report.failure_codes, report.failure_codes


def test_feedback_is_numeric_with_metric_value_and_threshold():
    feedback = _evaluate(CASES["b02_numero_inventado"]).feedback()
    assert "numero_ou_data_sem_origem: numeros_e_datas_fora_da_fonte=1 | limiar=0 | detalhe=[5,8%]" in feedback
    assert "Medidas atuais: palavras=" in feedback


def test_beginner_too_hard_fails_legibility_with_value_and_band():
    case = dict(CASES["g3_avancado"], nivel="iniciante")
    failure = next(f for f in _evaluate(case).failures if f.code == "legibilidade_fora_da_faixa")
    assert failure.valor < 55 and failure.limiar == ">= 55"


# --------------------------------------------------------------------------------- métricas isoladas


def test_flesch_uses_portuguese_coefficients_and_syllables():
    assert [count_syllables(w) for w in ("decisão", "economia", "saúde", "quatro", "história", "leão", "mãe")] == \
        [3, 5, 3, 2, 4, 2, 1]
    simple = "O juro subiu. A conta ficou cara. O preço da comida subiu."
    assert flesch_reading_ease_pt(simple) > 70  # a fórmula inglesa dava valores negativos para textos assim


def test_numbers_are_compared_as_whole_tokens_ignoring_trailing_punctuation():
    source = "A Selic ficou em 10,50% em outubro de 2026."
    assert numbers_without_origin("Em 2026, a Selic ficou em 10,50%.", source) == []
    assert numbers_without_origin("A Selic ficou em 10%.", source) == ["10%"]


def test_dates_by_name_must_exist_in_source():
    source = "A reunião ocorreu nos dias 12 e 13 de outubro de 2026."
    assert dates_without_origin("Reunião de 12 e 13 de outubro.", source) == []
    assert dates_without_origin("Reunião de 18 de setembro.", source) == ["18 de setembro", "setembro"]


@pytest.mark.parametrize("emoji", ["📉", "🤑", "✅", "❤️", "🚀"])
def test_emoji_detection_covers_supplemental_and_dingbats(emoji):
    assert has_emoji(f"Texto {emoji}")


def test_recommendation_language_detected_but_not_noun_sale():
    assert recommendation_language("Vale a pena investir agora em títulos.")
    assert recommendation_language("Compre ações de bancos.")
    assert not recommendation_language("A venda de ativos do Tesouro cresceu.")


def test_level_classifier_uses_yaml_bands_and_returns_indistinto():
    glossary = load_glossary()
    good = content.GOOD_TEXT
    for level in ("iniciante", "intermediario", "avancado"):
        text = " ".join(s["content"] for s in good[level].values() if isinstance(s, dict))
        assert classify_level(text, glossary.technical_forms()) == level
    assert classify_level("Texto simples sem termos. Frase curta.", glossary.technical_forms(),
                          {**load_thresholds(), "flesch_iniciante_min": 200}) == "indistinto"


def test_missing_threshold_fails_loudly():
    with pytest.raises(MissingThreshold):
        Thresholds({}).req("flesch_iniciante_min")


def test_script_checks_timing_rate_and_spoken_rule():
    script = content.good_output("roteiro_video", "iniciante")
    for scene in script["scenes"]:
        scene["fala_falada"] = rules.spoken_text(scene["fala_escrita"], GLOSSARY)
    ctx = EvaluationContext(level="iniciante", fmt="roteiro_video", source_text=SOURCE, glossary=GLOSSARY,
                            thresholds=load_thresholds(), main_points=[
                                {"id": "p1", "title": "Copom mantém a Selic em 10,50% ao ano", "assertions": []},
                                {"id": "p2", "title": "IPCA acumulado acima da meta de inflação", "assertions": []},
                                {"id": "p3", "title": "Disciplina fiscal e choques de oferta como riscos",
                                 "assertions": ["Choques de oferta em alimentos e energia podem pressionar a inflação no curto prazo."]}],
                            origin=ORIGIN)
    assert evaluate(script, ctx).passed, [f.line() for f in evaluate(script, ctx).failures]
    broken = content.good_output("roteiro_video", "iniciante")
    broken["scenes"][1]["start_sec"] = 8  # sobreposição
    broken["scenes"][0]["fala_escrita"] += " " + " ".join(["palavra"] * 40)
    codes = evaluate(broken, ctx).failure_codes
    assert {"tempos_do_roteiro_invalidos", "fala_rapida_demais_para_a_duracao", "fala_falada_diferente_da_regra"} <= set(codes)
