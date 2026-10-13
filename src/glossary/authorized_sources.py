"""Authorized source resolvers for glossary definitions."""
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

import fitz

BCB_PDF_PATH = Path("data") / "source_glossaries" / "glossario_cidadania_financeira.pdf"
BCB_CACHE_PATH = Path("data") / "cache" / "bcb_glossario.json"
B3_SEARCH_URL = "https://borainvestir.b3.com.br/glossario/?termo={term}"


@dataclass
class TermResolution:
    term: str
    found: bool
    definition: str | None = None
    source: str | None = None
    source_url: str | None = None
    status: str = "sem_definicao"


def normalize_term(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _extract_bcb_index_terms(text: str) -> list[str]:
    terms: list[str] = []
    for match in re.finditer(r"(?m)^\d+\.\s+(.+?)\.{2,}\s*\d+\s*$", text):
        term = re.sub(r"\.{2,}", "", match.group(1)).strip()
        if term:
            terms.append(term)
    return terms


def build_bcb_index(pdf_path: str | Path = BCB_PDF_PATH) -> dict[str, str]:
    path = Path(pdf_path)
    if not path.exists():
        return {}
    document = fitz.open(str(path))
    full_text = "\n".join(page.get_text() for page in document)
    document.close()

    terms = _extract_bcb_index_terms(full_text)
    normalized_terms = {normalize_term(term): term for term in terms}
    definitions: dict[str, str] = {}

    current: str | None = None
    lines = full_text.splitlines()
    for line in lines:
        stripped = line.strip()
        normalized_line = normalize_term(stripped)
        if normalized_line in normalized_terms:
            current = normalized_terms[normalized_line]
            definitions[current] = ""
            continue
        if current and stripped:
            # Stop collecting when a new numbered index or page-like line appears.
            if re.match(r"^\d+\.\s+.+\.{2,}\s*\d+\s*$", stripped):
                current = None
                continue
            if stripped.lower().startswith("glossario simplificado"):
                continue
            definitions[current] = (definitions[current] + " " + stripped).strip()
    return definitions


def get_bcb_index(pdf_path: str | Path = BCB_PDF_PATH, cache_path: str | Path = BCB_CACHE_PATH) -> dict[str, str]:
    cache = Path(cache_path)
    if cache.exists():
        try:
            with cache.open("r", encoding="utf-8") as file:
                return json.load(file)
        except (OSError, json.JSONDecodeError):
            pass
    index = build_bcb_index(pdf_path)
    cache.parent.mkdir(parents=True, exist_ok=True)
    with cache.open("w", encoding="utf-8") as file:
        json.dump(index, file, ensure_ascii=False, indent=2)
    return index


class AuthorizedTermResolver:
    def __init__(self, bcb_index: dict[str, str] | None = None, fetch_b3: bool = True) -> None:
        self.bcb_index = bcb_index if bcb_index is not None else get_bcb_index()
        self.fetch_b3 = fetch_b3

    def bcb_lookup(self, term: str) -> TermResolution | None:
        for index_term, definition in self.bcb_index.items():
            if normalize_term(index_term) == normalize_term(term):
                return TermResolution(
                    term=term,
                    found=True,
                    definition=definition,
                    source="BCB",
                    source_url="glossario_cidadania_financeira.pdf",
                    status="encontrado",
                )
        return None

    def b3_lookup(self, term: str) -> TermResolution | None:
        if not self.fetch_b3:
            return None
        url = B3_SEARCH_URL.format(term=quote_plus(term))
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                text = page.inner_text("body")
                browser.close()
        except Exception:
            return None

        pattern = re.compile(r"-\s+(.+?)\n\s+(.+?)(?:\n\s*\[Leia mais\])", re.S)
        candidates = pattern.findall(text)
        normalized_term = normalize_term(term)
        chosen_definition = None
        for title, definition in candidates:
            if normalize_term(title) == normalized_term:
                chosen_definition = definition.strip()
                break
        if chosen_definition is None and candidates:
            # Accept a close first result only if its title contains the requested term.
            for title, definition in candidates:
                if normalized_term in normalize_term(title):
                    chosen_definition = definition.strip()
                    break
        if chosen_definition:
            return TermResolution(
                term=term,
                found=True,
                definition=" ".join(chosen_definition.split()),
                source="B3",
                source_url=url,
                status="encontrado",
            )
        return None

    def resolve(self, term: str) -> TermResolution:
        result = self.bcb_lookup(term)
        if result is not None:
            return result
        result = self.b3_lookup(term)
        if result is not None:
            return result
        return TermResolution(term=term, found=False, status="sem_definicao")