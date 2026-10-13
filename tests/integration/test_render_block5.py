from PIL import Image
from pathlib import Path

from src.generation.models import Carousel, Slide
from src.rendering.playwright_renderer import PlaywrightCarouselRenderer

def test_render_carousel_produces_five_pngs():
    carousel = Carousel(slides=[
        Slide(order=i, role="r", title=f"Titulo {i}", body="Corpo", highlight_data="10%")
        for i in range(1, 6)
    ])
    output = Path("data/exports/test_render")
    renderer = PlaywrightCarouselRenderer(output_dir=output)
    files = renderer.render_carousel(carousel, "iniciante", basename="case")
    assert len(files) == 5
    for file in files:
        assert file.exists()
        with Image.open(file) as image:
            assert image.size == (1080, 1350)