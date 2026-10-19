"""Dossiê de triangulação: fontes sobre o mesmo assunto, independência entre elas e leitura de números.

Cada fonte passa pela mesma admissão e extração ancorada do pipeline de fonte única. Fontes de mesma origem
(mesma página, mesmo identificador, texto copiado, cobertura de um documento primário) contam como UMA fonte
independente: o texto nunca pode dizer "confirmado por N fontes" quando elas compartilham origem.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

from pydantic import BaseModel, Field

from src.triangulacao.origem_comum import detectar_origem_comum

SCALES = [
    (r"trilh(ão|ões|ao|oes)|tri\b", 1e12, "trilhões"),
    (r"bilh(ão|ões|ao|oes)|\bbi\b", 1e9, "bilhões"),
    (r"milh(ão|ões|ao|oes)|\bmi\b", 1e6, "milhões"),
    (r"\bmil\b", 1e3, "mil"),
]


class FonteDossie(BaseModel):
    id: str                      # f1, f2, ...
    nome: str
    tipo_fonte: str = "secundaria"
    titulo: str = ""
    data: str | None = None
    url: str | None = None
    conteudo: str
    hash: str = ""
    extraction: dict[str, Any] | None = None
    origem_comum_id: str | None = None

    def origin(self) -> dict:
        return {k: v for k, v in {"instituicao": self.nome, "titulo": self.titulo, "data": self.data,
                                  "url": self.url}.items() if v}


class Dossie(BaseModel):
    fontes: list[FonteDossie]
    grupos_origem: list[dict] = Field(default_factory=list)
    independentes: int = 0
    aviso: str | None = None

    @property
    def hash(self) -> str:
        return hashlib.sha256("|".join(sorted(f.hash for f in self.fontes)).encode()).hexdigest()

    def fonte(self, fonte_id: str) -> FonteDossie | None:
        return next((f for f in self.fontes if f.id == fonte_id), None)

    def texto_combinado(self) -> str:
        """Texto de todas as fontes (base do Grounding Checker e do arquivo do documento combinado)."""
        return "\n\n".join(f"[{f.id}] {f.nome}: {f.titulo}\n{f.conteudo}" for f in self.fontes)


def build_dossie(fontes: list[dict], limiar_sobreposicao: float = 0.6) -> Dossie:
    """Monta o dossiê e calcula a independência (um grupo de origem comum conta como uma fonte)."""
    items = []
    for index, raw in enumerate(fontes, start=1):
        content = (raw.get("conteudo") or raw.get("content") or "").strip()
        items.append(FonteDossie(
            id=raw.get("id") or f"f{index}", nome=raw.get("nome") or raw.get("instituicao") or f"Fonte {index}",
            tipo_fonte=raw.get("tipo_fonte") or "secundaria", titulo=raw.get("titulo") or "",
            data=str(raw.get("data")) if raw.get("data") else None, url=raw.get("url"), conteudo=content,
            hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        ))
    probe = [{"id": f.id, "nome": f.nome, "tipo_fonte": f.tipo_fonte, "url": f.url or "", "titulo": f.titulo,
              "trecho": " ".join(f.conteudo.split()[:300])} for f in items]
    groups = detectar_origem_comum(probe, limiar_sobreposicao=limiar_sobreposicao)
    for group in groups:
        for fonte in items:
            if fonte.id in group.fonte_ids:
                fonte.origem_comum_id = group.origem_comum_id
    independent = independent_count([f.id for f in items], items)
    aviso = None
    if independent < 2:
        aviso = (f"Só {independent} fonte(s) independente(s): as demais compartilham origem. "
                 "Sem triangulação: o material será gerado a partir de uma única fonte.")
    return Dossie(fontes=items, grupos_origem=[g.model_dump() for g in groups], independentes=independent, aviso=aviso)


def independent_count(fonte_ids: list[str], fontes: list[FonteDossie]) -> int:
    """Quantas origens distintas existem entre as fontes citadas (grupo de origem comum = 1)."""
    by_id = {f.id: f for f in fontes}
    origins = {by_id[i].origem_comum_id or i for i in fonte_ids if i in by_id}
    return len(origins)


# ------------------------------------------------------------------------------------------ números


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c)).lower()


def parse_quantity(value: str, unit: str | None = "") -> tuple[float | None, str]:
    """Lê '12,5' + 'R$ bilhões' como (12.5e9, 'R$'); '4,5' + '%' como (4.5, '%').

    A unidade canônica junta moeda/percentual sem a escala, para comparar 'R$ 12 bilhões' com 'R$ 12.000 milhões'.
    """
    text = f"{value or ''} {unit or ''}"
    low = text.lower()
    number_match = re.search(r"-?\d+(?:\.\d{3})*(?:,\d+)?|-?\d+(?:\.\d+)?", value or "") or \
        re.search(r"-?\d+(?:\.\d{3})*(?:,\d+)?|-?\d+(?:\.\d+)?", text)
    if not number_match:
        return None, ""
    raw = number_match.group(0)
    if "," in raw:
        number = float(raw.replace(".", "").replace(",", "."))
    elif re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", raw):
        number = float(raw.replace(".", ""))
    else:
        number = float(raw)
    for pattern, factor, _label in SCALES:
        if re.search(pattern, low):
            number *= factor
            break
    if "p.p" in low or "ponto percentual" in low or "pontos percentuais" in low:
        canonical = "p.p."
    elif "%" in low or "por cento" in low:
        canonical = "%"
    elif "us$" in low or "dólar" in low or "dolar" in low:
        canonical = "US$"
    elif "r$" in low or "reais" in low or "real" in low:
        canonical = "R$"
    else:
        canonical = re.sub(r"\s+", " ", _strip_accents(re.sub(r"[\d.,]+", "", unit or "")).strip())
        for pattern, _factor, _label in SCALES:
            canonical = re.sub(pattern, "", canonical).strip()
    per = re.search(r"\bpor\s+(barril|litro|tonelada|saca|acao|megawatt|kg)\b", _strip_accents(low))
    if per and canonical in {"R$", "US$"}:
        canonical = f"{canonical} por {per.group(1)}"  # preço unitário (US$ por barril) ≠ valor total (US$)
    return number, canonical


def quantity_label(value: str, unit: str | None) -> str:
    """Rótulo no texto original da fonte, com a moeda antes do número: ('12', 'R$ bilhões') -> 'R$ 12 bilhões'."""
    unit = (unit or "").strip()
    match = re.match(r"^(R\$|US\$|€)\s*(.*)$", unit)
    if match:
        return f"{match.group(1)} {value} {match.group(2)}".strip()
    if unit in {"%", "p.p."}:
        return f"{value}{unit}" if unit == "%" else f"{value} {unit}"
    return f"{value} {unit}".strip()


def normalize_period(period: str | None) -> str:
    return re.sub(r"\s+", " ", _strip_accents(period or "")).strip()


def format_quantity(number: float, unit: str) -> str:
    """Formata um valor canônico de volta em português (para títulos de gráfico)."""
    for _pattern, factor, label in SCALES:
        if abs(number) >= factor:
            scaled = number / factor
            text = f"{scaled:,.2f}".rstrip("0").rstrip(".").replace(",", "X").replace(".", ",").replace("X", ".")
            return f"{unit} {text} {label}".strip() if unit in {"R$", "US$"} else f"{text} {label} {unit}".strip()
    text = f"{number:,.2f}".rstrip("0").rstrip(".").replace(",", "X").replace(".", ",").replace("X", ".")
    if unit == "%":
        return f"{text}%"
    if unit in {"R$", "US$"}:
        return f"{unit} {text}"
    return f"{text} {unit}".strip()
