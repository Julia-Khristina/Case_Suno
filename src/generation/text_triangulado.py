"""Texto analítico TRIANGULADO: o mesmo contrato do texto analítico (4 seções, Pydantic, partes por regra),
gerado a partir da matriz de triangulação em vez de uma fonte única (decisão de 17/10/2026)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.extraction.models import ExtractionResult
from src.generation import rules
from src.generation.base import StructuredGenerator
from src.generation.inputs import LEVEL_LABELS, PROMPTS_DIR, GenerationInput
from src.generation.models import AnalyticalText
from src.generation.text_analytical import finalize_analytical_text
from src.triangulacao.graficos_matriz import STATUS_LABEL
from src.triangulacao.models import LinhaMatriz

POSITION_TEXT = {"apoiar": "apoia", "contestar": "contesta", "neutra": "neutra", "nao_menciona": "não menciona"}


def matrix_block(rows: list[LinhaMatriz], include_difference: bool = False) -> str:
    """Matriz para o modelo e para o juiz. Por decisão de projeto, a diferença calculada entre fontes NÃO vai ao
    gerador (aparece só na matriz e nos gráficos); o juiz pode recebê-la."""
    lines = []
    for row in rows:
        lines.append(f"[{row.linha_id}] {row.topico} — status: {STATUS_LABEL[row.status]}"
                     + (f" ({row.justificativa_status})" if include_difference and row.justificativa_status else ""))
        for cell in row.celulas:
            position = POSITION_TEXT.get(cell.posicao_qualitativa.value, "") if cell.posicao_qualitativa else ""
            origin = f", origem comum {cell.origem_comum_id}" if cell.origem_comum_id else ""
            lines.append(f"  - {cell.fonte_nome} ({cell.tipo_fonte}{origin}){': ' + position if position and not cell.dado_numerico else ''}"
                         f" — {cell.valor_texto} | trecho: \"{cell.trecho_curto}\"")
    return "\n".join(lines)


@dataclass
class TriangulatedInput(GenerationInput):
    rows: list[LinhaMatriz] = field(default_factory=list)
    top_ids: list[str] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    charts: list[dict] = field(default_factory=list)

    def template_paths(self) -> list[Path]:
        return [PROMPTS_DIR / "system.txt", PROMPTS_DIR / "text_triangulado" / "base.txt",
                PROMPTS_DIR / "text" / f"{self.level}.txt"]

    def word_range(self) -> tuple[int, int]:
        return rules.word_range("texto_triangulado", self.source_words, self.thresholds)

    def render(self) -> tuple[str, str]:
        system_path, base_path, level_path = self.template_paths()
        lo, hi = self.word_range()
        sources = "\n".join(
            f"- {s['nome']} ({s.get('tipo_fonte', 'secundaria')}, {s.get('data') or 'sem data'}"
            f"{', origem comum ' + s['origem_comum_id'] if s.get('origem_comum_id') else ''}): {s.get('titulo', '')}"
            for s in self.sources)
        charts = "\n".join(f"- {c['id']}: {c['titulo']} (linhas {', '.join(c.get('linha_ids') or []) or '—'})"
                           for c in self.charts) or "(nenhum gráfico)"
        values = {
            "nivel": LEVEL_LABELS[self.level], "n_fontes": len(self.sources), "fontes": sources,
            "matriz": matrix_block(self.rows), "ids_pontos": ", ".join(self.top_ids), "graficos": charts,
            "glossario": self.glossary_block(), "explicacoes_impacto": self.impact_block(),
            "regras_nivel": level_path.read_text(encoding="utf-8").strip(), "guia_estilo": self.style_block(),
            "termos_proibidos": ", ".join(self.forbidden_terms) or "(nenhum)", "palavras_min": lo, "palavras_max": hi,
            "feedback": self.feedback or "(primeira tentativa)",
        }
        return system_path.read_text(encoding="utf-8").strip(), base_path.read_text(encoding="utf-8").format(**values)


class TriangulatedTextGenerator(StructuredGenerator):
    fmt = "texto_analitico"
    schema_name = "analytical_text_triangulated"

    def generate(self, extraction: ExtractionResult, level: str, source_text: str, feedback: str | None = None,
                 glossary=None, forbidden_terms: list[str] | None = None, origin: dict | None = None,
                 thresholds: dict | None = None, triangulacao: dict | None = None, **_compat) -> AnalyticalText:
        base = self.build_input(extraction, level, source_text, feedback, glossary, forbidden_terms, origin, thresholds)
        triangulacao = triangulacao or {}
        gen_input = TriangulatedInput(
            **{k: getattr(base, k) for k in ("level", "fmt", "extraction", "glossary", "thresholds", "source_words",
                                             "origin", "forbidden_terms", "feedback")},
            rows=[LinhaMatriz.model_validate(r) for r in triangulacao.get("matriz", [])],
            top_ids=triangulacao.get("pontos_centrais", []), sources=triangulacao.get("fontes", []),
            charts=charts_for_level(triangulacao.get("graficos", []), level, thresholds),
        )
        response = self.call(gen_input)
        text = finalize_analytical_text(response, level, gen_input.glossary, origin or {}, gen_input.prompt_version())
        return text


def charts_for_level(charts: list[dict], level: str, thresholds=None) -> list[dict]:
    """Quantidade de gráficos por nível (config/triangulacao.yaml: graficos_por_nivel)."""
    import yaml

    path = Path("config/triangulacao.yaml")
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {} if path.exists() else {}
    limit = int((config.get("graficos_por_nivel") or {}).get(level, 2))
    return charts[:limit]
