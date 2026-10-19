"""Verifica fontes candidatas antes de ativá-las (seção 4.1: feeds, robots.txt e termos de uso precedem a coleta).

Para cada feed: responde? quantos itens? traz o texto completo (content:encoded)? quantas palavras em média?
robots.txt permite o caminho do feed e o das notícias? Termos de uso NÃO são verificáveis automaticamente.

Uso: python scripts/verify_sources.py [--config]   (sem --config usa a lista de candidatos abaixo)
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

USER_AGENT = "CaseSunoCollector/1.0"
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"

CANDIDATES = [
    ("InfoMoney (geral)", "https://www.infomoney.com.br/feed/"),
    ("InfoMoney, mercados", "https://www.infomoney.com.br/mercados/feed/"),
    ("InfoMoney, economia", "https://www.infomoney.com.br/economia/feed/"),
    ("InfoMoney, negócios", "https://www.infomoney.com.br/negocios/feed/"),
    ("InfoMoney, onde investir", "https://www.infomoney.com.br/onde-investir/feed/"),
    ("Money Times", "https://www.moneytimes.com.br/feed/"),
    ("Seu Dinheiro", "https://www.seudinheiro.com/feed/"),
    ("E-Investidor (Estadão)", "https://einvestidor.estadao.com.br/feed/"),
    ("Investing.com Brasil, notícias", "https://br.investing.com/rss/news.rss"),
    ("Exame", "https://exame.com/feed/"),
    ("Agência Brasil, economia", "https://agenciabrasil.ebc.com.br/rss/economia/feed.xml"),
    ("Banco Central, notas à imprensa", "https://www.bcb.gov.br/api/feed/sitebcb/sitefeeds/notasImprensa?ano=2026"),
    ("Banco Central, notícias", "https://www.bcb.gov.br/api/feed/sitebcb/sitefeeds/noticias?ano=2026"),
    ("IBGE, Agência de Notícias", "https://agenciadenoticias.ibge.gov.br/agencia-noticias.html?format=feed&type=rss"),
    ("CVM, notícias", "https://www.gov.br/cvm/pt-br/assuntos/noticias/RSS"),
]


def _get(url: str, timeout: float = 15.0) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.status, response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


def _robots_allows(url: str, sample: str | None) -> dict:
    parts = urlparse(url)
    parser = urllib.robotparser.RobotFileParser()
    status, body = _get(f"{parts.scheme}://{parts.netloc}/robots.txt")
    if status != 200:
        return {"robots": f"indisponível ({status})", "feed": None, "noticia": None}
    parser.parse(body.splitlines())
    return {"robots": "ok", "feed": parser.can_fetch(USER_AGENT, url),
            "noticia": parser.can_fetch(USER_AGENT, sample) if sample else None}


def verify(name: str, url: str) -> dict:
    status, body = _get(url)
    row = {"fonte": name, "url": url, "http": status, "itens": 0, "texto_completo": 0, "palavras_media": 0}
    if status != 200:
        return {**row, **_robots_allows(url, None)}
    try:
        root = ET.fromstring(body.encode("utf-8") if body.startswith("<?xml") is False else body.encode("utf-8"))
    except ET.ParseError:
        return {**row, "erro": "XML inválido", **_robots_allows(url, None)}
    items = list(root.iter("item"))
    full = [i.findtext(CONTENT_NS) or "" for i in items]
    words = [len(re.sub(r"<[^>]+>", " ", f).split()) for f in full if f]
    sample = (items[0].findtext("link") or "").strip() if items else None
    row.update(itens=len(items), texto_completo=len(words), palavras_media=int(sum(words) / len(words)) if words else 0,
               exemplo=(items[0].findtext("title") or "").strip()[:80] if items else "")
    return {**row, **_robots_allows(url, sample)}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--config" in sys.argv:
        import yaml

        data = yaml.safe_load(Path("config/coleta_fontes.yaml").read_text(encoding="utf-8"))
        targets = [(f["nome"], f["url"]) for f in data.get("fontes", [])]
    else:
        targets = CANDIDATES
    for name, url in targets:
        print(json.dumps(verify(name, url), ensure_ascii=False))
