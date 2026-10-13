import zipfile
from pathlib import Path

from src.export.carousel_export import create_carousel_zip
from src.export.script_export import to_ai_prompt, to_person_script
from src.export.text_export import to_html, to_markdown
from src.generation.models import AnalyticalText, Script, Scene

def test_text_export_contains_sections():
    text = AnalyticalText(
        title="Titulo", subtitle="Sub", introduction="Intro", development="Dev",
        analysis="Analise", conclusion="Conclusao", covered_main_points=[], word_count_total=10
    )
    markdown = to_markdown(text)
    html = to_html(text)
    assert "## Introdução" in markdown
    assert "<article>" in html

def test_script_export_formats_person_and_ai():
    scenes = [
        Scene(order=i, role="gancho", start_sec=(i - 1) * 5, end_sec=i * 5, spoken="Fala", screen_text="Tela", visual="Visual", framing="close")
        for i in range(1, 6)
    ]
    script = Script(scenes=scenes, total_duration_sec=25.0)
    assert "Cena 1" in to_person_script(script)
    assert "Video vertical" in to_ai_prompt(script)

def test_zip_export_creates_archive(tmp_path):
    image = tmp_path / "slide.png"
    image.write_bytes(b"fake")
    output = create_carousel_zip([image], tmp_path / "carousel.zip")
    assert output.exists()
    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == ["slide.png"]