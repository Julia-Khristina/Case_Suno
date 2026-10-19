"""Pautas: notícias de fontes diferentes sobre o mesmo assunto, agrupadas na coleta (decisão de 18/10/2026).

Regras determinísticas, sem LLM:
1. Entidades do título e da descrição: códigos de ações (BRKM5), siglas (IPCA, BTG), nomes próprios (Braskem,
   Banco Central) e termos técnicos do glossário. Cada entidade pesa pelo quanto é rara no acervo (IDF): "Brasil"
   aparece em muitas notícias e quase não liga duas; "Braskem" aparece em poucas e liga.
2. Semelhança = cosseno TF-IDF dos radicais do título (peso 2), da descrição e das primeiras 250 palavras do
   texto. Duas notícias só se ligam se forem de fontes diferentes, estiverem na janela de horas e passarem do
   limiar dividindo uma entidade específica, ou passarem do limiar alto mesmo sem ela. Calibração em 18/10/2026
   com 47 notícias financeiras de 7 feeds: pares verdadeiros 0,77 e 0,66; maior par falso 0,37 (sem entidade em
   comum) e 0,34 (com entidade: resumo do pregão que cita a Cosan x notícia da Cosan).
3. Agrupamento guloso por ligação média: cada notícia entra na pauta com maior semelhança média aos membros,
   se passar do limiar; no máximo uma notícia por fonte e `max_fontes` por pauta.
4. Fontes independentes: a mesma matéria de agência (Reuters, Estadão Conteúdo...) publicada em dois sites, o
   mesmo título ou a mesma descrição contam como uma origem só.

Os limiares são provisórios (config/coleta_fontes.yaml, seção `pautas`) e devem ser calibrados com a coleta real.
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable

from collections import Counter

from src.evaluation.text_utils import STOPWORDS, stem, words

TICKER_RE = re.compile(r"\b[A-Z]{4}(?:3|4|5|6|11)\b")
ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,5}\b")
NAME_RE = re.compile(r"\b[A-ZÀ-Ý][\wÀ-ÿ'’.-]*(?:\s+(?:de|da|do|das|dos|e)?\s*[A-ZÀ-Ý][\wÀ-ÿ'’.-]*)*")
# Palavras que aparecem com maiúscula por começarem a frase ou por convenção editorial, sem indicar assunto.
GENERIC_CAPITALIZED = frozenset("""
veja entenda confira saiba tem nova novo novos novas sobe cai caem sobem alta queda após antes hoje ontem amanhã
segunda terça quarta quinta sexta sábado domingo janeiro fevereiro março abril maio junho julho agosto setembro
outubro novembro dezembro por que qual quais quem como onde quando mais menos melhor pior maior menor primeiro
última último especialistas analistas mercado mercados investidores ações bolsa dólar real governo empresa
empresas país brasil brasileiro brasileira brasileiros brasileiras
""".split())
GENERIC_ACRONYMS = frozenset({"EUA", "UE", "PT", "PL", "ONU", "SA", "S.A", "CEO", "TV", "IA", "AI", "US", "UK"})
AGENCY_RE = re.compile(
    r"\b(Reuters|Bloomberg|AFP|Associated Press|Estad[ãa]o Conte[úu]do|Ag[êe]ncia Estado|Ag[êe]ncia Brasil|"
    r"Broadcast|Valor PRO|Dow Jones)\b", re.IGNORECASE)
AGENCY_CREDIT_RE = re.compile(
    r"(?:\((?:{a})\)|(?:com informa[çc][õo]es|informa[çc][õo]es)\s+(?:da|do|de)\s+(?:{a})|(?:fonte|por|via):?\s+(?:{a}))"
    .format(a=AGENCY_RE.pattern[3:-3]), re.IGNORECASE)


def fold(text: str) -> str:
    base = unicodedata.normalize("NFKD", (text or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in base if not unicodedata.combining(c))).strip(" .-'’")


def _field(item: Any, name: str):
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


def extract_entities(title: str, description: str = "", glossary=None) -> dict[str, str]:
    """Entidades normalizadas → tipo (ticker, sigla, nome, termo)."""
    text = f"{title or ''}. {description or ''}"
    found: dict[str, str] = {}
    for ticker in TICKER_RE.findall(text):
        found[fold(ticker)] = "ticker"
        found.setdefault(fold(ticker[:4]), "ticker")  # BRKM5 e BRKM3 são a mesma empresa
    for acronym in ACRONYM_RE.findall(text):
        if acronym in GENERIC_ACRONYMS or TICKER_RE.fullmatch(acronym) or acronym.isdigit():
            continue
        found.setdefault(fold(acronym), "sigla")
    for match in NAME_RE.finditer(text):
        words = match.group(0).split()
        # tira palavras genéricas das pontas ("Veja Braskem" → "Braskem"; "Ações da Petrobras" → "Petrobras")
        while words and (fold(words[0]) in GENERIC_CAPITALIZED or fold(words[0]) in STOPWORDS):
            words = words[1:]
        while words and (fold(words[-1]) in GENERIC_CAPITALIZED or fold(words[-1]) in STOPWORDS):
            words = words[:-1]
        name = fold(" ".join(words))
        if len(name) < 3 or name.upper() in GENERIC_ACRONYMS or TICKER_RE.fullmatch(" ".join(words)):
            continue
        if all(fold(w) in GENERIC_CAPITALIZED or fold(w) in STOPWORDS for w in words):
            continue
        found.setdefault(name, "nome")
    if glossary is not None:
        for entry, _form, _pos in glossary.find_in_text(text, technical_only=True):
            found.setdefault(fold(entry.termo), "termo")
    return found


def agency_of(text: str | None) -> str | None:
    """Agência creditada no texto ("(Reuters)", "com informações da Reuters", "Estadão Conteúdo")."""
    match = AGENCY_CREDIT_RE.search(text or "")
    if not match:
        return None
    name = AGENCY_RE.search(match.group(0))
    return fold(name.group(0)) if name else None


@dataclass
class PautaItem:
    """Notícia candidata a pauta (do feed desta coleta ou do acervo das últimas horas)."""
    key: str
    titulo: str
    nome_fonte: str
    descricao: str = ""
    url: str = ""
    tipo_fonte: str = "secundaria"
    prioridade: int = 99
    data_publicacao: str | None = None
    conteudo: str | None = None
    agencia: str | None = None
    entidades: dict[str, str] = field(default_factory=dict)
    bag: Counter = field(default_factory=Counter)
    id_pauta: str | None = None
    id_card: str | None = None
    payload: Any = None  # item original (CollectedItem ou linha do acervo)

    @classmethod
    def from_item(cls, item: Any, key: str, glossary=None, **extra) -> "PautaItem":
        title = str(_field(item, "titulo") or "")
        description = str(_field(item, "descricao") or "")
        content = _field(item, "conteudo")
        return cls(key=key, titulo=title, nome_fonte=str(_field(item, "nome_fonte") or "fonte"),
                   descricao=description, url=str(_field(item, "url") or _field(item, "url_fonte") or ""),
                   tipo_fonte=str(_field(item, "tipo_fonte") or "secundaria"),
                   prioridade=int(_field(item, "prioridade") or 99),
                   data_publicacao=str(_field(item, "data_publicacao") or "") or None, conteudo=content,
                   agencia=_field(item, "agencia") or agency_of(f"{description}\n{(content or '')[:600]}\n"
                                                                 f"{(content or '')[-600:]}"),
                   entidades=extract_entities(title, description, glossary),
                   bag=term_bag(title, description, content), payload=item, **extra)


@dataclass
class Pauta:
    membros: list[PautaItem]
    id_pauta: str | None = None
    grupos_origem: list[list[str]] = field(default_factory=list)

    @property
    def lider(self) -> PautaItem:
        return min(self.membros, key=lambda m: (0 if m.tipo_fonte == "primaria" else 1, m.prioridade, m.key))

    @property
    def fontes(self) -> list[str]:
        return [m.nome_fonte for m in self.membros]

    @property
    def independentes(self) -> int:
        return len(self.grupos_origem) if self.grupos_origem else len(self.membros)

    @property
    def comparavel(self) -> bool:
        return self.independentes >= 2

    @property
    def assunto(self) -> str:
        return self.lider.titulo


def term_bag(title: str, description: str = "", content: str | None = None, body_words: int = 250) -> Counter:
    """Radicais de conteúdo: título duas vezes, descrição e o começo do texto completo."""
    body = " ".join((content or "").split()[:body_words])
    return Counter(stem(w) for w in words(f"{title} {title} {description} {body}")
                   if w not in STOPWORDS and len(w) > 2 and not w.isdigit())


def default_config() -> dict:
    return {"janela_horas": 72, "limiar_similaridade": 0.40, "limiar_sem_entidade": 0.6, "max_fontes": 5,
            "df_max_especifica": 0.15}


@dataclass
class Corpus:
    """Estatísticas do acervo: IDF dos radicais e frequência das entidades."""
    n: int
    term_df: Counter
    entity_df: Counter
    vectors: dict[str, dict[str, float]] = field(default_factory=dict)

    @classmethod
    def build(cls, items: Iterable[PautaItem]) -> "Corpus":
        items = list(items)
        corpus = cls(n=max(1, len(items)), term_df=Counter(t for i in items for t in i.bag),
                     entity_df=Counter(e for i in items for e in i.entidades))
        corpus.vectors = {i.key: corpus.vector(i) for i in items}
        return corpus

    def vector(self, item: PautaItem) -> dict[str, float]:
        # IDF suavizado (+1): com acervo pequeno (primeiras coletas), o IDF puro zera os termos que as duas
        # matérias do par dividem e esconde a pauta (par Prospera MEI: 0,19 puro x 0,44 suavizado com 3 notícias)
        return {t: (1 + math.log(c)) * (math.log((self.n + 1) / (self.term_df.get(t, 0) + 1)) + 1)
                for t, c in item.bag.items()}

    def cosine(self, a: PautaItem, b: PautaItem) -> float:
        va = self.vectors.get(a.key) or self.vector(a)
        vb = self.vectors.get(b.key) or self.vector(b)
        dot = sum(v * vb.get(t, 0.0) for t, v in va.items())
        norm = math.sqrt(sum(v * v for v in va.values())) * math.sqrt(sum(v * v for v in vb.values()))
        return dot / norm if norm else 0.0


def _date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def shared_specific_entities(a: PautaItem, b: PautaItem, corpus: Corpus, config: dict | None = None) -> list[str]:
    """Nomes, siglas e tickers em comum que aparecem em poucas notícias do acervo."""
    config = {**default_config(), **(config or {})}
    limit = max(2, math.ceil(config["df_max_especifica"] * corpus.n))
    return sorted(e for e in set(a.entidades) & set(b.entidades)
                  if a.entidades[e] != "termo" and corpus.entity_df.get(e, 0) <= limit)


def similarity(a: PautaItem, b: PautaItem, corpus: Corpus | None = None, config: dict | None = None) -> float:
    """Cosseno TF-IDF (0 a 1) se o par pode formar pauta; 0 quando não pode (mesma fonte, fora da janela,
    ou abaixo do limiar alto sem entidade específica em comum)."""
    config = {**default_config(), **(config or {})}
    corpus = corpus or Corpus.build([a, b])
    if a.nome_fonte == b.nome_fonte:
        return 0.0
    da, db = _date(a.data_publicacao), _date(b.data_publicacao)
    if da and db and abs((da - db).days) * 24 > config["janela_horas"]:
        return 0.0
    score = round(corpus.cosine(a, b), 3)
    if score < config["limiar_sem_entidade"] and not shared_specific_entities(a, b, corpus, config):
        return 0.0
    return score


def cluster(items: list[PautaItem], config: dict | None = None) -> list[Pauta]:
    """Agrupa as notícias em pautas (uma notícia isolada vira pauta de um membro só)."""
    config = {**default_config(), **(config or {})}
    corpus = Corpus.build(items)
    # ordem estável: primeiro as que já pertencem a uma pauta (preserva o agrupamento das coletas anteriores)
    ordered = sorted(items, key=lambda i: (i.id_pauta is None, 0 if i.tipo_fonte == "primaria" else 1, i.prioridade, i.key))
    pautas: list[Pauta] = []
    by_id: dict[str, Pauta] = {}
    for item in ordered:
        if item.id_pauta and item.id_pauta in by_id and item.nome_fonte not in by_id[item.id_pauta].fontes:
            by_id[item.id_pauta].membros.append(item)
            continue
        best, best_score = None, 0.0
        for pauta in pautas:
            if item.nome_fonte in pauta.fontes or len(pauta.membros) >= config["max_fontes"]:
                continue
            scores = [similarity(item, m, corpus, config) for m in pauta.membros]
            if min(scores) == 0.0:
                continue  # ligação média, mas sem aceitar quem não liga a algum membro (evita encadear assuntos)
            score = sum(scores) / len(scores)
            if score >= config["limiar_similaridade"] and score > best_score:
                best, best_score = pauta, score
        if best is not None:
            best.membros.append(item)
        else:
            pauta = Pauta(membros=[item], id_pauta=item.id_pauta)
            pautas.append(pauta)
            if item.id_pauta:
                by_id[item.id_pauta] = pauta
    for pauta in pautas:
        pauta.grupos_origem = origin_groups(pauta.membros)
        if pauta.id_pauta is None:
            ids = [m.id_pauta for m in pauta.membros if m.id_pauta]
            pauta.id_pauta = max(set(ids), key=ids.count) if ids else None
    return pautas


def origin_groups(members: list[PautaItem]) -> list[list[str]]:
    """Agrupa membros de mesma origem: mesma agência creditada, mesmo título ou mesma descrição."""
    from src.triangulacao.origem_comum import sobreposicao_literal

    groups: list[list[PautaItem]] = []
    for member in members:
        for group in groups:
            if any(_same_origin(member, other, sobreposicao_literal) for other in group):
                group.append(member)
                break
        else:
            groups.append([member])
    return [[m.key for m in group] for group in groups]


def _same_origin(a: PautaItem, b: PautaItem, overlap) -> bool:
    if a.agencia and a.agencia == b.agencia:
        return True
    if fold(a.titulo) == fold(b.titulo):
        return True
    if a.url and a.url == b.url:
        return True
    return bool(a.descricao and b.descricao and len(a.descricao.split()) >= 12 and overlap(a.descricao, b.descricao, 0.8))
