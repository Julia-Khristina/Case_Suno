"""Cleaning helpers for collected HTML and text."""

import html
import re
from typing import Any

HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def clean_html_text(value: str | None) -> str:
    if not value:
        return ""
    without_tags = HTML_TAG_RE.sub(" ", value)
    return WHITESPACE_RE.sub(" ", html.unescape(without_tags)).strip()


def clean_item(item: Any) -> Any:
    if isinstance(item, dict):
        item["titulo"] = clean_html_text(item.get("titulo") or item.get("title") or item.get("titulo_card"))
        item["descricao"] = clean_html_text(item.get("descricao") or item.get("description")) or item.get("descricao")
        item["url"] = (item.get("url") or item.get("source_url") or "").strip()
        return item
    try:
        item.titulo = clean_html_text(getattr(item, "titulo", None))
        item.descricao = clean_html_text(getattr(item, "descricao", None)) or item.descricao
        item.url = getattr(item, "url", "").strip()
    except Exception:
        pass
    return item