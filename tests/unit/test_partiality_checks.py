from src.admission.partiality_checks import check_partiality

LONG_COMPLETE = "a" * 600 + "."
LONG_WITH_PAYWALL = ("a" * 600 + " assine para continuar")


def test_complete_long_text_is_not_partial():
    result = check_partiality(LONG_COMPLETE)
    assert result.is_partial is False
    assert result.reasons == []


def test_short_text_is_partial():
    result = check_partiality("texto curto")
    assert result.is_partial is True
    assert "tamanho_minimo_nao_atingido" in result.reasons


def test_text_without_sentence_ending_is_partial():
    result = check_partiality("a" * 600)
    assert result.is_partial is True
    assert "texto_nao_termina_em_frase_completa" in result.reasons


def test_paywall_marker_is_partial():
    result = check_partiality(LONG_WITH_PAYWALL)
    assert result.is_partial is True
    assert "marcador_de_paywall_encontrado" in result.reasons