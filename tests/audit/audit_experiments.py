# -*- coding: utf-8 -*-
"""Auditoria: experimentos A5 (diferenciação), A6 (repetição/padding), A7 (curta x longa) e B6 (adversariais).

A5/A6 medem as saídas gravadas ANTES da correção (templates do HEAD e da árvore de trabalho de 17/10/2026),
em tests/audit/results/outputs_{head,wt}.json. B6 roda o avaliador corrigido.
Entrada: tests/audit/results/outputs_{head,wt}.json (gerados por audit_collect_outputs.py).
Saída:   tests/audit/results/experimentos.json + tabelas Markdown no stdout.
Sem LLM e sem rede. Uso: python -m tests.audit.audit_experiments
"""
from __future__ import annotations

import json
import re
import sys
from itertools import combinations
from pathlib import Path

from src.evaluation.flesch_ptbr import flesch_reading_ease_pt
from src.evaluation.redundancy import sentence_repetition_ratio, trigram_repetition_ratio
from src.evaluation.differentiation import trigram_overlap_ratio
from src.evaluation.grounding import extract_numbers
from src.evaluation.term_density import term_density_per_100_words
from src.evaluation.thresholds import load_thresholds
from src.glossary.reader import load_glossary_terms
from tests.audit.audit_b6_cases import APPROVED_IMPACT, MAIN_POINTS, build_cases

RES = Path("tests/audit/results")
WORD = re.compile(r"\w+", re.UNICODE)
LEVELS = ["iniciante", "intermediario", "avancado"]
STOP = set("""a o os as de da do das dos e em no na nos nas um uma uns umas que para por com sem ao aos à às
se sua seu suas seus é são foi ser mais menos como mas ou também já não isso esse essa este esta pelo pela pelos
pelas entre sobre até após the""".split())

# Glossário de auditoria: o config/glossario.yaml está VAZIO (termos: []), então usamos como proxy os nomes do
# cache do glossário do BCB (data/cache/bcb_glossario.json) + o jargão avançado citado na seção 4.6 da spec.
ADV = ["curva de juros", "forward guidance", "hiato do produto", "ebitda ajustado", "covenants",
       "política monetária contracionista", "expectativas ancoradas", "balanço de riscos", "demanda agregada",
       "juros reais", "desinflação", "prêmio de risco", "banda de tolerância", "fluxo de capitais", "risco fiscal"]


def audit_glossary() -> list[str]:
    raw = json.loads(Path("data/cache/bcb_glossario.json").read_text(encoding="utf-8"))
    terms = set()
    for k in raw:
        k = k.replace("\xa0", " ")
        base = re.sub(r"\s*\(.*?\)", "", k).strip()
        terms.add(base.lower())
        for inner in re.findall(r"\((.*?)\)", k):
            if not inner.startswith(("no ", "em ", "ou ")):
                terms.add(inner.lower())
    return sorted(t for t in terms | set(ADV) if len(t) > 2)


GLOSS = audit_glossary()


# ----------------------------------------------------------------------------------------- texto
def flatten(content: dict, fmt: str) -> str:
    if fmt == "texto_analitico":
        parts = [content.get("title", ""), content.get("subtitle", "")]
        for s in ("introduction", "development", "analysis", "conclusion"):
            v = content.get(s, "")
            parts.append(v.get("content", "") if isinstance(v, dict) else str(v))
        return "\n".join(parts)
    if fmt == "carrossel":
        slides = content.get("slides") or (content.get("carousel") or {}).get("slides", [])
        return "\n".join(f"{s.get('title', '')}. {s.get('body', '')}" for s in slides)
    if fmt == "roteiro_video":
        return "\n".join(sc.get("fala_escrita") or sc.get("spoken") or "" for sc in content.get("scenes", []))
    return json.dumps(content, ensure_ascii=False)


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(WORD.findall(s)) >= 3]


def words(text: str) -> list[str]:
    return [w.lower() for w in WORD.findall(text)]


def syllables_groups(word: str) -> int:
    return max(1, len(re.findall(r"[aeiouáéíóúâêôãõàü]+", word.lower())))


