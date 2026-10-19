"""Partes dos materiais montadas por regra, sem LLM (seções 4.3, 4.6 e 4.7 da especificação).

- bloco de fonte (texto, carrossel, legenda);
- caixa "Entenda os termos" do Iniciante (explicações aprovadas do glossário, fora da contagem de palavras);
- linha vermelha do nível no carrossel (config/tokens_visuais.yaml);
- fala falada do roteiro (números, porcentagens e datas por extenso; pronúncia do glossário);
- texto final da legenda (abertura, contexto, fonte, chamada, aviso configurado, hashtags);
- intervalo de palavras por formato, igual para os três níveis.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from src.evaluation.text_utils import word_count

# ------------------------------------------------------------------------------------------ fonte


def _date_br(value) -> str:
    """'2026-10-13' -> '13/10/2026'; outros formatos ficam como vieram."""
    text = str(value).strip()
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:[T ].*)?", text)
    return f"{match.group(3)}/{match.group(2)}/{match.group(1)}" if match else text


def source_block(origin: dict | None) -> str:
    origin = origin or {}
    if origin.get("fontes"):  # relatório triangulado: uma linha por fonte, na ordem do dossiê
        lines = []
        for fonte in origin["fontes"]:
            parts = [str(fonte.get("nome") or "").strip(), str(fonte.get("titulo") or "").strip(),
                     _date_br(fonte["data"]) if fonte.get("data") else ""]
            lines.append(", ".join(p for p in parts if p) + "." + (f" {fonte['url']}" if fonte.get("url") else ""))
        return "Fontes: " + " | ".join(lines)
    parts = [str(origin.get("instituicao") or "").strip(), str(origin.get("titulo") or "").strip(),
             _date_br(origin["data"]) if origin.get("data") else ""]
    parts = [p for p in parts if p]
    url = (origin.get("url") or "").strip()
    if not parts and not url:
        return "Fonte: texto enviado pelo usuário."
    label = ", ".join(parts) if parts else url
    return f"Fonte: {label}." + (f" {url}" if url and parts else "")


# --------------------------------------------------------------------------- caixa Entenda os termos


def understand_terms_box(text: str, glossary) -> str | None:
    """Lista os termos do glossário presentes no texto que têm explicação APROVADA. None se não houver."""
    lines, seen = [], set()
    for entry, _form, _pos in glossary.find_in_text(text):
        if entry.termo in seen or not entry.is_approved or not entry.explicacao_iniciante:
            continue
        seen.add(entry.termo)
        lines.append(f"{entry.termo}: {entry.explicacao_iniciante}")
    return "\n".join(lines) if lines else None


# ------------------------------------------------------------------------------------ linha do nível


def level_line(level: str, path: str = "config/tokens_visuais.yaml") -> str:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return (data.get("linha_por_nivel") or {})[level]


# ---------------------------------------------------------------------------------- números por extenso

_UNITS = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze",
          "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
_TENS = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
_HUNDREDS = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos",
             "oitocentos", "novecentos"]


def _below_thousand(n: int) -> str:
    if n == 100:
        return "cem"
    parts = []
    h, rest = divmod(n, 100)
    if h:
        parts.append(_HUNDREDS[h])
    if rest:
        if rest < 20:
            parts.append(_UNITS[rest])
        else:
            t, u = divmod(rest, 10)
            parts.append(_TENS[t] + (f" e {_UNITS[u]}" if u else ""))
    return " e ".join(parts) if parts else "zero"


def integer_to_words(n: int) -> str:
    if n < 0:
        return "menos " + integer_to_words(-n)
    if n < 1000:
        return _below_thousand(n)
    groups: list[tuple[str, int]] = []  # (por extenso, valor do grupo na sua escala)
    for scale_sing, scale_plur, size in (("bilhão", "bilhões", 10 ** 9), ("milhão", "milhões", 10 ** 6), ("mil", "mil", 1000)):
        q, n = divmod(n, size)
        if q:
            if size == 1000:
                groups.append(("mil" if q == 1 else f"{integer_to_words(q)} mil", q))
            else:
                groups.append((f"{integer_to_words(q)} {scale_sing if q == 1 else scale_plur}", q))
    if n:
        groups.append((_below_thousand(n), n))
    if len(groups) == 1:
        return groups[0][0]
    last_words, last_value = groups[-1]
    joiner = " e " if (last_value < 100 or last_value % 100 == 0) else " "
    return " ".join(g for g, _ in groups[:-1]) + joiner + last_words


def number_to_words(token: str) -> str:
    """'10,50' -> 'dez vírgula cinquenta'; '1.500' -> 'mil e quinhentos'; '2026' -> 'dois mil e vinte e seis'."""
    token = token.strip()
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", token):
        token = token.replace(".", "")
    if "," in token:
        whole, frac = token.split(",", 1)
        whole_words = integer_to_words(int(whole.replace(".", "") or 0))
        frac_words = " ".join(_UNITS[int(d)] for d in frac) if frac.startswith("0") else integer_to_words(int(frac))
        return f"{whole_words} vírgula {frac_words}"
    return integer_to_words(int(token))


_ABBREVIATIONS = [
    (r"\bp\.\s?p\.", "pontos percentuais"),
    (r"\ba\.\s?a\.", "ao ano"),
    (r"\ba\.\s?m\.", "ao mês"),
    (r"\bbi\b", "bilhões"),
    (r"\bmi\b", "milhões"),
]


def spoken_text(written: str, glossary=None) -> str:
    """Fala falada derivada por regra da fala escrita (seção 4.6)."""
    text = written
    for pattern, repl in _ABBREVIATIONS:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    def money(m: re.Match) -> str:
        value = number_to_words(m.group(1))
        scale = m.group(2) or ""
        scale_words = {"mil": "mil", "milhão": "milhão", "milhões": "milhões", "bilhão": "bilhão", "bilhões": "bilhões"}
        suffix = f" {scale_words[scale.lower()]} de reais" if scale else " reais"
        return value + suffix

    text = re.sub(r"R\$\s?(\d+(?:[.,]\d+)*)(?:\s+(mil|milhão|milhões|bilhão|bilhões))?", money, text)
    text = re.sub(r"(\d+(?:[.,]\d+)*)\s?%", lambda m: number_to_words(m.group(1)) + " por cento", text)
    text = re.sub(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b",
                  lambda m: f"{integer_to_words(int(m.group(1)))} do {integer_to_words(int(m.group(2)))} de "
                            f"{integer_to_words(int(m.group(3)))}", text)
    text = re.sub(r"\d+(?:[.,]\d+)*", lambda m: number_to_words(m.group(0).rstrip(".,")) + m.group(0)[len(m.group(0).rstrip('.,')):], text)
    if glossary is not None:
        for entry in glossary.termos:
            if entry.pronuncia:
                for form in entry.forms:
                    text = re.sub(rf"(?<!\w){re.escape(form)}(?!\w)", entry.pronuncia, text, flags=re.IGNORECASE)
    return text


# -------------------------------------------------------------------------------------------- legenda


def load_style_guide(path: str = "config/guia_estilo.yaml") -> dict:
    file_path = Path(path)
    return yaml.safe_load(file_path.read_text(encoding="utf-8")) or {} if file_path.exists() else {}


def institutional_notice() -> str | None:
    """Aviso institucional configurável e provisório (a Suno não forneceu texto obrigatório)."""
    notice = load_style_guide().get("aviso_institucional")
    return str(notice).strip() if notice else None


def caption_final_text(opening: str, short_context: str, source: str, cta: str, notice: str | None,
                       hashtags: list[str]) -> str:
    parts = [opening.strip(), short_context.strip(), cta.strip(), source.strip()]
    if notice:
        parts.append(notice)
    if hashtags:
        parts.append(" ".join(hashtags))
    return "\n\n".join(p for p in parts if p)


def hashtags_from_entities(entities: list[dict]) -> list[str]:
    if not load_style_guide().get("legenda_hashtags"):
        return []
    tags = []
    for entity in entities:
        name = re.sub(r"[^\w]", "", str(entity.get("canonical_name") or entity.get("name") or ""))
        if name and f"#{name}" not in tags:
            tags.append(f"#{name}")
    return tags[:5]


# ------------------------------------------------------------------------------------ intervalo de palavras


def word_range(fmt: str, source_words: int, thresholds) -> tuple[int, int]:
    """Intervalo de palavras do formato, igual para os três níveis (seção 4.6).

    Fonte com menos palavras que o mínimo do formato: o intervalo passa a depender da fonte
    (fator mínimo e máximo de config/limiares.yaml), para o gerador não precisar encher texto.
    """
    from src.evaluation.thresholds import as_thresholds

    t = as_thresholds(thresholds)
    if fmt == "texto_analitico":
        lo, hi = t.req("tamanho_texto_min_palavras"), t.req("tamanho_texto_max_palavras")
    elif fmt == "texto_triangulado":
        return t.req("texto_triangulado_min_palavras"), t.req("texto_triangulado_max_palavras")
    elif fmt == "carrossel":
        lo, hi = t.req("carrossel_min_palavras"), t.req("carrossel_max_palavras")
    elif fmt == "roteiro_video":
        dur = t.req("duracao_video_max_segundos")
        lo = int(t.req("palavras_por_segundo_roteiro_min") * dur * 0.5)
        hi = int(t.req("palavras_por_segundo_roteiro_max") * dur)
    else:
        raise ValueError(f"Formato desconhecido: {fmt}")
    if source_words and source_words < lo:
        floor = t.req("fonte_curta_piso_palavras")
        lo_eff = max(min(floor, lo), int(source_words * t.req("fonte_curta_fator_min")))
        hi_eff = min(hi, max(lo_eff + 20, int(source_words * t.req("fonte_curta_fator_max"))))
        return min(lo_eff, hi_eff), hi_eff
    return lo, hi


def measured_word_counts(sections: dict[str, str]) -> tuple[int, dict[str, int]]:
    by_section = {name: word_count(content) for name, content in sections.items()}
    return sum(by_section.values()), by_section
