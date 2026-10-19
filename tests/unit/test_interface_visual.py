"""Tela principal: sem perfil/nome do usuário, descrição de card limpa e informações da barra lateral."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from src.app import theme
from src.app.components.news_cards import _initials, card_summary, category_label


def _captured_html(func) -> str:
    with patch.object(theme.st, "markdown") as markdown:
        func()
    return "".join(call.args[0] for call in markdown.call_args_list)


def test_topbar_and_hero_have_no_profile_avatar_or_user_name():
    assert not hasattr(theme, "USER_NAME")
    page = _captured_html(theme.topbar) + _captured_html(theme.hero)
    assert "avatar" not in page and "Ju" not in page and "Julia" not in page
    texto, _ = theme.saudacao()
    assert texto in page and f"{texto}<b class=\"bang\">!</b>" in page


def test_topbar_shows_full_date_in_portuguese():
    assert theme.data_extenso(datetime(2026, 10, 17, tzinfo=theme.TZ)) == "Sábado, 17 de outubro de 2026"
    assert theme.data_extenso(datetime(2026, 3, 2, tzinfo=theme.TZ)) == "Segunda-feira, 2 de março de 2026"


def test_card_summary_strips_html_double_escaped_attributes_and_urls():
    raw = ('&amp;lt;img data-image-caption="Foto" src="https://cdn.x.com/a.jpg"&amp;gt;'
           '<p>O programa <b>Prospera MEI</b> propõe medidas. Leia em https://site.com/noticia</p>')
    assert card_summary(raw) == "O programa Prospera MEI propõe medidas. Leia em"
    assert card_summary(None) == ""


def test_category_and_source_initials_are_readable():
    assert category_label("acabou_de_acontecer") == "Acabou de acontecer"
    assert _initials("Seu Dinheiro") == "SD"
    assert _initials("Banco Central, notas à imprensa") == "BC"
    assert _initials("InfoMoney") == "IN"
    assert _initials("") == "?"


def test_monitored_sources_counts_only_active_feeds(tmp_path):
    config = tmp_path / "fontes.yaml"
    config.write_text("fontes:\n  - nome: A\n    ativa: true\n  - nome: B\n    ativa: false\n  - nome: C\n", encoding="utf-8")
    assert theme.monitored_sources(config) == 2
    assert theme.monitored_sources(tmp_path / "nao_existe.yaml") is None


def test_navigation_keeps_all_pages_with_icons():
    assert [label for _, label, _ in theme.PAGES] == ["Início", "Notícias", "Materiais", "Configurações"]
    assert all(icon and icon.startswith(":material/") for _, _, icon in theme.PAGES)


# ------------------------------------------------------------------ Configurações (glossário)
from src.app.glossary_panel import ALL, INITIAL_VISIBLE, add_pending_term, filter_terms, load_terms  # noqa: E402
from src.glossary.reader import load_glossary  # noqa: E402

TERMS = [
    {"termo": "Selic", "variacoes": ["taxa Selic"], "nivel": "intermediario", "status": "pendente",
     "explicacao_iniciante": "Taxa básica de juros."},
    {"termo": "Inflação", "variacoes": [], "nivel": "iniciante", "status": "aprovado",
     "explicacao_iniciante": "Alta generalizada dos preços."},
    {"termo": "Juros compostos", "variacoes": [], "nivel": "iniciante", "status": "sem_definicao"},
]


def test_glossary_opens_with_five_terms():
    assert INITIAL_VISIBLE == 5
    _data, terms = load_terms()
    assert len(terms) > 5  # o glossário real tem mais termos do que a abertura mostra


def test_search_ignores_accents_and_case_and_looks_at_variations_and_definitions():
    assert [t["termo"] for t in filter_terms(TERMS, "inflacao")] == ["Inflação"]
    assert [t["termo"] for t in filter_terms(TERMS, "TAXA SELIC")] == ["Selic"]
    # nome que começa com a busca vem antes de quem só cita a palavra na explicação
    assert [t["termo"] for t in filter_terms(TERMS, "juros")] == ["Juros compostos", "Selic"]
    assert filter_terms(TERMS, "não existe") == []


def test_level_and_status_filters_combine_with_search():
    assert [t["termo"] for t in filter_terms(TERMS, "", "iniciante", ALL)] == ["Inflação", "Juros compostos"]
    assert [t["termo"] for t in filter_terms(TERMS, "", ALL, "pendente")] == ["Selic"]
    assert filter_terms(TERMS, "selic", "iniciante", ALL) == []


def test_added_term_keeps_glossary_valid_header_and_rejects_duplicates(tmp_path):
    path = tmp_path / "glossario.yaml"
    path.write_text("# cabeçalho\nversao: '1'\ntermos:\n- termo: Selic\n  variacoes: [taxa Selic]\n  nivel: avancado\n"
                    "  status: pendente\n", encoding="utf-8")
    assert add_pending_term("Copom", "intermediario", path) is None
    assert add_pending_term("taxa selic", "iniciante", path) == "'taxa selic' já está no glossário."
    assert add_pending_term("  ", "iniciante", path) == "Informe o termo."
    assert path.read_text(encoding="utf-8").startswith("# cabeçalho\n")
    glossary = load_glossary(path)  # o arquivo continua passando na validação do leitor do pipeline
    copom = glossary.entry_for("Copom")
    assert copom is not None and copom.nivel == "intermediario" and copom.status == "sem_definicao"


def test_status_chip_tone_and_label():
    assert 'class="st-chip ok"' in theme.status_chip("aprovado")
    assert 'class="st-chip bad"' in theme.status_chip("reprovado_nas_metricas")
    assert theme.humanize("aguardando_revisao") == "Aguardando revisão"
    assert ">Não gerado<" in theme.status_chip(None, "Não gerado")


# ------------------------------------------------------------------ logo no menu
def test_sidebar_uses_the_official_logo_white_letters_and_red_brackets():
    import base64
    import io

    from PIL import Image

    html_logo = theme._brand_html()
    assert 'class="brand-logo"' in html_logo and "data:image/png;base64," in html_logo
    data = html_logo.split("base64,", 1)[1].split('"', 1)[0]
    image = Image.open(io.BytesIO(base64.b64decode(data))).convert("RGBA")
    opaque = [image.getpixel((x, y)) for x in range(0, image.width, 3) for y in range(0, image.height, 3)
              if image.getpixel((x, y))[3] > 230]
    whites = [p for p in opaque if min(p[:3]) > 230]
    reds = [p for p in opaque if p[0] > 150 and p[1] < 80 and p[2] < 80]
    assert whites and reds  # letras brancas (fundo escuro) e parênteses vermelhos da marca
    assert not [p for p in opaque if max(p[:3]) < 60]  # nada preto, que sumiria no menu escuro
