"""Relatório experimental reproduzível: matriz de confusão de níveis e custo/latência.

Uso:
    python scripts/relatorio_experimental.py            # benchmark + execuções gravadas no PostgreSQL
    python scripts/relatorio_experimental.py --sem-banco # só o benchmark (não precisa de banco nem de LLM)

Saídas: documents/resultados_experimentais.md e documents/resultados_experimentais.json.

Fontes dos números (nenhum é digitado à mão):
1. Benchmark escrito à mão (tests/audit/audit_b6_cases.py): saídas boas por nível e saídas ruins com defeito de
   nível conhecido. Nível esperado = nível do caso.
2. Execuções reais gravadas no banco (tabelas tentativas e avaliacoes_juiz): nível pedido x nível classificado de
   cada tentativa, tokens e latência por chamada. O nível é mostrado como foi gravado na execução e também
   reclassificado com o código atual a partir do conteúdo gravado, para separar mudança de código de mudança
   de saída.
O classificador é o mesmo do pipeline (src/evaluation/deterministic.py): texto do formato → Flesch PT-BR (Martins)
e densidade de termos técnicos do glossário → faixas de config/limiares.yaml → nível ou "indistinto".
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.deterministic import classify_scores, technical_density, text_for_metrics  # noqa: E402
from src.evaluation.flesch_ptbr import flesch_reading_ease_pt  # noqa: E402
from src.evaluation.offline_metrics import build_confusion_matrix, f1_for, precision_for, recall_for  # noqa: E402
from src.evaluation.thresholds import load_thresholds  # noqa: E402
from src.glossary.reader import load_glossary  # noqa: E402

LEVELS = ["iniciante", "intermediario", "avancado"]
LABELS = LEVELS + ["indistinto"]
NAMES = {"iniciante": "Iniciante", "intermediario": "Intermediário", "avancado": "Avançado", "indistinto": "Indistinto"}
OUT_MD = ROOT / "documents" / "resultados_experimentais.md"
OUT_JSON = ROOT / "documents" / "resultados_experimentais.json"


def classify(content: dict, fmt: str, glossary, thresholds) -> tuple[str, float, float]:
    text = text_for_metrics(content, fmt)
    flesch = flesch_reading_ease_pt(text)
    density = technical_density(text, glossary)
    return classify_scores(flesch, density, thresholds), round(flesch, 1), round(density, 2)


def summarize(expected: list[str], predicted: list[str]) -> dict:
    matrix = build_confusion_matrix(expected, predicted, labels=LABELS)
    # precisão sem nenhuma previsão do nível é indefinida (None), não 0: o classificador não errou, não previu
    per_level = {lvl: {"precisao": round(precision_for(matrix, lvl), 3) if lvl in predicted else None,
                       "recall": round(recall_for(matrix, lvl), 3), "f1": round(f1_for(matrix, lvl), 3)}
                 for lvl in LEVELS}
    hits = sum(1 for e, p in zip(expected, predicted) if e == p)
    return {"n": len(expected), "acerto": round(hits / len(expected), 3) if expected else None,
            "indistinto": sum(1 for p in predicted if p == "indistinto"), "matriz": matrix["matrix"],
            "por_nivel": per_level}


# ------------------------------------------------------------------------------------------- benchmark
def benchmark(glossary, thresholds) -> dict:
    from tests.audit.audit_b6_cases import build_cases

    rows = []
    for case in build_cases():
        if case["formato"] != "texto_analitico":
            continue
        # o caso de nível é o que interessa à matriz: boas (cada nível) e as ruins que trocam o nível
        level_case = case["tipo"] == "boa" or case["id"] in {"b08_iniciante_jargao_sem_explicacao",
                                                             "b09_avancado_sem_jargao"}
        predicted, flesch, density = classify(case["conteudo"], case["formato"], glossary, thresholds)
        rows.append({"id": case["id"], "tipo": case["tipo"], "esperado": case["nivel"], "classificado": predicted,
                     "flesch": flesch, "densidade": density, "caso_de_nivel": level_case})
    level_rows = [r for r in rows if r["caso_de_nivel"]]
    return {"casos": rows, "resumo_casos_de_nivel": summarize([r["esperado"] for r in level_rows],
                                                              [r["classificado"] for r in level_rows]),
            "resumo_todos": summarize([r["esperado"] for r in rows], [r["classificado"] for r in rows])}


# ------------------------------------------------------------------------------------------- execuções reais
def live_runs(conn, glossary, thresholds) -> dict | None:
    with conn.cursor() as cur:
        cur.execute("""SELECT e.id_execucao::text, e.criado_em, e.total_tokens, e.latencia_total, e.versao_modelo,
                              d.titulo_origem
                       FROM execucoes e LEFT JOIN documentos d ON d.hash = e.hash_documento
                       WHERE EXISTS (SELECT 1 FROM materiais m JOIN tentativas t USING (id_material)
                                     WHERE m.id_execucao = e.id_execucao)
                       ORDER BY e.criado_em""")
        executions = [dict(zip(["id", "criado_em", "tokens", "latencia", "modelos", "titulo"], r)) for r in cur.fetchall()]
        cur.execute("""SELECT f->>'code', COUNT(*) FROM tentativas t, jsonb_array_elements(COALESCE(t.falhas, '[]'::jsonb)) f
                       GROUP BY 1 ORDER BY 2 DESC""")
        failure_codes = {code: int(n) for code, n in cur.fetchall() if code}
        cur.execute("""SELECT m.id_execucao::text, m.nivel, m.formato, m.status_avaliacao, t.numero_tentativa,
                              t.nivel_classificado, t.conteudo, t.tokens, t.latencia, t.id_modelo,
                              jsonb_array_length(COALESCE(t.falhas, '[]'::jsonb)), j.tokens, j.latencia, j.media_ponderada
                       FROM materiais m JOIN tentativas t USING (id_material)
                       LEFT JOIN avaliacoes_juiz j USING (id_tentativa)
                       ORDER BY m.id_execucao, m.nivel, m.formato, t.numero_tentativa""")
        keys = ["execucao", "nivel", "formato", "status", "tentativa", "classificado_gravado", "conteudo", "tokens",
                "latencia", "modelo", "n_falhas", "tokens_juiz", "latencia_juiz", "nota_juiz"]
        attempts = [dict(zip(keys, r)) for r in cur.fetchall()]
    conn.rollback()
    if not attempts:
        return None
    for a in attempts:
        content = a.pop("conteudo") or {}
        a["classificado_atual"] = classify(content, a["formato"], glossary, thresholds)[0] if content else "indistinto"
        a["latencia"] = float(a["latencia"] or 0)
        a["latencia_juiz"] = float(a["latencia_juiz"] or 0) if a["latencia_juiz"] is not None else None

    finals = {}
    for a in attempts:  # última tentativa de cada material = versão entregue para revisão
        finals[(a["execucao"], a["nivel"], a["formato"])] = a
    cost = defaultdict(lambda: {"tentativas": 0, "tokens": 0, "latencia": 0.0})
    for a in attempts:
        for key in (a["formato"], f"nivel:{a['nivel']}", "geracao"):
            cost[key]["tentativas"] += 1
            cost[key]["tokens"] += int(a["tokens"] or 0)
            cost[key]["latencia"] += a["latencia"]
        if a["tokens_juiz"] is not None:
            cost["juiz"]["tentativas"] += 1
            cost["juiz"]["tokens"] += int(a["tokens_juiz"] or 0)
            cost["juiz"]["latencia"] += a["latencia_juiz"] or 0.0
    for ex in executions:
        generation = sum(int(a["tokens"] or 0) + int(a["tokens_juiz"] or 0) for a in attempts if a["execucao"] == ex["id"])
        ex["tokens_extracao_estimados"] = max(0, int(ex["tokens"] or 0) - generation)
        ex["criado_em"] = ex["criado_em"].astimezone(ZoneInfo("America/Sao_Paulo")).isoformat()
        ex["latencia"] = float(ex["latencia"] or 0)
    statuses = defaultdict(int)
    for final in finals.values():
        statuses[final["status"]] += 1
    return {
        "execucoes": executions,
        "tentativas": attempts,
        "matriz_tentativas_gravada": summarize([a["nivel"] for a in attempts], [a["classificado_gravado"] or "indistinto"
                                                                                for a in attempts]),
        "matriz_tentativas_codigo_atual": summarize([a["nivel"] for a in attempts], [a["classificado_atual"]
                                                                                     for a in attempts]),
        "matriz_versao_final_gravada": summarize([f["nivel"] for f in finals.values()],
                                                 [f["classificado_gravado"] or "indistinto" for f in finals.values()]),
        "custo": {k: {**v, "tokens_medios": round(v["tokens"] / v["tentativas"]) if v["tentativas"] else 0,
                      "latencia_media_s": round(v["latencia"] / v["tentativas"], 2) if v["tentativas"] else 0.0}
                  for k, v in cost.items()},
        "status_finais": dict(statuses),
        "falhas_por_codigo": failure_codes,
        "tentativas_por_material": round(len(attempts) / len(finals), 2),
    }


# ------------------------------------------------------------------------------------------- Markdown
def matrix_md(summary: dict) -> str:
    head = "| Pedido \\ Classificado | " + " | ".join(NAMES[c] for c in LABELS) + " | Recall |\n"
    head += "|---|" + "---|" * (len(LABELS) + 1) + "\n"
    rows = []
    for lvl in LEVELS:
        cells = " | ".join(str(summary["matriz"][lvl][c]) for c in LABELS)
        rows.append(f"| **{NAMES[lvl]}** | {cells} | {summary['por_nivel'][lvl]['recall']:.2f} |")
    foot = (f"\nn = {summary['n']} · acerto = {summary['acerto']:.0%} · indistinto = {summary['indistinto']} · "
            "precisão por nível: " + ", ".join(
                f"{NAMES[l]} " + ("—" if summary["por_nivel"][l]["precisao"] is None
                                  else f"{summary['por_nivel'][l]['precisao']:.2f}") for l in LEVELS))
    return head + "\n".join(rows) + "\n" + foot


def to_markdown(result: dict) -> str:
    lines = [f"# Resultados experimentais\n",
             f"Gerado por `python scripts/relatorio_experimental.py` em {result['gerado_em']}. "
             "Não edite à mão: rode o script de novo.\n",
             "## 1. Matriz de confusão de níveis: benchmark escrito à mão\n",
             "Saídas boas de cada nível e as saídas ruins que trocam o nível (Iniciante com jargão sem explicação; "
             "texto Iniciante entregue como Avançado).\n", matrix_md(result["benchmark"]["resumo_casos_de_nivel"]), "",
             "| Caso | Esperado | Classificado | Flesch PT-BR | Densidade /100 |", "|---|---|---|---|---|"]
    for row in result["benchmark"]["casos"]:
        if row["caso_de_nivel"]:
            lines.append(f"| {row['id']} | {NAMES[row['esperado']]} | {NAMES[row['classificado']]} | {row['flesch']} | "
                         f"{row['densidade']} |")
    live = result.get("execucoes_reais")
    if live:
        lines += ["", "## 2. Matriz de confusão de níveis: saídas reais do modelo\n",
                  f"{len(live['execucoes'])} execução(ões) gravada(s), {len(live['tentativas'])} tentativas "
                  f"({live['tentativas_por_material']} por material).\n",
                  "### Todas as tentativas, nível gravado na execução\n", matrix_md(live["matriz_tentativas_gravada"]),
                  "", "### Todas as tentativas, reclassificadas com o código atual\n",
                  matrix_md(live["matriz_tentativas_codigo_atual"]), "",
                  "### Versão final de cada material (a que vai para revisão)\n",
                  matrix_md(live["matriz_versao_final_gravada"]), "",
                  "Status final dos materiais: " + ", ".join(f"{k}: {v}" for k, v in live["status_finais"].items()), "",
                  "### Por que as tentativas reprovaram (falhas das métricas determinísticas)\n",
                  "| Falha | Tentativas |", "|---|---|",
                  *[f"| {code} | {n} |" for code, n in live["falhas_por_codigo"].items()], "",
                  "## 3. Custo e latência medidos\n",
                  "| Etapa | Chamadas | Tokens | Tokens por chamada | Latência média (s) |", "|---|---|---|---|---|"]
        order = ["texto_analitico", "carrossel", "roteiro_video", "nivel:iniciante", "nivel:intermediario",
                 "nivel:avancado", "geracao", "juiz"]
        for key in order:
            item = live["custo"].get(key)
            if item:
                lines.append(f"| {key} | {item['tentativas']} | {item['tokens']} | {item['tokens_medios']} | "
                             f"{item['latencia_media_s']} |")
        if "juiz" not in live["custo"]:
            lines.append("| juiz | 0 | 0 | — | — |")
        lines += ["", "| Execução | Documento | Tokens totais | Extração (estimada) | Latência somada (s) | Modelos |",
                  "|---|---|---|---|---|---|"]
        for ex in live["execucoes"]:
            lines.append(f"| {ex['criado_em'][:16]} | {(ex['titulo'] or '')[:50]} | {ex['tokens']} | "
                         f"{ex['tokens_extracao_estimados']} | {ex['latencia']:.1f} | {ex['modelos']} |")
    else:
        lines += ["", "## 2 e 3. Execuções reais\n", "Sem banco ou sem execuções gravadas: rode com o PostgreSQL ativo."]
    return "\n".join(lines) + "\n"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    glossary, thresholds = load_glossary(), load_thresholds()
    result = {"gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"), "benchmark": benchmark(glossary, thresholds)}
    if "--sem-banco" not in sys.argv:
        try:
            from src.persistence.database import connect

            with connect() as conn:
                result["execucoes_reais"] = live_runs(conn, glossary, thresholds)
        except Exception as exc:  # noqa: BLE001
            print(f"Banco indisponível ({type(exc).__name__}): só o benchmark será gerado.")
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    OUT_MD.write_text(to_markdown(result), encoding="utf-8")
    print(f"Gerado: {OUT_MD.relative_to(ROOT)} e {OUT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
