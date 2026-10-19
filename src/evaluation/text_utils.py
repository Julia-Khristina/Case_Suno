"""Utilitários de texto compartilhados pelas métricas determinísticas (português do Brasil)."""
from __future__ import annotations

import re
import unicodedata

WORD_RE = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", re.UNICODE)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[\"'(«A-ZÀ-Ý0-9])|\n+")

STOPWORDS = frozenset("""
a o os as um uma uns umas de da do das dos dum duma em no na nos nas num numa por pelo pela pelos pelas
para pra com sem sob sobre entre até após ante contra desde e ou mas nem que se como quando onde porque pois
já não sim mais menos muito muita muitos muitas pouco pouca também ainda só apenas isso isto esse essa esses
essas este esta estes estas aquele aquela aqueles aquelas ele ela eles elas seu sua seus suas lhe lhes me te
nos vos ao aos à às é são foi foram ser está estão estava era há tem têm ter vai vão pode podem deve devem
segundo conforme cada qual quais todo toda todos todas outro outra outros outras mesmo mesma já tal
""".split())


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def words(text: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(normalize(text))]


def word_count(text: str) -> int:
    return len(WORD_RE.findall(normalize(text)))


def sentences(text: str) -> list[str]:
    parts = [p.strip() for p in SENTENCE_SPLIT_RE.split(normalize(text))]
    return [p for p in parts if WORD_RE.search(p)]


def stem(word: str) -> str:
    """Radical simples (prefixo de 5 letras sem acento) para tolerar flexões: elevado/elevada/elevados."""
    base = unicodedata.normalize("NFKD", word.lower())
    base = "".join(c for c in base if not unicodedata.combining(c))
    return base[:5]


def content_stems(text: str) -> set[str]:
    return {stem(w) for w in words(text) if len(w) >= 4 and w not in STOPWORDS and not w.isdigit()}


def trigrams(text: str) -> list[tuple[str, str, str]]:
    ws = words(text)
    return [tuple(ws[i:i + 3]) for i in range(len(ws) - 2)]


def jaccard_trigrams(left: str, right: str) -> float:
    a, b = set(trigrams(left)), set(trigrams(right))
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)
