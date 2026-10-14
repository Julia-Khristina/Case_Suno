"""Seed simple configuration and reference-day data."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "data" / "reference_days"
SEED_DIR.mkdir(parents=True, exist_ok=True)


REFERENCE_DAYS = [
    {"day": 1, "date": "2026-01-05", "category": "acabou_de_acontecer", "title": "Copom mantem Selic", "source": "BCB", "topic": "política monetária"},
    {"day": 2, "date": "2026-01-12", "category": "em_andamento", "title": "IPCA acumula alta", "source": "IBGE", "topic": "inflação"},
    {"day": 3, "date": "2026-01-19", "category": "acabou_de_acontecer", "title": "Dólar fecha em queda", "source": "B3", "topic": "câmbio"},
    {"day": 4, "date": "2026-01-26", "category": "em_andamento", "title": "Empresas reportam resultados", "source": "CVM", "topic": "resultados corporativos"},
    {"day": 5, "date": "2026-02-02", "category": "acabou_de_acontecer", "title": "PIB cresce", "source": "IBGE", "topic": "atividade econômica"},
    {"day": 6, "date": "2026-02-09", "category": "em_andamento", "title": "Copom sinaliza cenário", "source": "BCB", "topic": "comunicado"},
    {"day": 7, "date": "2026-02-16", "category": "acabou_de_acontecer", "title": "Bolsa fecha em alta", "source": "B3", "topic": "mercado acionário"},
    {"day": 8, "date": "2026-02-23", "category": "em_andamento", "title": "Fiscal monitora metas", "source": "CVM", "topic": "fiscal"},
    {"day": 9, "date": "2026-03-02", "category": "acabou_de_acontecer", "title": "Desemprego recua", "source": "IBGE", "topic": "mercado de trabalho"},
    {"day": 10, "date": "2026-03-09", "category": "em_andamento", "title": "Atenção ao câmbio", "source": "BCB", "topic": "câmbio"},
    {"day": 11, "date": "2026-03-16", "category": "acabou_de_acontecer", "title": "Mercado acompanha Copom", "source": "Forbes", "topic": "manchete"},
    {"day": 12, "date": "2026-03-23", "category": "em_andamento", "title": "PIB e mercado", "source": "IBGE", "topic": "atividade"},
]


def main():
    for item in REFERENCE_DAYS:
        path = SEED_DIR / f"dia_{item['day']:02d}.json"
        path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
    (SEED_DIR / "README.md").write_text(
        "12 dias de referência (mínimo) para calibração e validação da suíte offline.\n",
        encoding="utf-8",
    )
    print(f"Seed initialized with {len(REFERENCE_DAYS)} reference days.")


if __name__ == "__main__":
    main()