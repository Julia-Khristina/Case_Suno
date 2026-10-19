"""Entrada estruturada do gerador (seção 4.6, "Entrada do gerador").

O gerador recebe os pontos centrais com suas afirmações e o trecho original, os dados numéricos, as entradas do
glossário dos termos presentes, as regras do nível e do formato, o guia de estilo e a lista de termos proibidos.
Não recebe o documento inteiro.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from src.extraction.models import ExtractionResult
from src.generation import rules

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
LEVEL_LABELS = {"iniciante": "INICIANTE", "intermediario": "INTERMEDIÁRIO", "avancado": "AVANÇADO"}
FORMAT_DIRS = {"texto_analitico": "text", "carrossel": "carousel", "roteiro_video": "script"}


@dataclass
class GenerationInput:
    level: str
    fmt: str
    extraction: ExtractionResult
    glossary: object
    thresholds: dict
    source_words: int
    origin: dict = field(default_factory=dict)
    forbidden_terms: list[str] = field(default_factory=list)
    feedback: str | None = None

    # ----------------------------------------------------------------------------------- blocos
    def main_points_block(self) -> str:
        by_id = {a.id: a for a in self.extraction.assertions}
        lines = []
        for point in self.extraction.main_points:
            lines.append(f"[{point.id}] {point.title}")
            for aid in point.assertion_ids:
                a = by_id.get(aid)
                if a is None:
                    continue
                flags = [a.type] + ([a.role] if a.role != "nenhum" else []) + (["variação declarada"] if a.variation_declared else [])
                lines.append(f"  - ({a.id}; {', '.join(flags)}) {a.text}")
                lines.append(f"    trecho de origem: \"{a.source_span.text}\"")
        # afirmações de causa/impacto/risco/acompanhar fora dos pontos alimentam Análise e Conclusão
        used = {aid for p in self.extraction.main_points for aid in p.assertion_ids}
        extra = [a for a in self.extraction.assertions if a.id not in used and a.role != "nenhum"]
        if extra:
            lines.append("[apoio] Afirmações de causa, impacto, risco ou fator a acompanhar:")
            for a in extra:
                lines.append(f"  - ({a.id}; {a.type}, {a.role}) {a.text}")
        return "\n".join(lines) or "(nenhum ponto central extraído)"

    def numeric_block(self) -> str:
        lines = [f"- ({n.id}) {n.indicator}: {n.value}{(' ' + n.unit) if n.unit else ''}"
                 f"{(' — ' + n.reference_period) if n.reference_period else ''} | trecho: \"{n.source_span.text}\""
                 for n in self.extraction.numeric_data]
        return "\n".join(lines) or "(nenhum dado numérico extraído: não cite números além dos que aparecem nas afirmações)"

    def _input_text(self) -> str:
        return " ".join([p.title for p in self.extraction.main_points] + [a.text for a in self.extraction.assertions])

    def glossary_block(self) -> str:
        lines, seen = [], set()
        for entry, _form, _pos in self.glossary.find_in_text(self._input_text()):
            if entry.termo in seen:
                continue
            seen.add(entry.termo)
            if entry.is_approved and entry.explicacao_iniciante:
                lines.append(f"- {entry.termo} (nível {entry.nivel}): explicação aprovada: {entry.explicacao_iniciante}")
            else:
                lines.append(f"- {entry.termo} (nível {entry.nivel}): sem explicação aprovada"
                             + (" — no Iniciante, explique com palavras simples logo após o termo" if self.level == "iniciante" else ""))
        return "\n".join(lines) or "(nenhum termo do glossário nas afirmações)"

    def impact_block(self) -> str:
        approved = self.glossary.approved_impact_explanations()
        if not approved:
            return "(nenhuma explicação de impacto aprovada: NÃO use o marcador 'Em geral,')"
        return "\n".join(f"- Em geral, {a}" for a in approved)

    def style_block(self) -> str:
        guide = rules.load_style_guide()
        level_line = (guide.get("niveis") or {}).get(self.level, "")
        return (f"Voz {guide.get('voz', 'sóbria e factual')}, {guide.get('idioma', 'português do Brasil')}, sem emojis, "
                f"sem recomendação de compra ou venda, sem sensacionalismo. Projeções continuam projeções. "
                f"Nível: {level_line}")

    def word_range(self) -> tuple[int, int]:
        return rules.word_range(self.fmt, self.source_words, self.thresholds)

    def point_ids(self) -> str:
        return ", ".join(p.id for p in self.extraction.main_points) or "(nenhum)"

    # ----------------------------------------------------------------------------------- prompt
    def template_paths(self) -> list[Path]:
        folder = PROMPTS_DIR / FORMAT_DIRS[self.fmt]
        return [PROMPTS_DIR / "system.txt", folder / "base.txt", folder / f"{self.level}.txt"]

    def prompt_version(self) -> str:
        digest = hashlib.sha256()
        for path in self.template_paths():
            digest.update(path.read_bytes())
        return digest.hexdigest()[:12]

    def render(self) -> tuple[str, str]:
        """Retorna (mensagem de sistema, mensagem do usuário)."""
        system_path, base_path, level_path = self.template_paths()
        lo, hi = self.word_range()
        values = {
            "nivel": LEVEL_LABELS[self.level],
            "regras_nivel": level_path.read_text(encoding="utf-8").strip(),
            "pontos_centrais": self.main_points_block(),
            "ids_pontos": self.point_ids(),
            "dados_numericos": self.numeric_block(),
            "glossario": self.glossary_block(),
            "explicacoes_impacto": self.impact_block(),
            "guia_estilo": self.style_block(),
            "termos_proibidos": ", ".join(self.forbidden_terms) or "(nenhum)",
            "palavras_min": lo,
            "palavras_max": hi,
            "feedback": self.feedback or "(primeira tentativa)",
            "verbos_acao": "compartilhar, curtir, comentar, salvar",
        }
        return system_path.read_text(encoding="utf-8").strip(), base_path.read_text(encoding="utf-8").format(**values)
