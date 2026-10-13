from typing import Optional
from pydantic import BaseModel, Field, model_validator


class AnalyticalSection(BaseModel):
    title: str
    content: str


class AnalyticalText(BaseModel):
    title: str
    subtitle: str
    introduction: str
    development: str
    analysis: str
    conclusion: str
    covered_main_points: list[str] = []
    word_count_total: int
    word_count_by_section: dict[str, int] = {}


class Slide(BaseModel):
    order: int
    role: str
    title: str
    body: str
    highlight_data: str | None = None


class Carousel(BaseModel):
    slides: list[Slide]

    @model_validator(mode="after")
    def validate_count(self):
        if len(self.slides) != 5:
            raise ValueError("Carrossel deve ter exatamente 5 slides")
        return self


class Caption(BaseModel):
    opening: str
    short_context: str
    source_block: str
    cta_verb: str
    cta_sentence: str
    institutional_notice: str | None = None
    hashtags: list[str] = Field(default_factory=list)


class Scene(BaseModel):
    order: int
    role: str
    start_sec: float
    end_sec: float
    spoken: str
    screen_text: str
    visual: str
    framing: str
    direction_note: str | None = None

    @model_validator(mode="after")
    def validate_time(self):
        if self.end_sec <= self.start_sec:
            raise ValueError("Intervalo de cena invalido")
        return self


class Script(BaseModel):
    scenes: list[Scene]
    total_duration_sec: float

    @model_validator(mode="after")
    def validate_count_and_duration(self):
        if len(self.scenes) != 5:
            raise ValueError("Roteiro deve ter exatamente 5 cenas")
        if self.total_duration_sec > 60:
            raise ValueError("Duracao total deve ser de ate 60 segundos")
        return self