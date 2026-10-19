import zipfile
from pathlib import Path

from src.export.carousel_export import create_carousel_zip
from src.export.script_export import to_ai_prompt, to_person_script
from src.export.text_export import to_html, to_markdown
from src.generation.models import AnalyticalText, AnalyticalSection, Script, Scene

def test_text_export_contains_sections():
    text = AnalyticalText(
        title="Titulo", subtitle="Sub",
        introduction=AnalyticalSection(title="Intro", content="Intro content", ponto_ids=["mp1"]),
        development=AnalyticalSection(title="Dev", content="Dev content", ponto_ids=["mp1"]),
        analysis=AnalyticalSection(title="Analise", content="Analise content", ponto_ids=["mp1"]),
        conclusion=AnalyticalSection(title="Conclusao", content="Conclusao content", ponto_ids=["mp1"]),
        covered_main_points=[], word_count_total=40,
        fonte_bloco="Fonte: documento original",
    )
    markdown = to_markdown(text)
    html = to_html(text)
    # intertítulos gerados pelo modelo são mostrados ao leitor (seção 4.6); nomes de papel viram o padrão
    assert "## Intro" in markdown and "## Fonte" in markdown
    assert "<article>" in html


def test_markdown_round_trip_for_human_edit():
    from src.export.text_export import from_markdown

    text = AnalyticalText(
        title="Titulo", subtitle="Sub",
        introduction=AnalyticalSection(title="introduction", content="Intro editada.", ponto_ids=["p1"]),
        development=AnalyticalSection(title="Dados", content="Dev.", ponto_ids=["p2"]),
        analysis=AnalyticalSection(title="Riscos", content="Analise.", ponto_ids=["p3"]),
        conclusion=AnalyticalSection(title="Síntese", content="Fim.", ponto_ids=["p1"]),
        word_count_total=4, fonte_bloco="Fonte: BCB.",
    )
    parsed = AnalyticalText.model_validate(from_markdown(to_markdown(text), text.model_dump()))
    assert parsed.introduction.content == "Intro editada." and parsed.conclusion.title == "Síntese"
    assert parsed.development.ponto_ids == ["p2"] and parsed.fonte_bloco == "Fonte: BCB."
    assert "## Introdução" in to_markdown(text)

def test_script_export_formats_person_and_ai():
    scenes = [
        Scene(
            order=i, role="gancho", start_sec=(i - 1) * 5, end_sec=i * 5,
            fala_escrita="Fala", fala_falada="Fala falada", texto_na_tela="Tela",
            visual="Visual", enquadramento="close", direcao_note=None,
        )
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