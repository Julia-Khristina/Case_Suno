"""Pydantic models for extraction."""
from typing import Literal
from pydantic import BaseModel, Field


class SourceSpan(BaseModel):
    text: str
    start: int | None = None
    end: int | None = None


class MainPoint(BaseModel):
    id: str
    order: int
    title: str
    assertion_ids: list[str] = Field(default_factory=list)


class Assertion(BaseModel):
    id: str
    text: str
    type: Literal["fato", "projecao", "evento_futuro"]
    role: Literal["nenhum", "causa", "impacto", "risco", "acompanhar"] = "nenhum"
    source_span: SourceSpan
    variation_declared: bool = False


class NumericData(BaseModel):
    id: str
    indicator: str
    value: str
    unit: str | None = None
    reference_period: str | None = None
    source_span: SourceSpan


class Entity(BaseModel):
    id: str
    name: str
    canonical_name: str
    type: str = "instituicao"


class Event(BaseModel):
    id: str
    name: str
    canonical_name: str
    reference_date: str | None = None
    type: str = "evento"


class SourceComplexity(BaseModel):
    flesch: float | None = None
    term_density: float | None = None
    word_count: int


class PendingTerm(BaseModel):
    term: str
    proposed_definition: str | None = None
    source: str | None = None
    source_url: str | None = None
    status: str = "pendente"


class ExtractionResult(BaseModel):
    main_points: list[MainPoint] = Field(default_factory=list, max_length=3)
    assertions: list[Assertion] = Field(default_factory=list)
    numeric_data: list[NumericData] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    detected_terms: list[str] = Field(default_factory=list)
    pending_terms: list[PendingTerm] = Field(default_factory=list)
    source_complexity: SourceComplexity