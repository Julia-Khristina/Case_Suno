from src.admission.origin import origin_for_link, origin_for_text

def test_origin_for_text_without_data_uses_user_label():
    origin = origin_for_text(titulo=None, instituicao=None)
    assert origin.to_source_label() == "texto enviado pelo usuario"


def test_origin_for_link_infers_institution_from_domain():
    origin = origin_for_link("https://www.bcb.gov.br/publicacoes/atascopom/cronologicos", page_title="Atas")
    assert origin.instituicao == "Banco Central"
    assert origin.titulo == "Atas"


def test_origin_label_from_complete_metadata():
    from datetime import date
    origin = origin_for_text(instituicao="CVM", titulo="Fato relevante", data=date(2026,10,1))
    assert origin.to_source_label() == "CVM: Fato relevante, 2026-10-01"