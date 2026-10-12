"""Origin metadata helpers."""
import re
from datetime import date, datetime
from typing import Optional
from urllib.parse import urlparse

from .models import OriginMetadata

DOMAIN_TO_INSTITUTION = {
    "bcb.gov.br": "Banco Central",
    "www.bcb.gov.br": "Banco Central",
    "cvm.gov.br": "CVM",
    "www.gov.br": "Governo",
    "b3.com.br": "B3",
    "ibge.gov.br": "IBGE",
    "forbes.com.br": "Forbes Brasil",
}


def origin_for_text(
    instituicao: Optional[str] = None,
    titulo: Optional[str] = None,
    data: Optional[date] = None,
    url: Optional[str] = None,
) -> OriginMetadata:
    return OriginMetadata(instituicao=instituicao, titulo=titulo, data=data, url=url)


def origin_for_link(url: str, page_title: Optional[str] = None, page_date: Optional[str] = None) -> OriginMetadata:
    parsed = urlparse(url)
    institution = DOMAIN_TO_INSTITUTION.get(parsed.netloc.lower())
    title = page_title.strip() if page_title else parsed.path.strip("/") or None
    parsed_date = None
    if page_date:
        try:
            parsed_date = datetime.fromisoformat(page_date).date()
        except ValueError:
            parsed_date = None
    return OriginMetadata(instituicao=institution, titulo=title, data=parsed_date, url=url)


def extract_page_title(html: str) -> Optional[str]:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip() or None