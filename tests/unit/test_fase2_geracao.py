"""Geração (seção 4.6): entrada estruturada, prompts por nível e formato, partes por regra, sem padding."""
from __future__ import annotations

import pytest

from src.evaluation.differentiation import assert_differentiation, trigram_overlap_ratio
from src.evaluation.thresholds import load_thresholds
from src.extraction.extractor import Extractor
from src.generation import rules
from src.generation.carousel import CarouselGenerator
from src.generation.models import AnalyticalText, Caption, Carousel, Script
from src.generation.script import ScriptGenerator
from src.generation.text_analytical import AnalyticalTextGenerator
from src.glossary.reader import Glossary, GlossaryEntry, load_glossary
from src.shared.llm_client import InvalidLLMOutput
from tests.fakes import content
from tests.fakes.llm import FakeLLMClient

EXTRACTION = Extractor(llm_client=FakeLLMClient()).extract(content.SOURCE)


def _generate(generator_cls, level="iniciante", client=None, **kwargs):
    client = client or FakeLLMClient()
    generator = generator_cls(llm_client=client)
    result = generator.generate(EXTRACTION, level, content.SOURCE, origin=content.ORIGIN, **kwargs)
    return result, client, generator


def test_generator_receives_structured_input_not_full_document():
    _result, client, _ = _generate(AnalyticalTextGenerator)
    prompt = client.prompts[0]["prompt"]
    assert "[p1] Copom mantém a Selic em 10,50% ao ano" in prompt
    assert "(a1; fato)" in prompt and 'trecho de origem: "decidiu, por unanimidade' in prompt
    assert "(n1) Selic: 10,50" in prompt
    assert "Selic (nível intermediario)" in prompt  # entrada do glossário do termo presente
    assert "garantia de lucro" in prompt          # termos proibidos
    assert "Frases curtas" in prompt               # regras do nível
    # o documento inteiro não vai ao gerador (trecho que não é afirmação nem dado extraído)
    assert "O governo federal anunciou medidas de contenção de gastos" not in prompt
    assert "conteúdo entre <dados>" in client.prompts[0]["system"]


@pytest.mark.parametrize("fmt_cls", [AnalyticalTextGenerator, CarouselGenerator, ScriptGenerator])
@pytest.mark.parametrize("level,marker", [("iniciante", "Nível INICIANTE"), ("intermediario", "Nível INTERMEDIÁRIO"),
                                          ("avancado", "Nível AVANÇADO")])
def test_prompt_is_specific_to_level_and_format(fmt_cls, level, marker):
    client = FakeLLMClient(responses={"analytical_text": [content.good_output("texto_analitico", "iniciante")],
                                      "carrossel": [content.good_output("carrossel", "iniciante")],
                                      "roteiro_video": [content.good_output("roteiro_video", "iniciante")]})
    generator = fmt_cls(llm_client=client)
    generator.generate(EXTRACTION, level, content.SOURCE, origin=content.ORIGIN)
    assert marker in client.prompts[0]["prompt"]
    assert len(generator.last_input.prompt_version()) == 12


@pytest.mark.parametrize("fmt_cls", [AnalyticalTextGenerator, CarouselGenerator, ScriptGenerator])
def test_feedback_reaches_every_format(fmt_cls):
    client = FakeLLMClient(responses={"analytical_text": [content.good_output("texto_analitico", "iniciante")],
                                      "carrossel": [content.good_output("carrossel", "iniciante")],
                                      "roteiro_video": [content.good_output("roteiro_video", "iniciante")]})
    fmt_cls(llm_client=client).generate(EXTRACTION, "iniciante", content.SOURCE, feedback="- falha_x: valor=1 | limiar=0")
    assert "- falha_x: valor=1 | limiar=0" in client.prompts[0]["prompt"]


def test_text_parts_are_built_by_rule_not_by_the_model():
    response = content.good_output("texto_analitico", "iniciante")
    response["fonte_bloco"] = "Fonte: inventada pelo modelo"
    response["word_count_total"] = 9999
    client = FakeLLMClient(responses={"iniciante:texto_analitico": [response]})
    text, _, _ = _generate(AnalyticalTextGenerator, client=client)
    assert isinstance(text, AnalyticalText)
    assert text.fonte_bloco == rules.source_block(content.ORIGIN)
    assert text.word_count_total == sum(text.word_count_by_section.values()) < 9999
    assert text.caixa_entenda_os_termos is None  # nenhum termo aprovado no glossário ainda


