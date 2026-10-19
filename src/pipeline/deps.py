"""Dependências do pipeline (fora do estado serializável): cliente LLM único, glossário, limiares,
termos proibidos, persistência e versões de configuração (seção 4.7: cada execução registra o contexto)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.evaluation.format_checks import load_forbidden_terms, load_recommendation_patterns
from src.evaluation.thresholds import Thresholds, load_thresholds
from src.glossary.reader import Glossary, load_glossary
from src.pipeline.persistence import InMemoryPersistence
from src.shared.llm_client import LLMClient

ROOT = Path(__file__).resolve().parents[2]


def _hash_files(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        if path.exists():
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


@dataclass
class PipelineDeps:
    llm_client: Any = None
    glossary: Glossary | None = None
    thresholds: Thresholds | None = None
    forbidden_terms: list[str] | None = None
    recommendation_patterns: list[str] | None = None
    persistence: Any = None
    rubric_path: str = "src/evaluation/rubric.yaml"
    term_resolver: Any = None
    require_distinct_judge: bool | None = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.llm_client = self.llm_client or LLMClient()
        self.glossary = self.glossary or load_glossary()
        self.thresholds = self.thresholds or load_thresholds()
        self.forbidden_terms = load_forbidden_terms() if self.forbidden_terms is None else self.forbidden_terms
        if self.recommendation_patterns is None:
            self.recommendation_patterns = load_recommendation_patterns()
        self.persistence = self.persistence or InMemoryPersistence()
        if self.require_distinct_judge is None:
            self.require_distinct_judge = getattr(self.llm_client, "mode", "simulated") in {"live", "record"}

    def config_versions(self) -> dict[str, str]:
        prompts = list((ROOT / "src" / "generation" / "prompts").rglob("*.txt")) + \
            list((ROOT / "src" / "extraction" / "prompts").rglob("*.txt"))
        client = self.llm_client
        judge_model = getattr(client, "judge_model", None) or "não configurado"
        return {
            "glossario": f"{self.glossary.versao}#{self.glossary.hash}",
            "prompts": _hash_files(prompts),
            "limiares": _hash_files([ROOT / "config" / "limiares.yaml"]),
            "rubrica": _hash_files([ROOT / self.rubric_path]),
            "estilo": _hash_files([ROOT / "config" / "guia_estilo.yaml", ROOT / "config" / "termos_proibidos.yaml"]),
            "modelo_geracao": str(getattr(client, "default_model", "")),
            "modelo_juiz": str(judge_model),
            "modo_llm": str(getattr(client, "mode", "")),
        }
