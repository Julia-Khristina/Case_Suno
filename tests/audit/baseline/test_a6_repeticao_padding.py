"""Experimento A6: repeticao, padding, numeros sem origem, tamanho da saída versus tamanho da fonte."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from src.evaluation.format_checks import count_words, has_emoji
from src.evaluation.grounding import extract_numbers, all_generated_numbers_exist
from src.evaluation.redundancy import sentence_repetition_ratio, trigram_repetition_ratio

SOURCE_TEXTS = {
    "curto": "O Copom decidiu manter a Selic em 10,50% ao ano. A inflacao esta em 4,5%. O proximo encontro sera daqui a 45 dias.",
    "medio": (
        "O Comitê de Política Monetária do Banco Central decidiu manter a taxa Selic em 10,50% ao ano. "
        "A decisão foi unânime. O IPCA acumula 4,5% em doze meses, acima da meta de 3%. "
        "O cenário externo segue desafiador com juros elevados nos Estados Unidos. "
        "A atividade econômica doméstica mostra resiliência, mas o mercado de trabalho ainda apresenta sinais de desaceleração. "
        "O próximo encontro do Copom está marcado para daqui a 45 dias."
    ),
    "longo": (
        "O Comitê de Política Monetária (Copom) do Banco Central do Brasil reuniu-se e decidiu, por unanimidade, "
        "manter a taxa Selic em 10,50% ao ano. O comunicado afirma que a política monetária segue contracionista "
        "para garantir a convergência da inflação para a meta de 3% até 2026. O IPCA acumulado em 12 meses encontra-se em 4,5%. "
        "No cenário internacional, o Federal Reserve mantém juros elevados, afetando o fluxo de capitais para mercados emergentes. "
        "No cenário doméstico, a atividade econômica apresentou resiliência, com crescimento do PIB acima das expectativas iniciais. "
        "O mercado de trabalho mostra sinais mistos, com a taxa de desemprego em 7,8%. O governo federal anunciou medidas de contenção de gastos. "
        "As expectativas de inflação para 2027 encontram-se em 3,5%, segundo o boletim Focus. "
        "O Copom alerta que choques de oferta em alimentos e energia podem pressionar a inflação no curto prazo. "
        "O próximo encontro está agendado para daqui a 45 dias. O Banco Central reafirma seu compromisso com a estabilidade de preços."
    ),
}

# Saídas simuladas ruins (com padding, repetição, números sem origem)
BAD_OUTPUTS = {
    "bad_padding": (
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
        "texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto texto "
    ),
    "bad_repetition": (
        "O Copom decidiu manter a Selic em 10,50% ao ano. O Copom decidiu manter a Selic em 10,50% ao ano. "
        "O Copom decidiu manter a Selic em 10,50% ao ano. O Copom decidiu manter a Selic em 10,50% ao ano. "
        "O Copom decidiu manter a Selic em 10,50% ao ano. O Copom decidiu manter a Selic em 10,50% ao ano. "
        "O Copom decidiu manter a Selic em 10,50% ao ano. O Copom decidiu manter a Selic em 10,50% ao ano. "
    ),
    "bad_number_no_origin": (
        "A Selic esta em 99,99% ao ano, muito acima do normal. O IPCA esta em 25,00%. "
        "O Banco Central decidiu aumentar os juros para 15,00% sem qualquer base na fonte."
    ),
    "bad_output_too_large": (
        "O Copom decidiu manter a Selic em 10,50% ao ano. " * 200
    ),
}

# Saídas boas (coerentes com a fonte)
GOOD_OUTPUTS = {
    "good_curto": (
        "O Copom decidiu manter a taxa Selic em 10,50% ao ano. A inflacao medida pelo IPCA esta em 4,5%. "
        "O proximo encontro do Comitê esta marcado para daqui a 45 dias."
    ),
    "good_medio": (
        "O Comitê de Política Monetária do Banco Central decidiu manter a taxa Selic em 10,50% ao ano. "
        "A decisão foi unânime. O IPCA acumula 4,5% em doze meses, acima da meta de 3%. "
        "O próximo encontro do Copom está marcado para daqui a 45 dias."
    ),
    "good_longo": (
        "O Copom decidiu manter a Selic em 10,50% ao ano. O IPCA acumulado em 12 meses encontra-se em 4,5%. "
        "O próximo encontro do Copom está agendado para daqui a 45 dias. O Banco Central reafirma seu compromisso com a estabilidade de preços."
    ),
}


def _metrics(text: str, source: str) -> dict:
    words = count_words(text)
    numbers = extract_numbers(text)
    numbers_ok = all_generated_numbers_exist(text, source)
    return {
        "word_count": words,
        "sentence_repetition": round(sentence_repetition_ratio(text), 4),
        "trigram_repetition": round(trigram_repetition_ratio(text), 4),
        "numbers_found": numbers,
        "numbers_all_in_source": numbers_ok,
        "has_emoji": has_emoji(text),
        "output_vs_source_ratio": round(words / max(1, count_words(source)), 2),
    }


def run_a6(output_dir: Path) -> dict:
    results = {}
    for size, source in SOURCE_TEXTS.items():
        entry = {"source": {"word_count": count_words(source), "text": source[:80] + "..."}}
        for out_name, output in BAD_OUTPUTS.items():
            entry[out_name] = _metrics(output, source)
        for out_name, output in GOOD_OUTPUTS.items():
            entry[f"good_{out_name.replace('good_', '')}"] = _metrics(output, source)
        results[size] = entry

    report = {
        "experimento": "A6",
        "descricao": "Repeticao, padding, numeros sem origem, tamanho da saída versus tamanho da fonte",
        "resultados": results,
        "executado_em": datetime.now(UTC).isoformat(),
    }
    out_path = output_dir / "a6_result.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = run_a6(out_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))