from typing import Optional
from pydantic import BaseModel, Field, model_validator, field_validator


class AnalyticalSection(BaseModel):
    """Uma seção do texto analítico com ponto_ids cobertos."""
    title: str
    content: str
    ponto_ids: list[str] = Field(default_factory=list)
    afirmacao_ids: list[str] = Field(default_factory=list)
    linha_ids: list[str] = Field(default_factory=list)  # texto triangulado: linhas da matriz usadas


class AnalyticalText(BaseModel):
    """Texto analítico com 4 seções, ponto_ids por parágrafo, proporção 15/35/30/20."""
    title: str
    subtitle: str
    introduction: AnalyticalSection
    development: AnalyticalSection
    analysis: AnalyticalSection
    conclusion: AnalyticalSection
    covered_main_points: list[str] = []
    word_count_total: int
    word_count_by_section: dict[str, int] = {}
    fonte_bloco: str
    caixa_entenda_os_termos: Optional[str] = None  # só Iniciante, montada por regra, fora da contagem
    aviso_fonte_insuficiente: Optional[str] = None
    # Blocos fora da contagem de palavras, montados por regra:
    graficos_citados: list[str] = Field(default_factory=list)
    graficos: list[dict] = Field(default_factory=list)           # gráficos (arquivo, dados plotados, texto alternativo)
    triangulacao: Optional[dict] = None                           # matriz, fontes e independência (texto triangulado)
    rastreio: list[dict] = Field(default_factory=list)            # frase -> afirmação, tipo (fato/projeção) e trecho
    versao_prompt: str = "1.0"

    @model_validator(mode="after")
    def validate_sections(self):
        """Valida que cada seção tem ponto_ids e que os 3 pontos centrais são cobertos."""
        for section_name, section in [
            ("introduction", self.introduction),
            ("development", self.development),
            ("analysis", self.analysis),
            ("conclusion", self.conclusion),
        ]:
            if not section.ponto_ids:
                raise ValueError(f"Seção {section_name} deve ter pelo menos um ponto_id")
        return self

    @field_validator("fonte_bloco")
    @classmethod
    def _valida_fonte_bloco(cls, v: str) -> str:
        if not v or "Fonte" not in v:
            raise ValueError("fonte_bloco deve mencionar a fonte por regra")
        return v


class Slide(BaseModel):
    """Slide do carrossel com papel definido: gancho, corpo ou conclusão."""
    order: int
    role: str  # "gancho", "corpo" ou "conclusao"
    title: str
    body: str
    highlight_data: str | None = None
    ponto_id: str | None = None  # ponto central coberto pelo slide de corpo
    afirmacao_ids: list[str] = Field(default_factory=list)

    @field_validator("role")
    @classmethod
    def _valida_role(cls, v: str) -> str:
        if v not in {"gancho", "corpo", "conclusao"}:
            raise ValueError(f"role deve ser 'gancho', 'corpo' ou 'conclusao', obtido: {v}")
        return v


class Carousel(BaseModel):
    """Carrossel: 5 slides (gancho, 3 corpo, conclusão) + linha vermelha de nível + legenda.

    `linha_vermelha_nivel` é definida por regra a partir do nível (config/tokens_visuais.yaml), não pelo modelo.
    """
    slides: list[Slide]
    linha_vermelha_nivel: str | None = None  # "em cima", "duas laterais", "embaixo"
    legenda: Optional["Caption"] = None
    versao_prompt: str = "1.0"

    @model_validator(mode="after")
    def validate_count_and_roles(self):
        if len(self.slides) != 5:
            raise ValueError("Carrossel deve ter exatamente 5 slides")
        roles = [s.role for s in self.slides]
        if roles[0] != "gancho":
            raise ValueError("Primeiro slide deve ser 'gancho'")
        if roles[-1] != "conclusao":
            raise ValueError("Último slide deve ser 'conclusao'")
        if roles[1:4] != ["corpo", "corpo", "corpo"]:
            raise ValueError("Slides 2, 3 e 4 devem ser 'corpo'")
        return self


class Caption(BaseModel):
    """Legenda do Instagram: fonte por regra, verbo da lista, aviso opcional, até 2000 caracteres no total.

    `source_block`, `institutional_notice` e `texto_final` são montados por regra (src/generation/rules.py).
    """
    opening: str
    short_context: str
    source_block: str
    cta_verb: str
    cta_sentence: str
    institutional_notice: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    texto_final: str | None = None
    versao_prompt: str = "1.0"

    @field_validator("cta_verb")
    @classmethod
    def _valida_cta_verb(cls, v: str) -> str:
        verbos_validos = {"compartilhar", "curtir", "comentar", "salvar"}
        if v.lower() not in verbos_validos:
            raise ValueError(f"cta_verb deve ser um de {verbos_validos}, obtido: {v}")
        return v

    @field_validator("source_block")
    @classmethod
    def _valida_source_block(cls, v: str) -> str:
        if not v or "Fonte" not in v:
            raise ValueError("source_block deve mencionar a fonte por regra")
        return v

    @model_validator(mode="after")
    def validate_max_chars(self):
        total = len(self.texto_final) if self.texto_final else len(
            "\n\n".join([self.opening, self.short_context, self.source_block, self.cta_sentence,
                         self.institutional_notice or "", " ".join(self.hashtags)]))
        if total > 2000:
            raise ValueError(f"Legenda excede 2.000 caracteres ({total})")
        return self


class Scene(BaseModel):
    """Cena do roteiro: fala escrita e fala falada separadas, enquadramento controlado."""
    order: int
    role: str  # "gancho", "corpo", "conclusao"
    start_sec: float
    end_sec: float
    fala_escrita: str
    fala_falada: str  # números e datas por extenso
    texto_na_tela: str
    visual: str
    enquadramento: str  # "close", "plano_medio", "plano_aberto"
    direcao: str | None = None
    ponto_id: str | None = None
    afirmacao_ids: list[str] = Field(default_factory=list)
    versao_prompt: str = "1.0"

    @field_validator("enquadramento")
    @classmethod
    def _valida_enquadramento(cls, v: str) -> str:
        validos = {"close", "plano_medio", "plano_aberto"}
        if v not in validos:
            raise ValueError(f"enquadramento deve ser um de {validos}, obtido: {v}")
        return v

    @field_validator("role")
    @classmethod
    def _valida_role(cls, v: str) -> str:
        if v not in {"gancho", "corpo", "conclusao"}:
            raise ValueError(f"role deve ser 'gancho', 'corpo' ou 'conclusao', obtido: {v}")
        return v

    @model_validator(mode="after")
    def validate_time(self):
        if self.end_sec <= self.start_sec:
            raise ValueError("Intervalo de cena invalido")
        return self


class Script(BaseModel):
    """Roteiro de vídeo: 5 cenas, até 60 segundos."""
    scenes: list[Scene]
    total_duration_sec: float
    versao_prompt: str = "1.0"

    @model_validator(mode="after")
    def validate_count_and_duration(self):
        if len(self.scenes) != 5:
            raise ValueError("Roteiro deve ter exatamente 5 cenas")
        if self.total_duration_sec > 60:
            raise ValueError("Duracao total deve ser de ate 60 segundos")
        return self

Carousel.model_rebuild()
