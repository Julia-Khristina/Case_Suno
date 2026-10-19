"""Renderização do carrossel com Playwright (seção 4.6), sem LLM.

- Template HTML/CSS em src/rendering/templates/carrossel.html, com tokens de config/tokens_visuais.yaml.
- Fontes e logo carregados dos arquivos do projeto (embutidos em base64); espera document.fonts.ready.
- Mede se o texto coube em cada campo (scrollHeight > clientHeight) e o contraste texto/fundo (WCAG).
- Um PNG 1080×1350 por slide, numerados, e ZIP para exportação.
"""
from __future__ import annotations

import base64
import html
import io
import zipfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = Path(__file__).resolve().parent / "templates" / "carrossel.html"
LINES = {"em cima": ["em-cima"], "duas laterais": ["lateral-esq", "lateral-dir"], "embaixo": ["embaixo"]}

# Texto que não coube: altura do conteúdo acima do limite do campo (max-height do CSS). Folga de 12 px para acentos
# e descidas de letras grandes, que passam da caixa da linha sem cortar o texto.
FIT_SCRIPT = """() => Array.from(document.querySelectorAll('h1, h2, .apoio, .texto, .fonte')).filter(el => {
  const limit = parseFloat(getComputedStyle(el).maxHeight);
  return !isNaN(limit) && el.scrollHeight > limit + 12;
}).map(el => (el.tagName.toLowerCase() + '.' + el.className.replace(/\\s*ajuste\\s*/, '')).replace(/\\.$/, ''))"""


@dataclass
class RenderResult:
    paths: list[Path] = field(default_factory=list)
    overflow: dict[int, list[str]] = field(default_factory=dict)   # slide -> campos em que o texto não coube
    contrast: dict[str, float] = field(default_factory=dict)        # par de cores -> razão de contraste

    @property
    def fits(self) -> bool:
        return not self.overflow


@lru_cache(maxsize=1)
def load_tokens(path: str = "config/tokens_visuais.yaml") -> dict:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8")) or {}


def _font_faces(tokens: dict) -> str:
    family = tokens["fonte"]["familia"]
    faces = []
    for weight, file in sorted((tokens["fonte"].get("arquivos") or {}).items()):
        data = base64.b64encode((ROOT / file).read_bytes()).decode()
        faces.append(f"@font-face{{font-family:'{family}';font-weight:{weight};font-style:normal;"
                     f"src:url(data:font/ttf;base64,{data}) format('truetype');}}")
    return "\n".join(faces)


