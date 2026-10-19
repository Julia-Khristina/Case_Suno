"""Modelos de dados para triangulacao de fontes."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, model_validator


class TipoFonte(str, Enum):
    PRIMARIA = "primaria"
    SECUNDARIA = "secundaria"
    MANCHETE = "manchete"


class StatusLinhaMatriz(str, Enum):
    CONVERGENCIA = "convergencia"
    DIVERGENCIA_NUMERICA = "divergencia_numerica"
    DIVERGENCIA_QUALITATIVA = "divergencia_qualitativa"
    SEM_CONTRA_PONTO = "sem_contraponto"
    NAO_COMPARAVEL = "nao_comparavel"


class PosicaoQualitativa(str, Enum):
    APOIA = "apoiar"
    CONTESTA = "contestar"
    NEUTRA = "neutra"
    NAO_MENCIONA = "nao_menciona"


class CelulaMatriz(BaseModel):
    """Celula da matriz: o que uma fonte diz sobre um ponto de comparacao."""
    fonte_id: str
    fonte_nome: str
    tipo_fonte: TipoFonte = TipoFonte.SECUNDARIA
    data: str | None = None
    valor_texto: str | None = None  # o que a fonte diz, texto livre
    trecho: str | None = None  # trecho exato de origem (max 25 palavras na citação)
    trecho_curto: str | None = None  # citação curta (max 25 palavras)
    origem_comum_id: str | None = None  # grupo de origem comum
    confianca: float | None = None  # 0.0 a 1.0
    posicao_qualitativa: PosicaoQualitativa | None = None
    dado_numerico: dict[str, Any] | None = None  # indicador, valor, unidade, período normalizados


class LinhaMatriz(BaseModel):
    """Linha da matriz de triangulacao."""
    linha_id: str
    topico: str  # ponto de comparacao
    status: StatusLinhaMatriz
    celulas: list[CelulaMatriz] = Field(default_factory=list)
    diferenca_absoluta: float | None = None  # para divergência numérica
    diferenca_relativa: float | None = None  # percentual
    fontes_convergentes: list[str] = Field(default_factory=list)  # ids das fontes que convergem
    fontes_divergentes: list[str] = Field(default_factory=list)  # ids das fontes que divergem
    evidencia_necessaria: list[str] = Field(default_factory=list)  # ids de trecho necessários
    revisada_por_humano: bool = False
    confirmada_por_humano: bool | None = None  # True=confirmada, False=rejeitada, None=pendente
    justificativa_status: str | None = None  # por que esse status


class DadoNumericoNormalizado(BaseModel):
    """Dado numerico normalizado para comparacao."""
    indicador: str
    valor: float
    unidade: str
    periodo: str
    fonte_id: str
    fonte_nome: str
    trecho: str
    escala: str = "unidade"
    normalizado: bool = True


class ComparacaoNumerica(BaseModel):
    """Resultado de comparacao numerica entre fontes."""
    indicador: str
    unidade: str
    periodo: str
    valores: list[DadoNumericoNormalizado] = Field(default_factory=list)
    status: StatusLinhaMatriz = StatusLinhaMatriz.NAO_COMPARAVEL
    diferenca_absoluta: float | None = None
    diferenca_relativa: float | None = None
    tolerancia_usada: dict[str, float] | None = None
    motivo_nao_comparavel: str | None = None


class PosicaoClassificada(BaseModel):
    """Classificacao qualitativa de uma afirmacao."""
    afirmacao_id: str
    fonte_id: str
    posicao: PosicaoQualitativa
    confianca: float  # 0.0 a 1.0
    trecho_evidencia: str
    justificativa: str | None = None


class OrigemComum(BaseModel):
    """Grupo de fontes de mesma origem."""
    origem_comum_id: str
    fonte_ids: list[str] = Field(default_factory=list)
    motivo: str  # mesmo link, mesmo identificador, sobreposicao literal, documento primario
    documento_primario: str | None = None  # se uma das fontes eh o primario


class Triangulacao(BaseModel):
    """Conjunto completo de triangulacao."""
    triangulacao_id: str
    assunto: str
    fontes: list[dict[str, Any]] = Field(default_factory=list)  # metadados de cada fonte
    origem_comum_grupos: list[OrigemComum] = Field(default_factory=list)
    matriz: list[LinhaMatriz] = Field(default_factory=list)
    comparacoes_numericas: list[ComparacaoNumerica] = Field(default_factory=list)
    classificacoes_qualitativas: list[PosicaoClassificada] = Field(default_factory=list)
    graficos: list[dict[str, Any]] = Field(default_factory=list)  # arquivo, hash, dados
    pontos_centrais: list[str] = Field(default_factory=list)  # ids dos 3 pontos centrais
    revisoes_humanas: list[dict[str, Any]] = Field(default_factory=list)
    hash_contexto_execucao: str | None = None
    criado_em: str = Field(default_factory=lambda: datetime.now().isoformat())
    total_fontes_independentes: int = 0
    permite_triangulacao: bool = False
    aviso_sem_triangulacao: str | None = None