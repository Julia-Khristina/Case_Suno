"""Renderização real com Playwright: 5 PNGs 1080×1350, linha do nível e detecção de texto que não coube."""
from pathlib import Path

from PIL import Image

from src.generation.carousel import finalize_carousel
from src.rendering.playwright_renderer import PlaywrightCarouselRenderer, zip_slides
from tests.fakes.content import ORIGIN, good_output


def _carousel(level):
    return finalize_carousel(good_output("carrossel", "iniciante"), level, ORIGIN, [], "teste")


def test_render_carousel_produces_five_pngs(tmp_path):
    result = PlaywrightCarouselRenderer(output_dir=tmp_path).render(_carousel("iniciante"), "iniciante", basename="case")
    assert len(result.paths) == 5 and result.fits
    for file in result.paths:
        with Image.open(file) as image:
            assert image.size == (1080, 1350)
    with Image.open(result.paths[1]) as body:  # slide de corpo é branco com a linha vermelha em cima
        assert body.getpixel((540, 600))[:3] == (255, 255, 255)
        assert body.getpixel((540, 47))[0] > 150 and body.getpixel((540, 47))[1] < 60
    assert zip_slides(result.paths)[:2] == b"PK"


def test_text_that_does_not_fit_is_reported(tmp_path):
    carousel = _carousel("avancado")
    carousel.slides[2].body = carousel.slides[2].body * 8
    result = PlaywrightCarouselRenderer(output_dir=tmp_path).render(carousel, "avancado", basename="longo")
    assert not result.fits and 3 in result.overflow
