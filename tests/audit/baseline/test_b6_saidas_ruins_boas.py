"""Experimento B6: 12 saidas ruins e 3 boas contra as metricas determinísticas; tabela esperado x obtido."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from src.evaluation.thresholds import load_thresholds
from src.evaluation.flesch_ptbr import flesch_reading_ease_pt, evaluate_level
from src.evaluation.term_density import term_density_per_100_words
from src.evaluation.redundancy import sentence_repetition_ratio, trigram_repetition_ratio
from src.evaluation.format_checks import count_words, has_emoji, has_forbidden_terms
from src.evaluation.grounding import extract_numbers, all_generated_numbers_exist
from src.evaluation.coverage import main_points_coverage
from src.evaluation.level_classifier import classify_level

THRESHOLDS = load_thresholds()
FORBIDDEN = ["compre agora", "venda agora", "garantia de lucro", "recomendo comprar", "recomendo vender"]

# 12 saidas ruins (cada uma com um problema especifico)
BAD_OUTPUTS = {
    "b1_padding": ("texto " * 400, "tamanho_fora_do_intervalo"),
    "b2_repeticao_frase": ("O Copom decidiu manter a Selic. O Copom decidiu manter a Selic. O Copom decidiu manter a Selic. " * 50, "redundancia_excessiva"),
    "b3_numero_sem_origem": ("A Selic esta em 99,99% ao ano, muito acima do normal.", "numero_ou_data_nao_encontrado_na_fonte"),
    "b4_emoji": ("O Copom decidiu manter a Selic em 10,50%. 📈 A inflacao esta controlada.", "emoji_encontrado"),
    "b5_termo_proibido": ("Compre agora ações da empresa com garantia de lucro.", "termo_proibido_encontrado"),
    "b6_sem_cobertura": ("Texto generico sobre economia sem mencionar os pontos centrais.", "cobertura_de_pontos_centrais_insuficiente"),
    "b7_flesch_baixo_iniciante": (
        "A autoridade monetária brasileira optou por preservar a taxa básica de juros no patamar atual de dez vírgula cinco zero por cento ao ano, "
        "considerando o balanço de riscos inflacionário e as expectativas do mercado para o próximo ciclo de política monetária. "
        "O Comitê avalia que a manutenção da taxa é adequada para assegurar a convergência da inflação para a meta estabelecida pelo Conselho Monetário Nacional.",
        "legibilidade_fora_da_faixa",
    ),
    "b8_flesch_alto_avancado": (
        "O Copom segurou a Selic. Juros alto. Inflacao alta. Sem mudança. proxima reuniao em 45 dias.",
        "legibilidade_fora_da_faixa",
    ),
    "b9_saida_muito_curta": ("O Copom mudou a Selic.", "tamanho_fora_do_intervalo"),
    "b10_marcador_em_geral_fora_glossario": ("Em geral, a economia vai melhorar muito proximo ano sem qualquer base.", "marcador_em_geral_fora_do_glossario"),
    "b11_densidade_alta_iniciante": ("selic ipca copom juros taxa selic ipca copom juros taxa selic ipca copom juros taxa selic ipca copom juros taxa " * 10, "densidade_fora_da_faixa"),
    "b12_nivel_classificado_diferente": (
        "O Comitê de Política Monetária do Banco Central decidiu manter a taxa Selic em 10,50% ao ano por unanimidade. "
        "O IPCA acumula 4,5% em doze meses. O próximo encontro está marcado para daqui a 45 dias. "
        "A política monetária contracionista está sendo mantida para assegurar a convergência da inflação para a meta de 3%. "
        "O cenário internacional segue desafiador com juros elevados nas economias avançadas. "
        "A atividade econômica doméstica mostra resiliência, mas o mercado de trabalho ainda apresenta sinais de desaceleração. "
        "O governo anunciou medidas de contenção de gastos e a dívida pública segue em patamar elevado.",
        "nivel_classificado_diferente_do_alvo",
    ),
}

# 3 saidas boas
GOOD_OUTPUTS = {
    "g1_iniciante": (
        "O Copom decidiu manter a taxa Selic em 10,50% ao ano. A inflação está em 4,5%. "
        "O próximo encontro está marcado para daqui a 45 dias."
    ),
    "g2_intermediario": (
        "O Comitê de Política Monetária do Banco Central decidiu manter a taxa Selic em 10,50% ao ano. "
        "A decisão foi unânime. O IPCA acumula 4,5% em doze meses, acima da meta de 3%. "
        "O próximo encontro do Copom está marcado para daqui a 45 dias."
    ),
    "g3_avancado": (
        "O Copom decidiu, por unanimidade, manter a taxa Selic em 10,50% ao ano, preservando o viés contracionista da política monetária. "
        "O IPCA acumula 4,5% em 12 meses, acima do centro da meta de 3%. O comitê avalia que o balanço de riscos justifica a manutenção do patamar atual. "
        "O próximo encontro está agendado para daqui a 45 dias."
    ),
}

SOURCE = ("O Comitê de Política Monetária do Banco Central decidiu manter a taxa Selic em 10,50% ao ano. "
          "A decisão foi unânime. O IPCA acumula 4,5% em doze meses, acima da meta de 3%. "
          "O próximo encontro do Copom está marcado para daqui a 45 dias.")
MAIN_POINTS = ["Selic", "IPCA", "proximo encontro"]


def _evaluate(text: str, level: str) -> dict:
    words = count_words(text)
    flesch = flesch_reading_ease_pt(text)
    density = term_density_per_100_words(text, ["selic", "copom", "ipca", "juros", "inflacao"])
    numbers = extract_numbers(text)
    numbers_ok = all_generated_numbers_exist(text, SOURCE)
    coverage = main_points_coverage(text, MAIN_POINTS)
    emoji = has_emoji(text)
    forbidden = has_forbidden_terms(text, FORBIDDEN)
    sent_rep = sentence_repetition_ratio(text)
    tri_rep = trigram_repetition_ratio(text)
    classified = classify_level(text, ["selic", "copom", "ipca", "juros", "inflacao"])

    level_ok = evaluate_level(flesch, level, THRESHOLDS)
    density_ok = {
        "iniciante": density <= THRESHOLDS.get("densidade_iniciante_max", 3),
        "intermediario": THRESHOLDS.get("densidade_intermediaria_min", 3) <= density <= THRESHOLDS.get("densidade_intermediaria_max", 8),
        "avancado": density >= THRESHOLDS.get("densidade_avancado_min", 8),
    }.get(level, True)
    size_ok = 350 <= words <= 500

    failures = []
    if not level_ok:
        failures.append("legibilidade_fora_da_faixa")
    if not density_ok:
        failures.append("densidade_fora_da_faixa")
    if not numbers_ok:
        failures.append("numero_ou_data_nao_encontrado_na_fonte")
    if coverage < len(MAIN_POINTS):
        failures.append("cobertura_de_pontos_centrais_insuficiente")
    if emoji:
        failures.append("emoji_encontrado")
    if forbidden:
        failures.append("termo_proibido_encontrado")
    if sent_rep > 0.95:
        failures.append("redundancia_excessiva")
    if not size_ok:
        failures.append("tamanho_fora_do_intervalo")
    if classified != level and classified != "indistinto":
        failures.append("nivel_classificado_diferente_do_alvo")

    return {
        "word_count": words,
        "flesch": round(flesch, 3),
        "level_flesch_ok": level_ok,
        "term_density": round(density, 3),
        "density_ok": density_ok,
        "numbers": numbers,
        "numbers_ok": numbers_ok,
        "coverage": f"{coverage}/{len(MAIN_POINTS)}",
        "emoji": emoji,
        "forbidden_terms": forbidden,
        "sentence_repetition": round(sent_rep, 4),
        "trigram_repetition": round(tri_rep, 4),
        "size_ok": size_ok,
        "classified_level": classified,
        "failures": failures,
        "passed": len(failures) == 0,
    }


def run_b6(output_dir: Path) -> dict:
    resultados = {}

    # Esperado: todas ruins devem falhar (passed=False), todas boas devem passar (passed=True)
    esperado_ruins = {name: False for name in BAD_OUTPUTS}
    esperado_boas = {name: True for name in GOOD_OUTPUTS}

    resultados_obtidos = {}
    for name, (text, expected_failure) in BAD_OUTPUTS.items():
        level = "iniciante"
        ev = _evaluate(text, level)
        resultados_obtidos[name] = {
            "esperado_passed": False,
            "obtido_passed": ev["passed"],
            "obtido_failures": ev["failures"],
            "falha_esperada": expected_failure,
            "correto": (not ev["passed"]) and (expected_failure in ev["failures"]),
            "metricas": ev,
        }

    for name, text in GOOD_OUTPUTS.items():
        level = {"g1_iniciante": "iniciante", "g2_intermediario": "intermediario", "g3_avancado": "avancado"}[name]
        ev = _evaluate(text, level)
        resultados_obtidos[name] = {
            "esperado_passed": True,
            "obtido_passed": ev["passed"],
            "obtido_failures": ev["failures"],
            "falha_esperada": None,
            "correto": ev["passed"],
            "metricas": ev,
        }

    resultados["ruins"] = {k: v for k, v in resultados_obtidos.items() if k in BAD_OUTPUTS}
    resultados["boas"] = {k: v for k, v in resultados_obtidos.items() if k in GOOD_OUTPUTS}

    todos_corretos = all(v["correto"] for v in resultados_obtidos.values())

    report = {
        "experimento": "B6",
        "descricao": "12 saidas ruins e 3 boas contra as metricas determinísticas; tabela esperado x obtido",
        "total_casos": len(resultados_obtidos),
        "todos_corretos": todos_corretos,
        "resultados": resultados,
        "executado_em": datetime.now(UTC).isoformat(),
    }
    out_path = output_dir / "b6_result.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = run_b6(out_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))