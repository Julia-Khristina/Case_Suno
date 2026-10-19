"""Experimento A5: diferenca entre niveis (Flesch, densidade de termos, tamanho de frase, sobreposicao de trigramas, distancia de edicao)."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from src.evaluation.differentiation import trigram_overlap_ratio
from src.evaluation.flesch_ptbr import flesch_reading_ease_pt
from src.evaluation.term_density import term_density_per_100_words, matching_terms

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from documents import DOCUMENTS

GLOSSARY_TERMS = ["selic", "copom", "ipca", "inflacao", "juros", "banco central", "meta", "pib"]


def _sentence_stats(text: str) -> dict:
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    if not sentences:
        return {"count": 0, "avg_words": 0.0, "max_words": 0}
    words_per = [len(s.split()) for s in sentences]
    return {
        "count": len(sentences),
        "avg_words": round(sum(words_per) / len(words_per), 2),
        "max_words": max(words_per),
    }


def _edit_distance(a: str, b: str) -> int:
    """Distancia de Levenshtein simplificada entre sequencias de palavras."""
    wa = a.split()
    wb = b.split()
    prev = list(range(len(wb) + 1))
    for i, ca in enumerate(wa, 1):
        curr = [i] + [0] * len(wb)
        for j, cb in enumerate(wb, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]


def run_a5(output_dir: Path) -> dict:
    results = {}
    for name, text in DOCUMENTS.items():
        words = len(re.findall(r"\w+", text, flags=re.UNICODE))
        terms_found = matching_terms(text, GLOSSARY_TERMS)
        results[name] = {
            "word_count": words,
            "flesch": round(flesch_reading_ease_pt(text), 3),
            "term_density_per_100": round(term_density_per_100_words(text, GLOSSARY_TERMS), 3),
            "terms_found": terms_found,
            "sentence_stats": _sentence_stats(text),
        }

    # Comparacao par a par (simulando niveis diferentes sobre mesma fonte)
    pairs = [("curto", "medio"), ("curto", "longo"), ("medio", "longo")]
    comparison = {}
    for left, right in pairs:
        overlap = trigram_overlap_ratio(DOCUMENTS[left], DOCUMENTS[right])
        edit_dist = _edit_distance(DOCUMENTS[left], DOCUMENTS[right])
        comparison[f"{left}_vs_{right}"] = {
            "trigram_overlap": round(overlap, 4),
            "edit_distance": edit_dist,
        }

    report = {
        "experimento": "A5",
        "descricao": "Diferenca entre niveis: Flesch, densidade de termos, tamanho de frase, sobreposicao de trigramas, distancia de edicao",
        "documentos": results,
        "comparacoes": comparison,
        "executado_em": datetime.now(UTC).isoformat(),
    }
    out_path = output_dir / "a5_result.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = run_a5(out_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))