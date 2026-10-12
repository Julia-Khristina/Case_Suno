from src.admission.cleaner import clean_html, has_paywall_marker

def test_clean_html_removes_tags_and_scripts():
    html = "<html><script>alert(1)</script><p>Texto limpo</p></html>"
    assert clean_html(html) == "Texto limpo"


def test_has_paywall_marker_detects_marker():
    assert has_paywall_marker("Leia mais, assine para continuar") is True
    assert has_paywall_marker("Texto normal sem paywall") is False