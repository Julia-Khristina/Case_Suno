"""Texto analítico: LLM sobre entrada estruturada + partes montadas por regra (fonte, caixa de termos, contagens)."""
from __future__ import annotations

from pydantic import ValidationError

from src.extraction.models import ExtractionResult
from src.generation import rules
from src.generation.base import StructuredGenerator
from src.generation.models import AnalyticalText
from src.shared.llm_client import InvalidLLMOutput

SECTIONS = ("introduction", "development", "analysis", "conclusion")


class AnalyticalTextGenerator(StructuredGenerator):
    fmt = "texto_analitico"
    schema_name = "analytical_text"

    def generate(
        self,
        extraction: ExtractionResult,
        level: str,
        source_text: str,
        feedback: str | None = None,
        glossary=None,
        forbidden_terms: list[str] | None = None,
        origin: dict | None = None,
        thresholds: dict | None = None,
        **_compat,
    ) -> AnalyticalText:
        gen_input = self.build_input(extraction, level, source_text, feedback, glossary, forbidden_terms, origin, thresholds)
        response = self.call(gen_input)
        return finalize_analytical_text(response, level, gen_input.glossary, origin or {}, gen_input.prompt_version())


def finalize_analytical_text(response: dict, level: str, glossary, origin: dict, prompt_version: str) -> AnalyticalText:
    """Completa por regra o que não vem do modelo e valida o contrato Pydantic."""
    data = dict(response)
    for name in SECTIONS:
        section = data.get(name)
        if isinstance(section, str):
            section = {"title": name, "content": section}
        data[name] = {"title": "", "content": "", "ponto_ids": [], "afirmacao_ids": [], **(section or {})}
    total, by_section = rules.measured_word_counts({n: data[n]["content"] for n in SECTIONS})
    body = "\n".join(data[n]["content"] for n in SECTIONS)
    data.update(
        word_count_total=total,
        word_count_by_section=by_section,
        covered_main_points=sorted({pid for n in SECTIONS for pid in data[n]["ponto_ids"]}),
        fonte_bloco=rules.source_block(origin),
        caixa_entenda_os_termos=rules.understand_terms_box(f"{data.get('title', '')} {body}", glossary) if level == "iniciante" else None,
        versao_prompt=prompt_version,
    )
    try:
        return AnalyticalText.model_validate(data)
    except ValidationError as exc:
        raise InvalidLLMOutput(f"Texto analítico fora do contrato: {exc}") from exc
