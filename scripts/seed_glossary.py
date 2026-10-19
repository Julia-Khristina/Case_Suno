"""Popula config/glossario.yaml a partir do cache do glossário de Cidadania Financeira do BCB.

- Definições vindas da fonte autorizada entram com status "pendente": só passam a ser usadas
  (caixa "Entenda os termos", explicações) depois da aprovação da autora no painel do glossário.
- O jargão avançado citado na seção 4.6 da especificação entra como "sem_definicao" (autoria manual).
- O nível do termo serve à densidade de termos técnicos: "iniciante" = vocabulário cotidiano
  (não conta como jargão); "intermediario"/"avancado" = termos técnicos.
- Entradas já existentes no YAML (por exemplo, aprovadas ou editadas) são preservadas.

Uso: python scripts/seed_glossary.py
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "bcb_glossario.json"
TARGET = ROOT / "config" / "glossario.yaml"
BCB_URL = ("https://www.bcb.gov.br/content/cidadaniafinanceira/documentos_cidadania/"
           "Informacoes_gerais/glossario_cidadania_financeira.pdf")

# Vocabulário padrão de mercado (seção 4.6: "CDI, Selic, IPCA, dividendos")
INTERMEDIARIO = {
    "cdi", "cdb", "lca", "lci", "lcd", "rdb", "rdc", "ipca", "igp-m", "inpc", "incc", "selic", "taxa selic",
    "copom", "cmn", "debêntures", "dividendos", "tesouro direto", "título público", "fundo de investimento",
    "commodities", "liquidez", "rentabilidade", "rentabilidade bruta", "rentabilidade líquida", "bolsa de valores",
    "ações", "iof", "taxa referencial", "letra financeira", "letra de câmbio", "letra hipotecária",
    "perfil do investidor", "sfn", "amortização", "inadimplência", "cet", "custo efetivo total",
}

# Jargão pleno (seção 4.6) e jargão macroeconômico frequente em atas do Copom — sem definição autorizada
AVANCADO = [
    ("curva de juros", []), ("forward guidance", []), ("hiato do produto", []), ("ebitda ajustado", ["ebitda"]),
    ("covenants", ["covenant"]), ("política monetária contracionista", ["política monetária restritiva"]),
    ("expectativas ancoradas", ["ancoragem das expectativas", "expectativas desancoradas"]),
    ("balanço de riscos", []), ("juros reais", ["taxa de juros real"]), ("taxa neutra", ["juro neutro"]),
    ("prêmio de risco", []), ("demanda agregada", []), ("desinflação", []), ("banda de tolerância", []),
    ("núcleos de inflação", ["núcleo de inflação"]), ("aperto monetário", ["ciclo de aperto"]),
    ("afrouxamento monetário", []), ("risco fiscal", []), ("fluxo de capitais", []),
    ("inflação implícita", []), ("política fiscal", []), ("dívida pública", []), ("choques de oferta", ["choque de oferta"]),
]
INTERMEDIARIO_EXTRA = [("pib", ["produto interno bruto"]), ("boletim focus", ["focus"]), ("meta de inflação", []),
                       ("política monetária", []), ("taxa de câmbio", ["câmbio"]), ("federal reserve", ["fed"])]


def _split(name: str) -> tuple[str, list[str]]:
    name = name.replace("\xa0", " ").strip()
    base = re.sub(r"\s*\(.*?\)", "", name).strip()
    variations = [v.strip() for v in re.findall(r"\((.*?)\)", name)
                  if v and not v.lower().startswith(("no ", "em ", "ou ", "dinheiro"))]
    # "Internet banking (home banking, banco on-line)" -> várias variações
    out: list[str] = []
    for v in variations:
        out.extend(p.strip() for p in v.split(",") if p.strip())
    return base, out


def _first_sentences(text: str, max_chars: int = 320) -> str:
    text = re.split(r"\bExemplo de uso\b|\bVer também\b", text.replace("\xa0", " "))[0].strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out = ""
    for s in sentences:
        if len(out) + len(s) > max_chars and out:
            break
        out = f"{out} {s}".strip()
    return out


def build() -> dict:
    existing = yaml.safe_load(TARGET.read_text(encoding="utf-8")) if TARGET.exists() else {}
    kept = {str(t["termo"]).lower(): t for t in (existing or {}).get("termos") or [] if isinstance(t, dict)}
    raw = json.loads(CACHE.read_text(encoding="utf-8"))
    today = date.today().isoformat()
    entries: dict[str, dict] = {}
    used_forms: set[str] = set()

    def add(entry: dict) -> None:
        key = entry["termo"].lower()
        forms = [key, *[v.lower() for v in entry.get("variacoes", [])]]
        if key in entries or any(f in used_forms for f in forms):
            # variação já usada por outro termo: mantém só as formas livres
            entry["variacoes"] = [v for v in entry.get("variacoes", []) if v.lower() not in used_forms]
            if key in entries or key in used_forms:
                return
        used_forms.update(f.lower() for f in [entry["termo"], *entry["variacoes"]])
        entries[key] = entry

    for name, definition in raw.items():
        base, variations = _split(name)
        nivel = "intermediario" if base.lower() in INTERMEDIARIO else "iniciante"
        add({
            "termo": base, "variacoes": variations, "nivel": nivel,
            "explicacao_iniciante": _first_sentences(definition), "explicacao_impacto": None,
            "pronuncia": None, "fonte_definicao": "Glossário de Cidadania Financeira (BCB)", "url_fonte": BCB_URL,
            "data_consulta": today, "trecho_original": definition.replace("\xa0", " ")[:600], "status": "pendente",
        })
    for nivel, items in (("intermediario", INTERMEDIARIO_EXTRA), ("avancado", AVANCADO)):
        for term, variations in items:
            add({"termo": term, "variacoes": variations, "nivel": nivel, "explicacao_iniciante": None,
                 "explicacao_impacto": None, "pronuncia": None, "fonte_definicao": None, "url_fonte": None,
                 "data_consulta": None, "trecho_original": None, "status": "sem_definicao"})

    for key, entry in kept.items():  # preserva curadoria manual
        if entry.get("status") in {"aprovado", "autoria_manual"} or key not in entries:
            entries[key] = entry

    return {"versao": f"0.1.0-{today}", "termos": sorted(entries.values(), key=lambda e: e["termo"].lower())}


if __name__ == "__main__":
    data = build()
    header = ("# Glossário versionado (seção 4.5). Gerado por scripts/seed_glossary.py a partir do glossário\n"
              "# de Cidadania Financeira do BCB. Status 'pendente' = definição da fonte autorizada aguardando\n"
              "# aprovação da autora; só entradas 'aprovado'/'autoria_manual' são usadas nas explicações.\n")
    TARGET.write_text(header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"{len(data['termos'])} termos gravados em {TARGET}")
