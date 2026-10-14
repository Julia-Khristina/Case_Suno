"""Text extraction from digital PDFs."""
from pathlib import Path


class InsufficientPDFTextError(Exception):
    """Raised when a PDF has too little extractable text."""


def extract_pdf_text(path: str | Path, minimum_characters: int = 200) -> str:
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - ambiente sem dependencia
        raise RuntimeError("PyMuPDF (fitz) nao esta instalado; instale pymupdf para PDF digital.") from exc
    document = fitz.open(str(path))
    try:
        text = "\n".join(page.get_text() for page in document)
    finally:
        document.close()
    if len(text.strip()) < minimum_characters:
        raise InsufficientPDFTextError("Extração de PDF insuficiente; cole o texto manualmente.")
    return text.strip()