"""Text extraction from digital PDFs."""
from pathlib import Path

import fitz


class InsufficientPDFTextError(Exception):
    """Raised when a PDF has too little extractable text."""


def extract_pdf_text(path: str | Path, minimum_characters: int = 200) -> str:
    document = fitz.open(str(path))
    try:
        text = "\n".join(page.get_text() for page in document)
    finally:
        document.close()
    if len(text.strip()) < minimum_characters:
        raise InsufficientPDFTextError("Extração de PDF insuficiente; cole o texto manualmente.")
    return text.strip()