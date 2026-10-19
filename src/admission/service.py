"""Admission orchestration."""
from datetime import date
from pathlib import Path
from typing import Iterable

from .classification import classify_text
from .language import detect_language
from .models import AdmissionResult, OriginMetadata
from .partiality_checks import check_partiality
from .origin import origin_for_link, origin_for_text, extract_page_title
from .fetcher import fetch_url
from .pdf_text import extract_pdf_text
from src.glossary.reader import load_glossary_terms


DEFAULT_GLOSSARY_PATH = "config/glossario.yaml"


def _terms(glossary_terms: Iterable[str] | None) -> list[str]:
    if glossary_terms is None:
        return load_glossary_terms(DEFAULT_GLOSSARY_PATH)
    return list(glossary_terms)


def admit_text(
    text: str,
    origin: OriginMetadata | None = None,
    glossary_terms: Iterable[str] | None = None,
    min_characters: int = 500,
) -> AdmissionResult:
    normalized = text.strip()
    partiality = check_partiality(normalized, min_characters=min_characters)
    language = detect_language(normalized)
    terms = _terms(glossary_terms)
    classification = classify_text(normalized, terms)
    origin = origin or OriginMetadata()

    if partiality.is_partial:
        status = "bloqueado"
    elif language != "pt":
        status = "aviso"
    elif classification["financial_rule_passed"]:
        status = "admitido"
    else:
        status = "aviso"

    return AdmissionResult(
        is_partial=partiality.is_partial,
        partial_reasons=partiality.reasons,
        is_financial=classification["is_financial"],
        financial_rule_passed=classification["financial_rule_passed"],
        distinct_glossary_terms=classification["distinct_glossary_terms"],
        word_count=classification["word_count"],
        structured_type=classification["structured_type"],
        language=language,
        origin=origin,
        status=status,
        text=normalized,
    )


def admit_url(
    url: str,
    glossary_terms: Iterable[str] | None = None,
    min_characters: int = 500,
) -> AdmissionResult:
    fetched = fetch_url(url)
    title = extract_page_title(fetched.html) or fetched.title
    origin = origin_for_link(url, title)
    return admit_text(
        fetched.text,
        origin=origin,
        glossary_terms=glossary_terms,
        min_characters=min_characters,
    )


def admit_pdf(
    path: str | Path,
    origin: OriginMetadata | None = None,
    glossary_terms: Iterable[str] | None = None,
    min_characters: int = 500,
) -> AdmissionResult:
    text = extract_pdf_text(path)
    return admit_text(
        text,
        origin=origin,
        glossary_terms=glossary_terms,
        min_characters=min_characters,
    )