"""URL fetching with Playwright."""
from dataclasses import dataclass
from typing import Optional

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


def fetch_url(url: str, timeout_ms: int = 30000) -> FetchedContent:
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            html = page.content()
            title = page.title() or None
            browser.close()
    except Exception as exc:
        raise InaccessibleURLError(f"Não consegui acessar a página: {exc}") from exc

    text = clean_html(html)
    lowered = text.lower()
    login_required = any(marker in lowered for marker in ["faça login", "sign in", "log in"])
    if login_required:
        raise InaccessibleURLError("Não consegui acessar a página pois exige login, mande por texto")
    return FetchedContent(url=url, title=title, html=html, text=text, login_required=False)