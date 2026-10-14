"""Collection fetchers for primary and headline sources."""

import html
import re
import socket
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class SourceDefinition:
    nome: str
    tipo: str
    prioridade: int
    ativa: bool = True
    url: str = ""
    adapter: str = "rss"


@dataclass
class CollectedItem:
    titulo: str
    nome_fonte: str
    tipo_fonte: str = "primaria"
    url: str = ""
    data_publicacao: str | None = None
    descricao: str | None = None
    categoria: str = "acabou_de_acontecer"
    motivo_entrada: str = "entrada por coleta diaria"
    prioridade: int = 99
    relacionados: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _http_get(url: str, timeout: float = 10.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "CaseSunoCollector/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _parse_rss(xml_text: str, source_name: str, source_type: str, priority: int) -> list[CollectedItem]:
    items: list[CollectedItem] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items
    for element in root.iter("item"):
        title = _clean_text(element.findtext("title"))
        link = _clean_text(element.findtext("link"))
        description = _clean_text(element.findtext("description"))
        pub_date = _clean_text(element.findtext("pubDate"))
        if not title:
            continue
        items.append(
            CollectedItem(
                titulo=title,
                nome_fonte=source_name,
                tipo_fonte=source_type,
                url=link,
                data_publicacao=pub_date or None,
                descricao=description or None,
                prioridade=priority,
                motivo_entrada=f"coleta diaria de {source_name}",
            )
        )
    return items


def load_sources() -> list[SourceDefinition]:
    try:
        import yaml

        with open("config/coleta_fontes.yaml", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        definitions = []
        for raw in data.get("fontes", []):
            definitions.append(
                SourceDefinition(
                    nome=raw["nome"],
                    tipo=raw["tipo"],
                    prioridade=int(raw.get("prioridade", 99)),
                    ativa=bool(raw.get("ativa", True)),
                    url=raw.get("url", ""),
                    adapter=raw.get("adapter", "rss"),
                )
            )
        return definitions
    except Exception:
        return [
            SourceDefinition("BCB", "primaria", 1, url="https://www.bcb.gov.br"),
            SourceDefinition("CVM", "primaria", 2, url="https://www.cvm.gov.br"),
            SourceDefinition("B3", "primaria", 3, url="https://www.b3.com.br"),
            SourceDefinition("IBGE", "primaria", 4, url="https://www.ibge.gov.br"),
            SourceDefinition("Forbes", "manchete", 5, url="https://www.forbes.com.br"),
        ]


def fetch_source(source: SourceDefinition, timeout: float = 10.0) -> list[CollectedItem]:
    if not source.ativa or not source.url:
        return []
    try:
        content = _http_get(source.url, timeout=timeout)
    except (urllib.error.URLError, socket.timeout, TimeoutError, ValueError, OSError):
        return []
    if source.adapter == "rss":
        return _parse_rss(content, source.nome, source.tipo, source.prioridade)
    return []


def fetch_all_sources(timeout: float = 10.0) -> tuple[list[CollectedItem], list[str]]:
    errors: list[str] = []
    items: list[CollectedItem] = []
    for source in load_sources():
        if not source.ativa:
            continue
        source_items = fetch_source(source, timeout=timeout)
        if not source_items:
            errors.append(f"{source.nome}: sem itens ou fonte indisponivel")
        items.extend(source_items)
    return items, errors


def fetch_bcb(*args, **kwargs) -> list[CollectedItem]:
    url = kwargs.get("url", "https://www.bcb.gov.br")
    return fetch_source(SourceDefinition("BCB", "primaria", 1, url=url, adapter=kwargs.get("adapter", "rss")))


def fetch_cvm(*args, **kwargs) -> list[CollectedItem]:
    return fetch_source(SourceDefinition("CVM", "primaria", 2, url=kwargs.get("url", "https://www.cvm.gov.br"), adapter=kwargs.get("adapter", "rss")))


def fetch_b3(*args, **kwargs) -> list[CollectedItem]:
    return fetch_source(SourceDefinition("B3", "primaria", 3, url=kwargs.get("url", "https://www.b3.com.br"), adapter=kwargs.get("adapter", "rss")))


def fetch_ibge(*args, **kwargs) -> list[CollectedItem]:
    return fetch_source(SourceDefinition("IBGE", "primaria", 4, url=kwargs.get("url", "https://www.ibge.gov.br"), adapter=kwargs.get("adapter", "rss")))


def fetch_forbes_headlines(*args, **kwargs) -> list[CollectedItem]:
    source = SourceDefinition("Forbes", "manchete", 5, url=kwargs.get("url", "https://www.forbes.com.br"), adapter=kwargs.get("adapter", "rss"))
    items = fetch_source(source)
    for item in items:
        item.tipo_fonte = "manchete"
        item.motivo_entrada = "manchete sem extração automática"
    return items