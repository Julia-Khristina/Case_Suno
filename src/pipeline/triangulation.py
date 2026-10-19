"""Etapas da triangulação dentro do pipeline (decisão de 17/10/2026).

Com 2+ fontes independentes, o texto analítico do 3×3 vira triangulado: cada fonte passa por admissão e extração,
o alinhador monta a matriz, o sistema escolhe os 3 pontos centrais e gera os gráficos. Carrossel e roteiro usam os
mesmos 3 pontos por meio de uma extração combinada (afirmações com o nome da fonte).
Com menos de 2 fontes independentes, o pipeline segue como fonte única, com aviso.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.admission.service import admit_text
from src.extraction.extractor import Extractor
from src.extraction.models import Assertion, ExtractionResult, MainPoint, NumericData, SourceComplexity
from src.glossary.reader import load_aliases
from src.triangulacao.alinhamento import align_sources, rank_rows
from src.triangulacao.dossie import Dossie, build_dossie
from src.triangulacao.graficos_matriz import charts_for_matrix, charts_for_single_source
from src.triangulacao.models import LinhaMatriz

CHARTS_DIR = Path("data/exports/graficos")
MAX_CHARTS = 4  # o máximo entre os níveis; cada nível usa os primeiros N (config/triangulacao.yaml)


def admit_sources(fontes: list[dict], deps) -> tuple[Dossie | None, list[str], list[dict]]:
    """Admite cada fonte; descarta as bloqueadas. Retorna (dossiê ou None se < 2 independentes, avisos, admitidas)."""
    warnings, admitted = [], []
    for raw in fontes:
        content = (raw.get("conteudo") or "").strip()
        result = admit_text(content, glossary_terms=deps.glossary.all_forms())
        if result.status == "bloqueado":
            warnings.append(f"Fonte '{raw.get('nome')}' descartada na admissão: {', '.join(result.partial_reasons)}")
            continue
        if result.status == "aviso":
            warnings.append(f"Fonte '{raw.get('nome')}' admitida com aviso (pode não ser financeira).")
        admitted.append(raw)
    if len(admitted) < 2:
        warnings.append("Menos de 2 fontes admitidas: sem triangulação, o material usa uma única fonte.")
        return None, warnings, admitted
    dossie = build_dossie(admitted)
    if dossie.aviso:
        warnings.append(dossie.aviso)
        return None, warnings, admitted
    return dossie, warnings, admitted


def combined_origin(dossie: Dossie) -> dict:
    return {"fontes": [{"nome": f.nome, "titulo": f.titulo, "data": f.data, "url": f.url} for f in dossie.fontes],
            "instituicao": "; ".join(f.nome for f in dossie.fontes), "titulo": dossie.fontes[0].titulo}


def extract_and_align(dossie: Dossie, deps) -> tuple[dict, ExtractionResult, list[str], list]:
    """Extrai cada fonte, alinha, escolhe os pontos centrais e gera os gráficos.

    Retorna (estado da triangulação, extração combinada, avisos, chamadas de extração).
    """
    warnings: list[str] = []
    calls: list = []
    for fonte in dossie.fontes:
        extractor = Extractor(llm_client=deps.llm_client, glossary=deps.glossary, aliases=load_aliases(),
                              term_resolver=deps.term_resolver)
        result = extractor.extract(fonte.conteudo)
        calls += extractor.calls
        fonte.extraction = result.model_dump(mode="json")
        warnings += [f"{fonte.nome}: {w}" for w in result.warnings]
    alignment = align_sources(dossie, deps.llm_client)
    warnings += alignment.avisos
    if not alignment.linhas:
        raise ValueError("O alinhador não encontrou nenhum ponto em comum entre as fontes.")
    top = rank_rows(alignment.linhas)
    sources = [f.model_dump(exclude={"extraction", "conteudo"}) for f in dossie.fontes]
    charts = charts_for_matrix(alignment.linhas, sources, CHARTS_DIR / dossie.hash[:16], MAX_CHARTS)
    state = {
        "assunto": alignment.assunto,
        "fontes": sources,
        "grupos_origem": dossie.grupos_origem,
        "independentes": dossie.independentes,
        "matriz": [row.model_dump(mode="json") for row in alignment.linhas],
        "pontos_centrais": [row.linha_id for row in top],
        "graficos": charts,
        "extracoes": {f.id: f.extraction for f in dossie.fontes},
    }
    return state, merged_extraction(dossie, alignment.linhas, top), warnings, calls


def merged_extraction(dossie: Dossie, rows: list[LinhaMatriz], top: list[LinhaMatriz]) -> ExtractionResult:
    """Extração combinada: afirmações e números de todas as fontes (ids 'f1:a3', texto com a fonte) e os 3 pontos
    centrais da matriz. Alimenta carrossel, roteiro, métricas e rastreabilidade."""
    assertions, numbers, entities, events, terms = [], [], [], [], set()
    for fonte in dossie.fontes:
        extraction = ExtractionResult.model_validate(fonte.extraction or {})
        for a in extraction.assertions:
            assertions.append(Assertion(id=f"{fonte.id}:{a.id}", text=f"Segundo {fonte.nome}, {a.text[0].lower()}{a.text[1:]}",
                                        type=a.type, role=a.role, source_span=a.source_span,
                                        variation_declared=a.variation_declared))
        for n in extraction.numeric_data:
            numbers.append(NumericData(id=f"{fonte.id}:{n.id}", indicator=f"{n.indicator} ({fonte.nome})", value=n.value,
                                       unit=n.unit, reference_period=n.reference_period, source_span=n.source_span))
        entities += extraction.entities
        events += extraction.events
        terms.update(extraction.detected_terms)
    known = {a.id for a in assertions}
    points = []
    for order, row in enumerate(top, start=1):
        ids = []
        for cell in row.celulas:
            ids += [a.id for a in assertions if a.id.startswith(f"{cell.fonte_id}:") and cell.trecho
                    and (a.source_span.text in cell.trecho or cell.trecho in a.source_span.text)]
        points.append(MainPoint(id=row.linha_id, order=order, title=row.topico,
                                assertion_ids=[i for i in dict.fromkeys(ids) if i in known],
                                justification=row.justificativa_status))
    words = sum(len(f.conteudo.split()) for f in dossie.fontes)
    return ExtractionResult(main_points=points, assertions=assertions, numeric_data=numbers, entities=entities,
                            events=events, detected_terms=sorted(terms), source_complexity=SourceComplexity(word_count=words))


def single_source_charts(extraction: dict, document_hash: str) -> list[dict]:
    return charts_for_single_source(extraction, CHARTS_DIR / (document_hash or "documento")[:16])


def matrix_points_for_eval(triangulacao: dict) -> list[dict]:
    """Pontos centrais para a cobertura: título da linha + o que cada fonte diz nela."""
    rows = {r["linha_id"]: r for r in triangulacao.get("matriz", [])}
    points = []
    for row_id in triangulacao.get("pontos_centrais", []):
        row = rows.get(row_id) or {}
        points.append({"id": row_id, "title": row.get("topico", ""),
                       "assertions": [c.get("valor_texto") or "" for c in row.get("celulas", [])]})
    return points


def source_names_by_id(triangulacao: dict) -> dict[str, str]:
    return {f["id"]: f["nome"] for f in triangulacao.get("fontes", [])}


def triangulation_context(triangulacao: dict | None) -> dict[str, Any] | None:
    if not triangulacao:
        return None
    return {"matriz": triangulacao.get("matriz", []), "fontes": triangulacao.get("fontes", []),
            "pontos_centrais": triangulacao.get("pontos_centrais", [])}
