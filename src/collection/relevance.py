"""Seleção dos cards do dia: cunho financeiro e geração possível (decisão de 17/10/2026).

Regras determinísticas, antes de qualquer LLM (seção 4.1):
1. Tema financeiro: título ou descrição com pelo menos um termo financeiro (lista de config/coleta_fontes.yaml
   ou termo técnico do glossário) e nenhum termo de exclusão no título. Não é filtro de jargão: notícias pouco
   técnicas continuam entrando se o tema for economia, mercado, empresas ou finanças pessoais.
2. Gerável: o texto completo do feed passa na MESMA admissão usada na geração (seção 4.3: não parcial,
   português, pelo menos 5 termos distintos do glossário e 200 palavras). Card que daria "aviso" não entra.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = "config/coleta_fontes.yaml"


@lru_cache(maxsize=2)
def load_selection_config(path: str = CONFIG_PATH) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8-sig")) or {}
    selection = data.get("selecao") or {}
    return {
        "exigir_tema_financeiro": bool(selection.get("exigir_tema_financeiro", True)),
        "exigir_texto_completo": bool(selection.get("exigir_texto_completo", True)),
        "max_por_fonte": int(selection.get("max_por_fonte", 3)),
        "tema_financeiro": tuple(str(t).lower() for t in data.get("tema_financeiro") or []),
        "excluir_titulo": tuple(str(t).lower() for t in data.get("excluir_titulo") or []),
    }


def _field(item: Any, name: str):
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


def _found(text: str, terms) -> list[str]:
    low = (text or "").lower()
    # aceita o plural regular ("dívida" acha "dívidas"; "ação" não vira "ações", que já está na lista)
    return [t for t in terms if t and re.search(rf"(?<!\w){re.escape(t)}(?:s|es)?(?!\w)", low)]


@dataclass
class Selection:
    financeiro: bool
    geravel: bool
    termos_tema: list[str] = field(default_factory=list)
    motivo_exclusao: str | None = None
    admissao: dict | None = None
    palavras: int = 0
    termos_glossario: int = 0

    @property
    def aceito(self) -> bool:
        return self.motivo_exclusao is None


def topic_check(item: Any, glossary=None, config: dict | None = None) -> tuple[bool, list[str], list[str]]:
    """(tema financeiro?, termos de tema achados, termos de exclusão no título) — sem ler o texto completo."""
    from src.glossary.reader import load_glossary

    config = config or load_selection_config()
    glossary = glossary or load_glossary()
    title = str(_field(item, "titulo") or "")
    headline = f"{title} {_field(item, 'descricao') or ''}"
    excluded = _found(title, config["excluir_titulo"])
    topic_terms = sorted(set(_found(headline, config["tema_financeiro"]) +
                             [form for _e, form, _p in glossary.find_in_text(headline, technical_only=True)]))
    return bool(topic_terms) and not excluded, topic_terms, excluded


def evaluate_item(item: Any, glossary=None, config: dict | None = None) -> Selection:
    from src.admission.service import admit_text
    from src.glossary.reader import load_glossary

    config = config or load_selection_config()
    glossary = glossary or load_glossary()
    financial, topic_terms, excluded = topic_check(item, glossary, config)

    content = _field(item, "conteudo") or ""
    admission = None
    generable = False
    words = len(content.split())
    distinct = 0
    if content:
        result = admit_text(content, glossary_terms=glossary.all_forms())
        admission = result.model_dump(mode="json")
        distinct = result.distinct_glossary_terms
        generable = result.status == "admitido"

    reason = None
    if config["exigir_tema_financeiro"] and excluded:
        reason = f"tema fora do escopo no título ({', '.join(excluded)})"
    elif config["exigir_tema_financeiro"] and not financial:
        reason = "sem termo financeiro no título ou na descrição"
    elif config["exigir_texto_completo"] and not content:
        reason = "feed sem texto completo (não daria para gerar sem abrir a página)"
    elif config["exigir_texto_completo"] and not generable:
        status = (admission or {}).get("status")
        detail = ", ".join((admission or {}).get("partial_reasons") or []) or (
            f"{distinct} termos do glossário e {words} palavras" if status == "aviso" else status)
        reason = f"texto não passa na admissão ({detail})"
    return Selection(financeiro=financial, geravel=generable, termos_tema=topic_terms, motivo_exclusao=reason,
                     admissao=admission, palavras=words, termos_glossario=distinct)


def entry_reason(item: Any, selection: Selection) -> str:
    source = _field(item, "nome_fonte") or "fonte"
    terms = ", ".join(selection.termos_tema[:4])
    text = f"{source}: tema financeiro ({terms})" if terms else f"{source}"
    if selection.geravel:
        text += f"; texto completo admitido ({selection.palavras} palavras, {selection.termos_glossario} termos do glossário)"
    return text


def select_items(items: list[Any], glossary=None, config: dict | None = None) -> tuple[list[tuple[Any, Selection]], list[dict]]:
    """Separa os itens aceitos dos descartados (com motivo), sem ranquear."""
    accepted, discarded = [], []
    for item in items:
        selection = evaluate_item(item, glossary, config)
        if selection.aceito:
            accepted.append((item, selection))
        else:
            discarded.append({"titulo": _field(item, "titulo"), "fonte": _field(item, "nome_fonte"),
                              "motivo": selection.motivo_exclusao})
    return accepted, discarded
