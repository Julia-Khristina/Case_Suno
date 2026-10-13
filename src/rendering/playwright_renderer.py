"""Carousel rendering with Playwright."""
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


class PlaywrightCarouselRenderer:
    def __init__(self, output_dir: str | Path = "data/exports") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def render_carousel(self, carousel: Any, level: str, basename: str = "carousel") -> list[Path]:
        target_dir = self.output_dir / basename
        target_dir.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        for slide in carousel.slides:
            html = self._build_html(slide=slide, level=level)
            output_path = target_dir / f"slide_{slide.order:02d}.png"
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1080, "height": 1350})
                page.set_content(html, wait_until="networkidle")
                page.screenshot(path=str(output_path), type="png")
                browser.close()
            outputs.append(output_path)
        return outputs

    def _build_html(self, slide: Any, level: str) -> str:
        line_position = {
            "iniciante": "top: 32px; left: 48px; right: 48px; height: 4px;",
            "intermediario": "top: 32px; left: 48px; width: 4px; height: calc(100% - 64px);",
            "avancado": "bottom: 32px; left: 48px; right: 48px; height: 4px;",
        }
        secondary_line = ""
        if level == "intermediario":
            secondary_line = "top: 32px; right: 48px; width: 4px; height: calc(100% - 64px);"
        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<style>
body {{
  margin: 0;
  width: 1080px;
  height: 1350px;
  background: #ffffff;
  color: #111111;
  font-family: Arial, sans-serif;
  position: relative;
  box-sizing: border-box;
  padding: 80px 64px;
}}
.level-line {{ position: absolute; background: #c1121f; {line_position.get(level, line_position['iniciante'])} }}
.level-line-secondary {{ position: absolute; background: #c1121f; {secondary_line} }}
h1 {{ font-size: 58px; line-height: 1.15; margin: 0 0 32px 0; color: #c1121f; }}
p {{ font-size: 34px; line-height: 1.35; margin: 0; }}
.highlight {{ margin-top: 32px; font-size: 40px; font-weight: bold; }}
</style>
</head>
<body>
  <div class="level-line"></div>
  {f'<div class="level-line-secondary"></div>' if secondary_line else ''}
  <h1>{slide.title}</h1>
  <p>{slide.body}</p>
  {f'<div class="highlight">{slide.highlight_data}</div>' if slide.highlight_data else ''}
</body>
</html>"""