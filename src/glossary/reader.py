"""Glossary and alias readers (validated by Pydantic, seção 4.5 da especificação)."""
from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

GLOSSARY_PATH = "config/glossario.yaml"
APPROVED_STATUSES = {"aprovado", "autoria_manual"}


class GlossaryEntry(BaseModel):
    termo: str
    variacoes: list[str] = Field(default_factory=list)
    nivel: Literal["iniciante", "intermediario", "avancado"] = "iniciante"
    explicacao_iniciante: str | None = None
    explicacao_impacto: str | None = None
    pronuncia: str | None = None
    fonte_definicao: str | None = None
    url_fonte: str | None = None
    data_consulta: str | None = None
    trecho_original: str | None = None
    status: Literal["aprovado", "pendente", "sem_definicao", "autoria_manual"] = "pendente"

    @property
    def forms(self) -> list[str]:
        return [self.termo, *self.variacoes]

    @property
    def is_technical(self) -> bool:
        """Termo técnico para densidade e jargão: nível intermediário ou avançado."""
        return self.nivel in {"intermediario", "avancado"}

    @property
    def is_approved(self) -> bool:
        return self.status in APPROVED_STATUSES


class Glossary(BaseModel):
    versao: str = "0"
    termos: list[GlossaryEntry] = Field(default_factory=list)
    hash: str = ""

    @model_validator(mode="after")
    def _unique_variations(self):
        seen: dict[str, str] = {}
        for entry in self.termos:
            for form in entry.forms:
                key = form.lower().strip()
                if key in seen and seen[key] != entry.termo:
                    raise ValueError(f"A variação '{form}' aponta para dois termos: {seen[key]} e {entry.termo}")
                seen[key] = entry.termo
        return self

    # ---------------------------------------------------------------- consultas
    def all_forms(self) -> list[str]:
        return [form for entry in self.termos for form in entry.forms]

    def technical_forms(self) -> list[str]:
        return [form for entry in self.termos if entry.is_technical for form in entry.forms]

    def entry_for(self, form: str) -> GlossaryEntry | None:
        key = form.lower().strip()
        for entry in self.termos:
            if key in {f.lower() for f in entry.forms}:
                return entry
        return None

    def approved_impact_explanations(self) -> list[str]:
        return [e.explicacao_impacto for e in self.termos if e.is_approved and e.explicacao_impacto]

    def find_in_text(self, text: str, technical_only: bool = False) -> list[tuple[GlossaryEntry, str, int]]:
        """Ocorrências (entrada, forma encontrada, posição) sem sobreposição; formas longas primeiro."""
        low = text.lower()
        taken: list[tuple[int, int]] = []
        hits: list[tuple[GlossaryEntry, str, int]] = []
        forms = sorted(((f, e) for e in self.termos for f in e.forms if not technical_only or e.is_technical),
                       key=lambda item: -len(item[0]))
        for form, entry in forms:
            for match in re.finditer(rf"(?<!\w){re.escape(form.lower())}(?!\w)", low):
                start, end = match.span()
                if any(start < b and end > a for a, b in taken):
                    continue
                taken.append((start, end))
                hits.append((entry, form, start))
        return sorted(hits, key=lambda h: h[2])


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.exists() else "ausente"


@lru_cache(maxsize=8)
def _load_cached(path: str, mtime: float) -> Glossary:
    file_path = Path(path)
    data = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    raw_terms = data.get("termos") or []
    entries = [GlossaryEntry(termo=t) if isinstance(t, str) else GlossaryEntry(**t) for t in raw_terms]
    return Glossary(versao=str(data.get("versao", "0")), termos=entries, hash=_file_hash(file_path))


def load_glossary(path: str | Path = GLOSSARY_PATH) -> Glossary:
    file_path = Path(path)
    if not file_path.exists():
        return Glossary(hash="ausente")
    return _load_cached(str(file_path), file_path.stat().st_mtime)


def load_glossary_terms(path: str | Path = GLOSSARY_PATH) -> list[str]:
    """Compatibilidade: lista de todas as formas (termos e variações) do glossário."""
    return load_glossary(path).all_forms()


def load_aliases(path: str | Path = "config/apelidos.yaml") -> dict[str, list[str]]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    result: dict[str, list[str]] = {}
    for item in data.get("apelidos", []) or []:
        if isinstance(item, dict) and item.get("nome_canonico"):
            result[str(item["nome_canonico"])] = list(item.get("apelidos", []) or [])
    return result


def count_distinct_terms(text: str, terms: Iterable[str]) -> int:
    lowered = text.lower()
    matches = {term for term in terms if term and re.search(rf"(?<!\w){re.escape(term.lower())}(?!\w)", lowered)}
    return len(matches)
