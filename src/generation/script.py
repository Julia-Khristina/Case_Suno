"""Roteiro de vídeo: LLM sobre entrada estruturada + fala falada derivada por regra."""
from __future__ import annotations

from pydantic import ValidationError

from src.extraction.models import ExtractionResult
from src.generation import rules
from src.generation.base import StructuredGenerator
from src.generation.models import Script
from src.shared.llm_client import InvalidLLMOutput


class ScriptGenerator(StructuredGenerator):
    fmt = "roteiro_video"
    schema_name = "script"

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
    ) -> Script:
        gen_input = self.build_input(extraction, level, source_text, feedback, glossary, forbidden_terms, origin, thresholds)
        response = self.call(gen_input)
        return finalize_script(response, gen_input.glossary, gen_input.prompt_version())


def finalize_script(response: dict, glossary, prompt_version: str) -> Script:
    scenes = []
    for scene in response.get("scenes") or []:
        scene = dict(scene)
        scene["fala_falada"] = rules.spoken_text(scene.get("fala_escrita", ""), glossary)
        scene.setdefault("versao_prompt", prompt_version)
        scenes.append(scene)
    total = response.get("total_duration_sec")
    if total is None and scenes:
        total = scenes[-1].get("end_sec", 0)
    try:
        return Script(scenes=scenes, total_duration_sec=float(total or 0), versao_prompt=prompt_version)
    except (ValidationError, TypeError, ValueError) as exc:
        raise InvalidLLMOutput(f"Roteiro fora do contrato: {exc}") from exc
