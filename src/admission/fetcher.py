"""URL fetching with Playwright, with HTTP fallback."""
from dataclasses import dataclass
from typing import Optional

import urllib.request
import re

from playwright.sync_api import sync_playwright

from .cleaner import clean_html


class InaccessibleURLError(Exception):
    """Raised when a URL cannot be fetched."""


@dataclass
class FetchedContent:
    url: str
    title: Optional[str]
    html: str
    text: str
    login_required: bool = False


def _title_from_html(html: str) -> Optional[str]:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip() or None


def _fetch_with_urllib(url: str) -> tuple[str, Optional[str]]:
    request = urllib.request.Request(url, headers={"User-Agent": "CaseSunoAdmission/1.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        html = response.read().decode(charset, errors="replace")
    return html, _title_from_html(html)


def fetch_url(url: str, timeout_ms: int = 30000) -> FetchedContent:
    html: Optional[str] = None
    title: Optional[str] = None
    playwright_error: Exception | None = None

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            html = page.content()
            title = page.title() or None
            browser.close()
    except Exception as exc:
        playwright_error = exc
        try:
            html, urllib_title = _fetch_with_urllib(url)
            title = urllib_title or title
        except Exception as urllib_exc:
            raise InaccessibleURLError(
                "Nao consegui acessar a pagina nem via navegador nem via HTTP: "
                f"{playwright_error}; {urllib_exc}"
            ) from urllib_exc

    text = clean_html(html or "")
    lowered = text.lower()
    login_required = any(marker in lowered for marker in ["faça login", "sign in", "log in"])
    if login_required:
        raise InaccessibleURLError("Nao consegui acessar a pagina pois exige login, mande por texto")
    return FetchedContent(url=url, title=title, html=html, text=text, login_required=False)