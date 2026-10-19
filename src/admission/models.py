from datetime import date
from typing import Optional
from pydantic import BaseModel


class OriginMetadata(BaseModel):
    instituicao: Optional[str] = None
    titulo: Optional[str] = None
    data: Optional[date] = None
    url: Optional[str] = None

    def to_source_label(self) -> str:
        if self.instituicao and self.titulo and self.data:
            return f"{self.instituicao}: {self.titulo}, {self.data.isoformat()}"
        if self.url:
            return self.url
        if self.titulo:
            return self.titulo
        return "texto enviado pelo usuario"

    @property
    def has_minimum_origin(self) -> bool:
        return bool(self.instituicao or self.titulo or self.data or self.url)


class PartialityResult(BaseModel):
    is_partial: bool
    reasons: list[str]


class AdmissionResult(BaseModel):
    is_partial: bool
    partial_reasons: list[str]
    is_financial: bool
    financial_rule_passed: bool
    distinct_glossary_terms: int
    word_count: int
    structured_type: str
    language: str
    origin: OriginMetadata
    status: str  # admitido | bloqueado | aviso
    text: str = ""  # texto limpo admitido (link e PDF: o conteúdo lido da página ou do arquivo)