def flesch_ptbr_martins(text: str) -> float:
    """Flesch adaptado ao português (Martins et al., 1996): 248,835 − 1,015·ASL − 84,6·ASW.

    Sílabas por grupos vocálicos (heurística; subconta hiatos). Só para comparação de auditoria.
    """
    ws = WORD.findall(text)
    if not ws:
        return 0.0
    sents = max(1, len([p for p in re.split(r"[.!?]+", text) if p.strip()]))
    return 248.835 - 1.015 * (len(ws) / sents) - 84.6 * (sum(syllables_groups(w) for w in ws) / len(ws))


def term_occurrences(text: str) -> list[tuple[str, int]]:
    low = text.lower()
    hits = []
    for t in GLOSS:
        for m in re.finditer(rf"(?<!\w){re.escape(t)}(?!\w)", low):
            hits.append((t, m.start()))
    return hits


EXPL = ("ou seja", "isto é", "que é", "que são", "significa", "chamad", " é a ", " é o ", "(", "—", ":")


def unexplained_terms(text: str) -> list[str]:
    """Heurística: termo do glossário sem marcador de explicação nas 20 palavras seguintes ou 5 anteriores."""
    low = text.lower()
    out = []
    for t, pos in term_occurrences(text):
        before = " ".join(low[:pos].split()[-5:])
        after = " ".join(low[pos + len(t):].split()[:20])
        if not any(m in after or m in before for m in EXPL):
            out.append(t)
    return sorted(set(out))


def levenshtein_words(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, wa in enumerate(a, 1):
        cur = [i]
        for j, wb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (wa != wb)))
        prev = cur
    return prev[-1]


def content_words(s: str) -> set[str]:
    return {w for w in words(s) if len(w) >= 4 and w not in STOP}


def unsupported_share(text: str, source: str) -> float:
    src = [content_words(s) for s in sentences(source)] or [set()]
    gen = sentences(text)
    if not gen:
        return 0.0
    bad = 0
    for s in gen:
        cw = content_words(s)
        if not cw:
            continue
        best = max(len(cw & ss) / len(cw) for ss in src)
        bad += best < 0.5
    return bad / len(gen)


def verbatim_copy_share(text: str, source: str, n: int = 6) -> float:
    """Fração das palavras da saída cobertas por sequências de n palavras copiadas literalmente da fonte."""
    tw, sw = words(text), words(source)
    src_ngrams = {tuple(sw[i:i + n]) for i in range(len(sw) - n + 1)}
    covered = [False] * len(tw)
    for i in range(len(tw) - n + 1):
        if tuple(tw[i:i + n]) in src_ngrams:
            for j in range(i, i + n):
                covered[j] = True
    return sum(covered) / max(1, len(tw))


def numbers_without_origin(text: str, source: str) -> list[str]:
    src_tokens = set(re.findall(r"\d[\d.,]*%?", source))
    src_bare = {t.rstrip("%").rstrip(".,") for t in src_tokens}
    return sorted({n for n in extract_numbers(text) if n.rstrip(".,") not in src_tokens
                   and n.rstrip("%").rstrip(".,") not in src_bare})