def test_understand_terms_box_uses_only_approved_glossary_and_only_for_beginner():
    glossary = Glossary(termos=[GlossaryEntry(termo="Selic", nivel="intermediario", status="aprovado",
                                              explicacao_iniciante="taxa básica de juros da economia."),
                                GlossaryEntry(termo="IPCA", nivel="intermediario", status="pendente",
                                              explicacao_iniciante="índice de inflação.")])
    text, _, _ = _generate(AnalyticalTextGenerator, glossary=glossary)
    assert text.caixa_entenda_os_termos == "Selic: taxa básica de juros da economia."
    advanced, _, _ = _generate(AnalyticalTextGenerator, level="avancado", glossary=glossary)
    assert advanced.caixa_entenda_os_termos is None


def test_carousel_caption_source_line_and_notice_are_rule_based():
    carousel, client, _ = _generate(CarouselGenerator)
    caption = carousel[1]
    assert isinstance(carousel[0], Carousel) and isinstance(caption, Caption)
    assert carousel[0].linha_vermelha_nivel == "em cima"
    assert caption.source_block == rules.source_block(content.ORIGIN)
    assert caption.texto_final.startswith(caption.opening) and caption.source_block in caption.texto_final
    assert caption.institutional_notice is None  # sem aviso oficial da Suno configurado
    assert "A fonte, o aviso institucional e as hashtags são inseridos pelo sistema" in client.prompts[0]["prompt"]
    assert [s.ponto_id for s in carousel[0].slides if s.role == "corpo"] == ["p1", "p2", "p3"]


def test_carousel_with_verb_outside_list_is_invalid_output():
    bad = content.good_output("carrossel", "iniciante")
    bad["caption"]["cta_verb"] = "comprar"
    with pytest.raises(InvalidLLMOutput):
        _generate(CarouselGenerator, client=FakeLLMClient(responses={"iniciante:carrossel": [bad]}))


def test_script_spoken_line_is_derived_by_rule():
    script, _, _ = _generate(ScriptGenerator)
    assert isinstance(script, Script)
    scene = script.scenes[0]
    assert "10,50%" in scene.fala_escrita
    assert scene.fala_falada == rules.spoken_text(scene.fala_escrita, load_glossary())
    assert "dez vírgula cinquenta por cento" in scene.fala_falada


def test_short_source_word_range_is_equal_across_levels_and_avoids_padding():
    t = load_thresholds()
    short = rules.word_range("texto_analitico", 141, t)
    assert short[1] < t["tamanho_texto_min_palavras"]  # fonte de 141 palavras não exige 350 palavras
    assert rules.word_range("texto_analitico", 948, t) == (350, 500)
    assert rules.word_range("carrossel", 948, t) == (t["carrossel_min_palavras"], t["carrossel_max_palavras"])
    assert rules.word_range("roteiro_video", 948, t)[1] == 180  # 3 palavras/s × 60 s


def test_prompt_states_no_padding_rule():
    _r, client, _ = _generate(AnalyticalTextGenerator)
    assert "Sem preenchimento" in client.prompts[0]["system"]
    assert "aviso_fonte_insuficiente" in client.prompts[0]["system"]


def test_differentiation_rejects_high_overlap():
    a = "O Copom decidiu manter a Selic em 10,50% ao ano. A inflação está em 4,5%. O próximo encontro será em 45 dias."
    b = a.replace("próximo", "proximo")
    assert trigram_overlap_ratio(a, b) > 0.7
    with pytest.raises(AssertionError):
        assert_differentiation({"iniciante": a, "avancado": b}, threshold=0.7)


def test_good_level_texts_are_differentiated():
    texts = {lvl: " ".join(s["content"] for k, s in content.GOOD_TEXT[lvl].items() if isinstance(s, dict))
             for lvl in ("iniciante", "intermediario", "avancado")}
    assert_differentiation(texts, threshold=0.7)