@lru_cache(maxsize=2)
def logo_data_uri(variant: str = "original") -> str:
    """Logo recortado; a variante 'branca' (para fundo vermelho) vira branca com transparência derivada da tinta."""
    from PIL import Image, ImageChops

    image = Image.open(ROOT / load_tokens()["logo"]).convert("RGBA")
    flat = Image.alpha_composite(Image.new("RGBA", image.size, (255, 255, 255, 255)), image).convert("RGB")
    r, g, b = flat.split()
    # tinta = 255 - min(R, G, B): preto e vermelho são tinta, o fundo branco não
    ink = ImageChops.invert(ImageChops.darker(ImageChops.darker(r, g), b))
    bbox = ink.point(lambda v: 255 if v > 24 else 0).getbbox() or (0, 0, *image.size)
    if variant == "branca":
        white = Image.new("L", image.size, 255)
        out = Image.merge("RGBA", (white, white, white, ink))   # tudo branco, opacidade = tinta
    elif variant == "fundo_escuro":
        # menu escuro da interface: letras pretas viram brancas, os parênteses vermelhos continuam vermelhos
        red_mask = ImageChops.subtract(r, ImageChops.lighter(g, b)).point(lambda v: 255 if v > 60 else 0)
        white = Image.new("RGB", image.size, (255, 255, 255))
        colored = Image.composite(flat, white, red_mask)
        cr, cg, cb = colored.split()
        # vermelho opaco: pela regra da tinta ele sairia ~86% opaco e escureceria sobre o fundo do menu
        out = Image.merge("RGBA", (cr, cg, cb, ImageChops.lighter(ink, red_mask)))
    else:
        out = Image.merge("RGBA", (r, g, b, ink))                # cores originais, fundo transparente
    buffer = io.BytesIO()
    out.crop(bbox).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def contrast_ratio(foreground: str, background: str) -> float:
    def luminance(hex_color: str) -> float:
        hex_color = hex_color.lstrip("#")
        channels = [int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    high, low = sorted((luminance(foreground), luminance(background)), reverse=True)
    return round((high + 0.05) / (low + 0.05), 2)


def _field(slide: Any, name: str):
    return slide.get(name) if isinstance(slide, dict) else getattr(slide, name, None)


def _highlight(value: str | None) -> str:
    if not value:
        return ""
    return f'<div class="destaque"><span class="par">(</span>{html.escape(value)}<span class="par">)</span></div>'


def build_slide_html(slide: Any, index: int, total: int, level: str, source_block: str = "") -> str:
    tokens = load_tokens()
    colors = tokens["cores"]
    role = _field(slide, "role")
    title = html.escape(_field(slide, "title") or "")
    body = html.escape(_field(slide, "body") or "")
    highlight = _field(slide, "highlight_data")
    if role == "gancho":
        kind, background = "capa", "vermelho"
        middle = f'{_highlight(highlight)}<h1 class="ajuste">{title}</h1><p class="apoio ajuste">{body}</p>'
    elif role == "conclusao":
        kind, background = "conclusao", "vermelho"
        middle = f'<h2 class="ajuste">{title}</h2><p class="texto ajuste">{body}</p>'
    else:
        kind, background = "corpo", "branco"
        middle = (f'<div class="indice">PONTO {index - 1} DE {total - 2}</div>{_highlight(highlight)}'
                  f'<h2 class="ajuste">{title}</h2><p class="texto ajuste">{body}</p>')
    line_position = (tokens.get("linha_por_nivel") or {}).get(level, "em cima")
    lines = "".join(f'<div class="linha {css}"></div>' for css in LINES.get(line_position, ["em-cima"]))
    values = {
        "font_faces": _font_faces(tokens), "familia": tokens["fonte"]["familia"],
        "vermelho": colors["vermelho"], "vermelho_escuro": colors["vermelho_escuro"], "branco": colors["branco"],
        "tinta": colors["tinta"], "tinta_suave": colors["tinta_suave"], "vermelho_suave": colors["vermelho_suave"],
        "margem": tokens["slides"]["margem_px"], "largura": tokens["slides"]["largura_px"],
        "altura": tokens["slides"]["altura_px"], "tipo": kind, "fundo": background, "linhas": lines,
        "logo": logo_data_uri("branca" if background == "vermelho" else "original"),
        "pagina": f"{index}/{total}", "rotulo": html.escape((tokens.get("rotulo_nivel") or {}).get(level, level)),
        "miolo": middle, "fonte": html.escape(source_block) if role == "conclusao" else "",
        "seguir": "" if index == total else '<span class="seguir">ARRASTE</span>',
    }
    return Template(TEMPLATE.read_text(encoding="utf-8")).substitute(values)


class PlaywrightCarouselRenderer:
    def __init__(self, output_dir: str | Path = "data/exports") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def render(self, carousel: Any, level: str, basename: str = "carousel", source_block: str | None = None) -> RenderResult:
        from playwright.sync_api import sync_playwright

        slides = list(_field(carousel, "slides") or [])
        caption = _field(carousel, "legenda")
        source = source_block or (_field(caption, "source_block") if caption else "") or ""
        target = self.output_dir / basename
        target.mkdir(parents=True, exist_ok=True)
        tokens = load_tokens()
        width, height = tokens["slides"]["largura_px"], tokens["slides"]["altura_px"]
        colors = tokens["cores"]
        result = RenderResult(contrast={
            "branco_sobre_vermelho": contrast_ratio(colors["branco"], colors["vermelho"]),
            "tinta_sobre_branco": contrast_ratio(colors["tinta"], colors["branco"]),
            "tinta_suave_sobre_branco": contrast_ratio(colors["tinta_suave"], colors["branco"]),
            "vermelho_sobre_branco": contrast_ratio(colors["vermelho"], colors["branco"]),
        })
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": width, "height": height})
            for index, slide in enumerate(slides, start=1):
                page.set_content(build_slide_html(slide, index, len(slides), level, source), wait_until="load")
                page.evaluate("() => document.fonts.ready")
                overflow = page.evaluate(FIT_SCRIPT)
                if overflow:
                    result.overflow[index] = overflow
                path = target / f"slide_{index:02d}.png"
                page.screenshot(path=str(path), type="png")
                result.paths.append(path)
            browser.close()
        return result

    def render_carousel(self, carousel: Any, level: str, basename: str = "carousel") -> list[Path]:
        """Compatibilidade: devolve só os caminhos dos PNGs."""
        return self.render(carousel, level, basename).paths


def zip_slides(paths: list[Path]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, arcname=path.name)
    return buffer.getvalue()
