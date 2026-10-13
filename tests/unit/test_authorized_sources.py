from src.glossary.authorized_sources import AuthorizedTermResolver

def test_bcb_source_resolves_known_term():
    resolver = AuthorizedTermResolver(bcb_index={"Selic": "Taxa de juros básica."}, fetch_b3=False)
    result = resolver.resolve("selic")
    assert result.found is True
    assert result.source == "BCB"
    assert result.proposed_definition if False else result.definition == "Taxa de juros básica."

def test_unknown_term_without_b3_is_sem_definicao():
    resolver = AuthorizedTermResolver(bcb_index={}, fetch_b3=False)
    result = resolver.resolve("termo inexistente")
    assert result.found is False
    assert result.status == "sem_definicao"