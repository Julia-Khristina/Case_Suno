"""Grounding and factual fidelity checks (seção 4.7: Grounding Checker, número e data)."""
from __future__ import annotations

import re
from typing import Iterable

from src.evaluation.text_utils import content_stems, normalize, sentences, stem

# Número: dígitos com separadores internos; a pontuação final ("2026," "10,50%.") não faz parte do número.
NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)*(?:\s?%)?")
MONTHS = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
          "outubro", "novembro", "dezembro")
DAY_MONTH_RE = re.compile(r"\b(\d{1,2})(?:º)?(?:\s*(?:e|a|,)\s*(\d{1,2}))?\s+de\s+(" + "|".join(MONTHS) + r")\b",
                          re.IGNORECASE)
MONTH_RE = re.compile(r"\b(" + "|".join(MONTHS) + r")\b", re.IGNORECASE)

# Verbos e expressões de variação/comparação (seção 4.4: só mudanças declaradas pela fonte)
VARIATION_RE = re.compile(
    r"\b(sub(iu|iram|indo)|ca(iu|íram|indo)|aument(ou|aram|ando)|recu(ou|aram)|avanç(ou|aram)|cresc(eu|eram)|"
    r"diminu(iu|íram)|acelero(u)?|aceleraram|desacelero(u)?|desaceleraram|dispar(ou|aram)|despenc(ou|aram)|"
    r"melhor(ou|aram)|pior(ou|aram)|reduz(iu|iram)|eleva(ram|u)|alt(a|ou) de|queda de|"
    r"crescimento|aumento|redução|recuo|avanço|elevação|aceleração|desaceleração)\b",
    re.IGNORECASE,
)
COMPARISON_RE = re.compile(
    r"\b(em relação ao|em comparação (com|ao)|comparad[oa] (com|ao)|frente ao|ante o|que no|do que no)\s+"
    r"(m[eê]s|ano|trimestre|semestre|per[ií]odo|relat[oó]rio|documento|ata)\s+(passad[oa]|anterior)\b"
    r"|\b(m[eê]s|ano|trimestre) passado\b",
    re.IGNORECASE,
)

GENERAL_MARKER_RE = re.compile(r"\bem geral\s*,", re.IGNORECASE)


def _norm_number(token: str) -> str:
    return token.replace(" ", "").rstrip(".,")


def extract_numbers(text: str) -> list[str]:
    return [_norm_number(m.group(0)) for m in NUMBER_PATTERN.finditer(normalize(text))]


def normalize_number(value: str) -> str:
    return _norm_number(value)


def numbers_without_origin(generated_text: str, source_text: str) -> list[str]:
    """Números do material ausentes da fonte (comparação por token inteiro, não por substring)."""
    source_tokens = set(extract_numbers(source_text))
    source_bare = {t.rstrip("%") for t in source_tokens}
    missing = []
    for number in extract_numbers(generated_text):
        if number in source_tokens or number.rstrip("%") in source_bare:
            continue
        missing.append(number)
    return sorted(set(missing))


def dates_without_origin(generated_text: str, source_text: str) -> list[str]:
    """Datas por extenso ("12 e 13 de outubro", "em setembro") que não existem na fonte."""
    src = normalize(source_text).lower()
    src_months = set(m.lower() for m in MONTH_RE.findall(src))
    src_pairs = set()
    for d1, d2, month in DAY_MONTH_RE.findall(src):
        src_pairs.add((d1, month.lower()))
        if d2:
            src_pairs.add((d2, month.lower()))
    missing = []
    gen = normalize(generated_text)
    for d1, d2, month in DAY_MONTH_RE.findall(gen):
        for day in filter(None, (d1, d2)):
            if (day, month.lower()) not in src_pairs:
                missing.append(f"{day} de {month.lower()}")
    for month in MONTH_RE.findall(gen):
        if month.lower() not in src_months:
            missing.append(month.lower())
    return sorted(set(missing))


def all_generated_numbers_exist(generated_text: str, source_text: str) -> bool:
    return not numbers_without_origin(generated_text, source_text) and not dates_without_origin(generated_text, source_text)


# Palavras de discurso e atribuição: não são conteúdo factual a conferir na fonte.
DISCOURSE_STEMS = {stem(w) for w in """fonte documento texto segundo conforme resumo síntese questão
pergunta central ponto pontos motivo principal acompanhar acompanhe aponta apontou destaca destacou indica indicou
afirma afirmou observa observou avalia avaliou registra registrou explica explicou mostra mostrou simples
importante significa portanto assim então""".split()}


def _claim_stems(sentence: str, glossary_forms: Iterable[str] = (), discourse: set[str] | None = None) -> set[str]:
    """Radicais de conteúdo da frase, sem palavras de discurso e sem os termos do glossário
    (trocar jargão por explicação, ou o inverso, é permitido pela regra de fidelidade)."""
    stems = content_stems(sentence) - (DISCOURSE_STEMS if discourse is None else discourse)
    low = sentence.lower()
    for form in glossary_forms:
        if re.search(rf"(?<!\w){re.escape(form.lower())}(?!\w)", low):
            stems -= content_stems(form)
    return stems