# ----------------------------------------------------------------------------------------- A5/A6/A7
def run_a5_a6(tree: str) -> dict:
    data = json.loads((RES / f"outputs_{tree}.json").read_text(encoding="utf-8"))["docs"]
    # frases de template: aparecem idênticas em saídas de >=2 documentos diferentes
    sent_docs: dict[str, set[str]] = {}
    for doc, d in data.items():
        for o in d["outputs"]:
            for s in sentences(flatten(o["conteudo"], o["formato"])):
                sent_docs.setdefault(s.lower(), set()).add(doc)
    template_sents = {s for s, ds in sent_docs.items() if len(ds) >= 2}

    per_output, pairs = [], []
    for doc, d in data.items():
        src = d["source"]
        src_w = len(WORD.findall(src))
        by_fmt: dict[str, dict[str, str]] = {}
        for o in d["outputs"]:
            fmt, lvl = o["formato"], o["nivel"]
            text = flatten(o["conteudo"], fmt)
            by_fmt.setdefault(fmt, {})[lvl] = text
            ws = WORD.findall(text)
            ss = sentences(text)
            occ = term_occurrences(text)
            per_output.append({
                "arvore": tree, "doc": doc, "palavras_fonte": src_w, "formato": fmt, "nivel": lvl,
                "palavras": len(ws),
                "flesch_codigo": round(flesch_reading_ease_pt(text), 1),
                "flesch_ptbr_martins": round(flesch_ptbr_martins(text), 1),
                "densidade_ocorr_100": round(100 * len(occ) / max(1, len(ws)), 2),
                "densidade_codigo_glossario_config": round(term_density_per_100_words(text, load_glossary_terms()), 2),
                "media_palavras_frase": round(len(ws) / max(1, len(ss)), 1),
                "termos_sem_explicacao": unexplained_terms(text) if lvl == "iniciante" else None,
                "rep_frases": round(sentence_repetition_ratio(text), 3),
                "rep_trigramas": round(trigram_repetition_ratio(text), 3),
                "frases_sem_respaldo": round(unsupported_share(text, src), 2),
                "copia_literal_6g": round(verbatim_copy_share(text, src), 2),
                "numeros_sem_origem": numbers_without_origin(text, src),
                "frases_template": round(sum(s.lower() in template_sents for s in ss) / max(1, len(ss)), 2),
                "razao_saida_fonte": round(len(ws) / max(1, src_w), 2),
            })
        for fmt, lv in by_fmt.items():
            for a, b in combinations(LEVELS, 2):
                if a in lv and b in lv:
                    wa, wb = words(lv[a]), words(lv[b])
                    pairs.append({
                        "arvore": tree, "doc": doc, "formato": fmt, "par": f"{a[:3]}-{b[:3]}",
                        "trigramas_jaccard": round(trigram_overlap_ratio(lv[a], lv[b]), 2),
                        "edicao_palavras": levenshtein_words(wa, wb),
                        "edicao_norm": round(levenshtein_words(wa, wb) / max(1, len(wa), len(wb)), 2),
                    })
    return {"saidas": per_output, "pares": pairs}


# ----------------------------------------------------------------------------------------- B6
def run_b6() -> list[dict]:
    src_mod = __import__("tests.audit.baseline.documents", fromlist=["DOC_MEDIO"])
    source = src_mod.DOC_MEDIO.strip()
    thresholds = load_thresholds()
    forbidden = ["compre agora", "venda agora", "garantia de lucro", "recomendo comprar", "recomendo vender"]
    rows = []
    # Depois da correção: o mesmo avaliador usado pelo pipeline (src/evaluation/deterministic.py),
    # com o glossário configurado e uma explicação de impacto aprovada só para o caso "Em geral,".
    from tests.unit.test_avaliador_deterministico import _evaluate

    for case in build_cases():
        report = _evaluate(case)
        text = flatten(case["conteudo"], case["formato"])
        rows.append({
            "id": case["id"], "tipo": case["tipo"], "nivel": case["nivel"], "esperado": case["esperado"],
            "palavras": len(WORD.findall(text)), "passou": report.passed, "falhas": report.failure_codes,
            "flesch": report.metrics["flesch"], "densidade": report.metrics["densidade_termos"],
            "classificado": report.classified_level, "rep_frases": report.metrics["repeticao_frases"],
        })
    return rows


def _md(rows: list[dict], cols: list[str]) -> str:
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    result = {"glossario_auditoria_n": len(GLOSS), "glossario_config_n": len(load_glossary_terms())}
    for tree in ("head", "wt"):
        result[tree] = run_a5_a6(tree)
    result["b6"] = run_b6()
    (RES / "experimentos.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"glossário config: {result['glossario_config_n']} termos; glossário de auditoria: {result['glossario_auditoria_n']}")
    for tree in ("head", "wt"):
        print(f"\n## A5/A6 saídas — {tree}")
        print(_md(result[tree]["saidas"], ["doc", "formato", "nivel", "palavras", "razao_saida_fonte", "flesch_codigo",
                                           "flesch_ptbr_martins", "densidade_ocorr_100", "media_palavras_frase",
                                           "rep_frases", "rep_trigramas", "frases_sem_respaldo", "copia_literal_6g",
                                           "frases_template",
                                           "numeros_sem_origem", "termos_sem_explicacao"]))
        print(f"\n## A5 pares — {tree}")
        print(_md(result[tree]["pares"], ["doc", "formato", "par", "trigramas_jaccard", "edicao_palavras", "edicao_norm"]))
    print("\n## B6 (avaliador corrigido)")
    print(_md(result["b6"], ["id", "tipo", "nivel", "palavras", "esperado", "passou", "falhas", "flesch", "densidade",
                             "classificado", "rep_frases"]))
