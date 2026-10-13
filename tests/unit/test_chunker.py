from src.extraction.chunker import split_into_chunks

def test_chunker_preserves_offsets_and_text():
    text = "Primeira frase. Segunda frase com mais detalhes. Terceira frase final."
    chunks = split_into_chunks(text, max_characters=40)
    assert len(chunks) >= 2
    rebuilt = "".join(chunk.text for chunk in chunks)
    assert "Primeira" in rebuilt
    assert "Terceira" in rebuilt
    assert chunks[0].start == 0
    assert chunks[-1].end == len(text)


def test_chunker_handles_empty_text():
    assert split_into_chunks("") == []