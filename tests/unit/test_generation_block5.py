from unittest.mock import patch

from src.extraction.models import ExtractionResult, MainPoint, SourceComplexity
from src.generation.carousel import CarouselGenerator
from src.generation.models import Caption, Carousel, Script
from src.generation.script import ScriptGenerator

EXTRACTION = ExtractionResult(
    main_points=[MainPoint(id="mp1", order=1, title="Ponto central")],
    source_complexity=SourceComplexity(word_count=100),
)

CANNED_CAROUSEL = {
    "carousel": {
        "slides": [
            {"order": 1, "role": "gancho", "title": "Gancho", "body": "Fato da fonte", "highlight_data": "10,50%"},
            {"order": 2, "role": "corpo", "title": "Ponto 1", "body": "Corpo 1", "highlight_data": None},
            {"order": 3, "role": "corpo", "title": "Ponto 2", "body": "Corpo 2", "highlight_data": None},
            {"order": 4, "role": "corpo", "title": "Ponto 3", "body": "Corpo 3", "highlight_data": None},
            {"order": 5, "role": "conclusao", "title": "Conclusao", "body": "Conclusao final", "highlight_data": None},
        ]
    },
    "caption": {
        "opening": "Abertura",
        "short_context": "Contexto",
        "source_block": "Fonte: documento original",
        "cta_verb": "salvar",
        "cta_sentence": "Salve este conteudo.",
        "institutional_notice": None,
        "hashtags": ["#mercado"],
    },
}

CANNED_SCRIPT = {
    "scenes": [
        {"order": 1, "role": "gancho", "start_sec": 0.0, "end_sec": 8.0, "spoken": "Gancho falado.", "screen_text": "Gancho", "visual": "Imagem de abertura", "framing": "close", "direction_note": None},
        {"order": 2, "role": "corpo", "start_sec": 8.0, "end_sec": 20.0, "spoken": "Ponto 1.", "screen_text": "Ponto 1", "visual": "Visual 1", "framing": "plano_medio", "direction_note": None},
        {"order": 3, "role": "corpo", "start_sec": 20.0, "end_sec": 32.0, "spoken": "Ponto 2.", "screen_text": "Ponto 2", "visual": "Visual 2", "framing": "plano_aberto", "direction_note": None},
        {"order": 4, "role": "corpo", "start_sec": 32.0, "end_sec": 44.0, "spoken": "Ponto 3.", "screen_text": "Ponto 3", "visual": "Visual 3", "framing": "close", "direction_note": None},
        {"order": 5, "role": "conclusao", "start_sec": 44.0, "end_sec": 52.0, "spoken": "Conclusao.", "screen_text": "Conclusao", "visual": "Visual final", "framing": "plano_medio", "direction_note": None},
    ],
    "total_duration_sec": 52.0,
}


def test_carousel_generator_returns_carousel_and_caption():
    with patch("src.generation.carousel.LLMClient.generate", return_value=CANNED_CAROUSEL):
        generator = CarouselGenerator()
        carousel, caption = generator.generate(EXTRACTION, "iniciante", "Fonte")
    assert isinstance(carousel, Carousel)
    assert len(carousel.slides) == 5
    assert isinstance(caption, Caption)


def test_script_generator_returns_valid_script():
    with patch("src.generation.script.LLMClient.generate", return_value=CANNED_SCRIPT):
        generator = ScriptGenerator()
        script = generator.generate(EXTRACTION, "iniciante", "Fonte")
    assert isinstance(script, Script)
    assert len(script.scenes) == 5
    assert script.total_duration_sec <= 60