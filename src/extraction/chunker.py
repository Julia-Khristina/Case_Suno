"""Sentence-level chunking with source offsets."""
import re
from dataclasses import dataclass


@dataclass
class TextChunk:
    text: str
    start: int
    end: int


def split_into_chunks(text: str, max_characters: int = 3000) -> list[TextChunk]:
    text = text.strip()
    if not text:
        return []

    pieces: list[tuple[int, int, str]] = []
    cursor = 0
    for match in re.finditer(r"(?<=[.!?])\s+", text):
        pieces.append((cursor, match.end(), text[cursor:match.end()]))
        cursor = match.end()
    if cursor < len(text):
        pieces.append((cursor, len(text), text[cursor:]))

    chunks: list[TextChunk] = []
    current_start = pieces[0][0]
    current_text = ""
    for start, end, sentence in pieces:
        candidate = f"{current_text} {sentence}".strip() if current_text else sentence.strip()
        if len(candidate) <= max_characters or not current_text:
            current_text = candidate
        else:
            chunks.append(TextChunk(text=current_text, start=current_start, end=start))
            current_text = sentence.strip()
            current_start = start
    if current_text:
        chunks.append(TextChunk(text=current_text, start=current_start, end=len(text)))
    return chunks or [TextChunk(text=text, start=0, end=len(text))]