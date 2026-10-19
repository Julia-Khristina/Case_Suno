"""Collection fetchers for RSS 2.0 and Atom feeds (seção 4.1).

Além de título, link, data e descrição, guarda o texto completo do artigo quando o feed o traz
(content:encoded no RSS, content no Atom), para o card já nascer com o documento que alimenta a geração.
"""
from __future__ import annotations

import html
import re
import socket
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from typing import Any

CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
_FEED_TRAILER_RE = re.compile(r"(O post|The post)\s.{0,300}?(apareceu primeiro em|appeared first on)\s.{0,120}$",
                              re.IGNORECASE | re.DOTALL)
_BLOCK_TAG_RE = re.compile(r"</?(p|div|br|li|h[1-6]|blockquote|tr)\b[^>]*>", re.IGNORECASE)
_DROP_RE = re.compile(r"<(script|style|figure|figcaption|iframe)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)


@dataclass
class SourceDefinition:
    nome: str
    tipo: str
    prioridade: int
    ativa: bool = True
    url: str = ""
    adapter: str = "rss"
    texto_completo: str = "feed"  # "feed": vem no feed; "pagina": lido da página da matéria quando o feed não traz


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
    conteudo: str | None = None  # texto completo do feed, já limpo

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _http_get(url: str, timeout: float = 10.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def html_to_text(value: str | None) -> str:
    """Texto do artigo a partir do HTML do feed: preserva parágrafos, remove figuras, scripts e rodapé do feed."""
    if not value:
        return ""
    text = _DROP_RE.sub(" ", html.unescape(value))
    text = _BLOCK_TAG_RE.sub("\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    paragraphs = [re.sub(r"[ \t\xa0]+", " ", p).strip() for p in text.split("\n")]
    text = "\n\n".join(p for p in paragraphs if p)
    return _FEED_TRAILER_RE.sub("", text).strip()


def _iso_date(value: str | None) -> str | None:
    """Data de publicação em ISO (RFC 822 do RSS ou ISO 8601 do Atom)."""
    if not value:
        return None
    from email.utils import parsedate_to_datetime

    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    return value[:10] if re.match(r"\d{4}-\d{2}-\d{2}", value) else None


def _root(xml_text: str):
    return ET.fromstring(xml_text.lstrip("﻿").strip())


def _parse_rss(xml_text: str, source_name: str, source_type: str, priority: int) -> list[CollectedItem]:
    items: list[CollectedItem] = []
    try:
        root = _root(xml_text)
    except ET.ParseError:
        return items
    for element in root.iter("item"):
        title = _clean_text(element.findtext("title"))
        if not title:
            continue
        description = html_to_text(element.findtext("description")).replace("\n\n", " ")
        items.append(CollectedItem(
            titulo=title, nome_fonte=source_name, tipo_fonte=source_type,
            url=_clean_text(element.findtext("link")),
            data_publicacao=_iso_date(_clean_text(element.findtext("pubDate"))),
            descricao=_FEED_TRAILER_RE.sub("", description).strip() or None,
            prioridade=priority, motivo_entrada=f"coleta diaria de {source_name}",
            conteudo=html_to_text(element.findtext(CONTENT_NS)) or None,
        ))
    return items


def _parse_atom(xml_text: str, source_name: str, source_type: str, priority: int) -> list[CollectedItem]:
    items: list[CollectedItem] = []
    try:
        root = _root(xml_text)
    except ET.ParseError:
        return items
    for entry in root.iter(f"{ATOM_NS}entry"):
        title = _clean_text(entry.findtext(f"{ATOM_NS}title"))
        if not title:
            continue
        link_el = entry.find(f"{ATOM_NS}link[@rel='alternate']")
        if link_el is None:
            link_el = entry.find(f"{ATOM_NS}link")
        link = (link_el.get("href") if link_el is not None else "") or ""
        content = html_to_text(entry.findtext(f"{ATOM_NS}content") or entry.findtext(f"{ATOM_NS}summary"))
        summary = html_to_text(entry.findtext(f"{ATOM_NS}summary")).replace("\n\n", " ") or \
            " ".join(content.split()[:60])
        updated = _clean_text(entry.findtext(f"{ATOM_NS}updated") or entry.findtext(f"{ATOM_NS}published"))
        items.append(CollectedItem(
            titulo=title, nome_fonte=source_name, tipo_fonte=source_type, url=link.strip(),
            data_publicacao=_iso_date(updated), descricao=summary or None, prioridade=priority,
            motivo_entrada=f"coleta diaria de {source_name}", conteudo=content or None,
        ))
    return items


_ROBOTS: dict[str, Any] = {}
_PARAGRAPH_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)
_LD_JSON_RE = re.compile(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)
USER_AGENT = "CaseSunoCollector/1.0"


def allowed_by_robots(url: str) -> bool:
    """Respeita o robots.txt do site (cache por domínio); sem robots legível, permite."""
    import urllib.parse
    import urllib.robotparser

    parts = urllib.parse.urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _ROBOTS:
        parser = urllib.robotparser.RobotFileParser(base + "/robots.txt")
        try:
            parser.read()
        except Exception:  # noqa: BLE001
            parser = None
        _ROBOTS[base] = parser
    parser = _ROBOTS[base]
    return True if parser is None else parser.can_fetch(USER_AGENT, url)


def article_text(html_text: str, min_words: int = 12) -> str:
    """Corpo da matéria: `articleBody` do JSON-LD, ou os parágrafos com pelo menos `min_words` palavras."""
    import json

    for block in _LD_JSON_RE.findall(html_text or ""):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        nodes = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for node in nodes:
            if isinstance(node, dict) and len(str(node.get("articleBody") or "").split()) >= 80:
                return html_to_text(str(node["articleBody"]))
    seen, paragraphs = set(), []
    for raw in _PARAGRAPH_RE.findall(html_text or ""):
        paragraph = html_to_text(raw).replace("\n\n", " ")
        if len(paragraph.split()) >= min_words and paragraph not in seen:
            seen.add(paragraph)
            paragraphs.append(paragraph)
    return _FEED_TRAILER_RE.sub("", "\n\n".join(paragraphs)).strip()


def fetch_article_text(url: str, timeout: float = 10.0) -> str | None:
    """Texto completo lido da página da matéria (só se o robots.txt permitir). None se não houver texto."""
    if not url or not allowed_by_robots(url):
        return None
    try:
        page = _http_get(url, timeout=timeout)
    except (urllib.error.URLError, socket.timeout, TimeoutError, ValueError, OSError):
        return None
    return article_text(page) or None


def load_sources() -> list[SourceDefinition]:
    try:
        import yaml

        with open("config/coleta_fontes.yaml", encoding="utf-8-sig") as file:
            data = yaml.safe_load(file) or {}
        return [
            SourceDefinition(nome=raw["nome"], tipo=raw["tipo"], prioridade=int(raw.get("prioridade", 99)),
                             ativa=bool(raw.get("ativa", True)), url=raw.get("url", ""), adapter=raw.get("adapter", "rss"),
                             texto_completo=str(raw.get("texto_completo", "feed")))
            for raw in data.get("fontes", [])
        ]
    except Exception:  # noqa: BLE001
        return []


def fetch_source(source: SourceDefinition, timeout: float = 10.0) -> list[CollectedItem]:
    if not source.ativa or not source.url:
        return []
    try:
        content = _http_get(source.url, timeout=timeout)
    except (urllib.error.URLError, socket.timeout, TimeoutError, ValueError, OSError):
        return []
    if source.adapter == "rss":
        return _parse_rss(content, source.nome, source.tipo, source.prioridade)
    if source.adapter == "atom":
        return _parse_atom(content, source.nome, source.tipo, source.prioridade)
    return []


def fetch_all_sources(timeout: float = 10.0, sources: list[SourceDefinition] | None = None) -> tuple[list[CollectedItem], list[str]]:
    errors: list[str] = []
    items: list[CollectedItem] = []
    for source in sources if sources is not None else load_sources():
        if not source.ativa:
            continue
        source_items = fetch_source(source, timeout=timeout)
        if not source_items:
            errors.append(f"{source.nome}: sem itens ou fonte indisponivel")
        items.extend(source_items)
    return items, errors


def fetch_bcb(*args, **kwargs) -> list[CollectedItem]:
    url = kwargs.get("url", "https://www.bcb.gov.br/api/feed/sitebcb/sitefeeds/notasImprensa?ano=2026")
    return fetch_source(SourceDefinition("BCB", "primaria", 1, url=url, adapter=kwargs.get("adapter", "atom")))


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