def sentence_support(sentence: str, support_units: Iterable[str], glossary_forms: Iterable[str] = (),
                     discourse: set[str] | None = None) -> float:
    """Fração das palavras de conteúdo da frase presentes nas duas unidades de apoio que mais a cobrem
    (frases da fonte ou afirmações). Duas unidades toleram frases que sintetizam dois fatos da fonte."""
    stems = _claim_stems(sentence, glossary_forms, discourse)
    if len(stems) < 2:
        return 1.0  # frase de ligação, sem afirmação factual própria
    scored = sorted(((len(stems & content_stems(u)), content_stems(u)) for u in support_units),
                    key=lambda item: -item[0])[:2]
    covered: set[str] = set()
    for _n, unit_stems in scored:
        covered |= stems & unit_stems
    return len(covered) / len(stems)


EXPLANATION_MARKERS = re.compile(
    r"\b(ou seja|isto é|que é|que são|significa|chamad[oa]s?|é o nome|quer dizer)\b"
    # definição de termo no início da frase: "Renúncia de receita é o dinheiro…", "Risco fiscal é a chance…"
    r"|^\W*(?:[\wÀ-ÿ]+\s){0,4}[\wÀ-ÿ]+\s+(?:é|são)\s+(?:o|a|os|as|um|uma|tudo|quando)\s",
    re.IGNORECASE,
)

# Vocabulário da própria comparação entre fontes (texto triangulado): descreve a matriz, não a fonte.
TRIANGULATION_DISCOURSE_STEMS = {stem(w) for w in """fontes fonte duas três concordam concordância divergem divergência
diverge lado lados oposto oposta posição posições gráfico mapa trecho trechos estimativa estimativas reportagem nota
independente independentes separada comparamos compara apresenta aparecem nenhuma ambas confirmar conta""".split()}


def unsupported_sentences(text: str, source_text: str, assertions: Iterable[str] = (), min_overlap: float = 0.5,
                          exempt: Iterable[str] = (), glossary_forms: Iterable[str] = (),
                          matrix_units: Iterable[str] = (), source_names: Iterable[str] = ()) -> tuple[list[str], list[str]]:
    """Retorna (frases sem respaldo, frases de explicação isentas).

    Frases de explicação de termo são conferidas contra o glossário, não contra a fonte (seção 4.7);
    por isso ficam isentas aqui e voltam como aviso para a revisão humana.
    Texto triangulado: as linhas da matriz também são base de respaldo (`matrix_units`), e os nomes das fontes e o
    vocabulário da comparação não contam como conteúdo a conferir.
    """
    units = list(sentences(source_text)) + list(assertions) + list(matrix_units)
    source_names = list(source_names)
    glossary_forms = list(glossary_forms) + source_names
    discourse = DISCOURSE_STEMS | TRIANGULATION_DISCOURSE_STEMS if source_names else DISCOURSE_STEMS
    exempt_set = {e.strip().lower() for e in exempt}
    unsupported, explanations = [], []
    for sentence in sentences(text):
        if sentence.strip().lower() in exempt_set:
            continue
        support = sentence_support(sentence, units, glossary_forms, discourse)
        if EXPLANATION_MARKERS.search(sentence) or GENERAL_MARKER_RE.search(sentence):
            if support < min_overlap:
                explanations.append(sentence)
            continue
        if support < min_overlap:
            unsupported.append(sentence)
    return unsupported, explanations


def undeclared_variations(text: str, source_text: str, declared_assertions: Iterable[str] = (),
                          min_overlap: float = 0.5) -> list[str]:
    """Frases que afirmam variação/comparação sem uma frase da fonte que declare a mesma variação."""
    src_sents = sentences(source_text)
    src_variation_units = [s for s in src_sents if VARIATION_RE.search(s) or COMPARISON_RE.search(s)]
    src_variation_units += list(declared_assertions)
    flagged = []
    for sentence in sentences(text):
        if COMPARISON_RE.search(sentence):
            if not any(COMPARISON_RE.search(u) for u in src_variation_units) or \
                    sentence_support(sentence, src_variation_units) < min_overlap:
                flagged.append(sentence)
            continue
        if not VARIATION_RE.search(sentence) or EXPLANATION_MARKERS.search(sentence):
            continue
        if sentence_support(sentence, src_variation_units) >= min_overlap:
            continue
        # âncora numérica: a magnitude da variação vem de uma frase da fonte sobre o mesmo assunto
        numbers = set(extract_numbers(sentence))
        anchored = [u for u in src_sents if numbers & set(extract_numbers(u))]
        if numbers and anchored and sentence_support(sentence, anchored) >= min_overlap * 0.6:
            continue
        flagged.append(sentence)
    return flagged


def general_marker_violations(text: str, approved_explanations: Iterable[str]) -> list[str]:
    """Frases com o marcador 'Em geral,' cujo conteúdo não é uma explicação aprovada do glossário."""
    approved = [re.sub(r"\W+", " ", a.lower()).strip() for a in approved_explanations if a]
    violations = []
    for sentence in sentences(text):
        if not GENERAL_MARKER_RE.search(sentence):
            continue
        body = re.sub(r"\W+", " ", GENERAL_MARKER_RE.split(sentence, maxsplit=1)[-1].lower()).strip()
        if not any(body == a or body.startswith(a) or a.startswith(body) and len(body) > 0.8 * len(a) for a in approved):
            violations.append(sentence)
    return violations


def check_general_impact_markers(text: str, approved_explanations: list[str]) -> bool:
    return not general_marker_violations(text, approved_explanations)
