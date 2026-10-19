"""Template do carrossel (seção 4.6): tipos de slide, linha do nível, logo, fontes do projeto e contraste."""
from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from src.rendering.playwright_renderer import build_slide_html, contrast_ratio, load_tokens, logo_data_uri

SLIDES = [
    {"order": 1, "role": "gancho", "title": "Juros básicos seguem em 10,50%", "body": "Apoio <script>", "highlight_data": "10,50%"},
    {"order": 2, "role": "corpo", "title": "Ponto um", "body": "Texto do ponto.", "highlight_data": None},
    {"order": 5, "role": "conclusao", "title": "Em resumo", "body": "Síntese.", "highlight_data": None},
]


@pytest.mark.parametrize("level,classes", [("iniciante", ["em-cima"]), ("intermediario", ["lateral-esq", "lateral-dir"]),
                                           ("avancado", ["embaixo"])])
def test_level_line_position(level, classes):
    page = build_slide_html(SLIDES[1], 2, 5, level)
    for css in classes:
        assert f'class="linha {css}"' in page
    assert page.count('class="linha ') == len(classes)


def test_cover_is_red_with_white_logo_highlight_and_escaped_text():
    page = build_slide_html(SLIDES[0], 1, 5, "iniciante")
    assert 'class="slide capa vermelho"' in page
    assert 'class="destaque"><span class="par">(</span>10,50%' in page
    assert "&lt;script&gt;" in page and "<script>" not in page.split("<body>")[1]
    assert logo_data_uri("branca") in page
    assert "ARRASTE" in page and ">1/5<" in page


def test_body_slide_is_white_with_point_index_and_conclusion_has_source():
    body = build_slide_html(SLIDES[1], 2, 5, "intermediario")
    assert 'class="slide corpo branco"' in body and "PONTO 1 DE 3" in body
    assert logo_data_uri("original") in body
    end = build_slide_html(SLIDES[2], 5, 5, "avancado", source_block="Fonte: BCB, Ata do Copom, 13/10/2026.")
    assert 'class="slide conclusao vermelho"' in end and "Fonte: BCB, Ata do Copom" in end
    assert "ARRASTE" not in end


def test_label_shown_is_separate_from_internal_level_name():
    assert "Análise avançada" in build_slide_html(SLIDES[1], 2, 5, "avancado")
    assert ">avancado<" not in build_slide_html(SLIDES[1], 2, 5, "avancado")


def test_project_fonts_are_embedded_not_loaded_from_the_internet():
    page = build_slide_html(SLIDES[0], 1, 5, "iniciante")
    assert page.count("@font-face") == len(load_tokens()["fonte"]["arquivos"])
    assert "fonts.googleapis.com" not in page and "data:font/ttf;base64," in page


def test_white_logo_variant_is_white_on_transparent():
    data = logo_data_uri("branca").split(",", 1)[1]
    image = Image.open(io.BytesIO(base64.b64decode(data))).convert("RGBA")
    opaque = [image.getpixel((x, y)) for x in range(0, image.width, 4) for y in range(0, image.height, 4)
              if image.getpixel((x, y))[3] > 200]
    assert opaque and all(p[:3] == (255, 255, 255) for p in opaque)
    assert image.getpixel((0, image.height - 1))[3] < 50 or image.getpixel((image.width - 1, 0))[3] < 50


def test_palette_contrast_meets_wcag_aa():
    colors = load_tokens()["cores"]
    assert contrast_ratio(colors["branco"], colors["vermelho"]) >= 4.5
    assert contrast_ratio(colors["tinta"], colors["branco"]) >= 4.5
    assert contrast_ratio(colors["tinta_suave"], colors["branco"]) >= 4.5
