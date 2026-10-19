"""Document extraction and anchoring (seções 4.3 e 4.4).

- Divide o documento por sentenças preservando offsets; extrai por parte.
- Ids únicos por parte quando há mais de uma (c2_a1...).
- Afirmação ou dado sem trecho exato localizável na fonte é descartado (não entra no grafo).
- Documentos com mais de uma parte passam por uma segunda passagem de agregação dos pontos centrais.
- Termos detectados por regra a partir do glossário, mais os sugeridos pelo modelo.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from src.evaluation.flesch_ptbr import flesch_reading_ease_pt
from src.evaluation.term_density import technical_density
from src.extraction.chunker import split_into_chunks
from src.extraction.entity_event import normalize_entities, normalize_events
from src.extraction.models import (
    Assertion,
    Entity,
    Event,
    ExtractionResult,
    MainPoint,
    NumericData,
    PendingTerm,
    SourceComplexity,
)
from src.extraction.typology import normalize_assertion_role, normalize_assertion_type
from src.glossary.authorized_sources import AuthorizedTermResolver
from src.glossary.pending_terms import find_pending_terms
from src.glossary.reader import Glossary, load_aliases, load_glossary
from src.shared.llm_client import InvalidLLMOutput, LLMClient

PROMPTS = Path(__file__).resolve().parent / "prompts"
PROMPT_SYSTEM = (PROMPTS / "system.txt").read_text(encoding="utf-8")
PROMPT_EXTRACT = (PROMPTS / "extract.txt").read_text(encoding="utf-8")
PROMPT_AGGREGATE = (PROMPTS / "aggregate.txt").read_text(encoding="utf-8")


class _ChunkExtraction(BaseModel):
    """Contrato da resposta por parte (mais tolerante que ExtractionResult nos campos auxiliares)."""
    main_points: list[MainPoint] = Field(default_factory=list)
    assertions: list[dict] = Field(default_factory=list)
    numeric_data: list[dict] = Field(default_factory=list)
    entities: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
    detected_terms: list[str] = Field(default_factory=list)


class _Aggregation(BaseModel):
    main_points: list[MainPoint]


_ID_TOKEN = re.compile(r"^[a-zA-Z]+_?\d+$")
LIST_FIELDS = ("main_points", "assertions", "numeric_data", "entities", "events")


def coerce_items(value: Any) -> tuple[list[dict], int]:
    """Normaliza listas mal formadas pelo modelo, sem inventar conteúdo.

    Aceita {"a1": {...}, "a2": {...}} (dicionário indexado por id) e listas com strings soltas intercaladas
    (["a2", ":", {...}]): o id solto vira o id do objeto seguinte; strings sem objeto são descartadas.
    Retorna (itens, quantidade de elementos descartados).
    """
    if isinstance(value, dict):
        if value and all(isinstance(v, dict) for v in value.values()):
            return [{**v, "id": v.get("id") or k} for k, v in value.items()], 0
        return [value], 0
    if not isinstance(value, list):
        return [], 1 if value not in (None, "") else 0
    items, dropped, pending_id = [], 0, None
    for element in value:
        if isinstance(element, dict):
            if pending_id and not element.get("id"):
                element = {**element, "id": pending_id}
            items.append(element)
            pending_id = None
        elif isinstance(element, str) and _ID_TOKEN.match(element.strip()):
            pending_id = element.strip()
        else:
            dropped += 0 if isinstance(element, str) and element.strip() in {":", ",", ""} else 1
    return items, dropped


def normalize_chunk_response(response: Any) -> tuple[dict, list[str]]:
    if not isinstance(response, dict):
        return {}, ["resposta da extração não é um objeto JSON"]
    data, warnings = dict(response), []
    for name in LIST_FIELDS:
        value = data.get(name)
        if not isinstance(value, (list, dict)):
            continue  # tipo errado continua inválido (aciona a nova tentativa), não vira lista vazia
        items, dropped = coerce_items(value)
        if value and not items:
            continue  # nada aproveitável: mantém o original para a validação reprovar
        data[name] = items
        if dropped:
            warnings.append(f"extração: {dropped} elemento(s) mal formado(s) descartado(s) em {name}")
    if "detected_terms" in data and not isinstance(data["detected_terms"], list):
        data["detected_terms"] = []
    data["detected_terms"] = [str(t) for t in data.get("detected_terms") or [] if isinstance(t, (str, int))]
    return data, warnings


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("“", '"').replace("”", '"').replace("’", "'")).strip()


def locate_span(source: str, span_text: str) -> tuple[int, int] | None:
    """Localiza o trecho na fonte tolerando apenas diferenças de espaço e aspas."""
    if not span_text or not span_text.strip():
        return None
    index = source.find(span_text)
    if index >= 0:
        return index, index + len(span_text)
    pattern = r"\s+".join(re.escape(part) for part in _norm_ws(span_text).split(" "))
    match = re.search(pattern, source) or re.search(pattern, source, flags=re.IGNORECASE)
    return match.span() if match else None


class Extractor:
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        glossary_terms: list[str] | None = None,
        aliases: dict[str, list[str]] | None = None,
        term_resolver: AuthorizedTermResolver | None = None,
        model_id: str | None = None,
        glossary_path: str = "config/glossario.yaml",
        aliases_path: str = "config/apelidos.yaml",
        glossary: Glossary | None = None,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.glossary = glossary or load_glossary(glossary_path)
        self.glossary_terms = glossary_terms if glossary_terms is not None else self.glossary.all_forms()
        self.aliases = aliases if aliases is not None else load_aliases(aliases_path)
        self._term_resolver = term_resolver
        self.model_id = model_id
        self.prompt_version = "extract-4"
        self.calls: list[Any] = []

    @property
    def term_resolver(self) -> AuthorizedTermResolver:
        if self._term_resolver is None:
            self._term_resolver = AuthorizedTermResolver(fetch_b3=False)
        return self._term_resolver

    # ----------------------------------------------------------------------------------- LLM
    def _call(self, prompt: str, schema: type[BaseModel], schema_name: str, cache_parts: dict,
              warnings: list[str] | None = None) -> dict:
        """Chama o modelo e valida; uma saída inválida ganha UMA nova tentativa com o erro como feedback."""
        attempt_prompt, last_error = prompt, None
        for attempt in (1, 2):
            try:
                result = self.llm_client.generate(attempt_prompt, system=PROMPT_SYSTEM, schema_name=schema_name,
                                                  model_id=self.model_id, role="extraction",
                                                  cache_parts={**cache_parts, "prompt_version": self.prompt_version,
                                                               "tentativa": attempt})
                self.calls.append(result)
                data, notes = normalize_chunk_response(result.response) if schema is _ChunkExtraction \
                    else (result.response, [])
                schema.model_validate(data)
                if warnings is not None:
                    warnings.extend(notes)
                return data
            except (InvalidLLMOutput, ValidationError) as exc:
                last_error = exc
                attempt_prompt = (f"{prompt}\n\nA resposta anterior foi inválida: {str(exc)[:600]}\n"
                                  "Responda de novo com UM objeto JSON exatamente no formato pedido: listas de objetos, "
                                  "sem chaves soltas dentro das listas.")
        raise InvalidLLMOutput(f"Extração fora do contrato após 2 tentativas: {last_error}") from last_error

    # ------------------------------------------------------------------------------- extract
    def extract(self, text: str, document_hash: str | None = None, persistence_conn=None,
                source_metadata: dict[str, Any] | None = None) -> ExtractionResult:
        chunks = split_into_chunks(text)
        multi = len(chunks) > 1
        warnings: list[str] = []
        candidates: list[MainPoint] = []
        assertions: list[Assertion] = []
        numeric: list[NumericData] = []
        entities: list[dict] = []
        events: list[dict] = []
        detected: list[str] = []

        for index, chunk in enumerate(chunks, start=1):
            prefix = f"c{index}_" if multi else ""
            prompt = PROMPT_EXTRACT.format(chunk_text=chunk.text, glossary_terms=", ".join(self.glossary_terms[:400]),
                                           aliases=self.aliases)
            parsed = _ChunkExtraction.model_validate(
                self._call(prompt, _ChunkExtraction, "extraction", {"chunk_start": chunk.start}, warnings))
            kept_ids: set[str] = set()
            for raw in parsed.assertions:
                span_text = ((raw.get("source_span") or {}).get("text") or "").strip()
                location = locate_span(text, span_text)
                if location is None:
                    warnings.append(f"afirmação descartada sem trecho exato na fonte: {raw.get('text', '')[:80]}")
                    continue
                aid = prefix + str(raw.get("id"))
                kept_ids.add(aid)
                assertions.append(Assertion(
                    id=aid, text=str(raw.get("text", "")), type=normalize_assertion_type(str(raw.get("type", "fato"))),
                    role=normalize_assertion_role(str(raw.get("role", "nenhum"))),
                    source_span={"text": text[location[0]:location[1]], "start": location[0], "end": location[1]},
                    variation_declared=bool(raw.get("variation_declared", False)),
                ))
            for raw in parsed.numeric_data:
                span_text = ((raw.get("source_span") or {}).get("text") or "").strip()
                location = locate_span(text, span_text)
                if location is None:
                    warnings.append(f"dado numérico descartado sem trecho exato: {raw.get('indicator', '')}")
                    continue
                numeric.append(NumericData(
                    id=prefix + str(raw.get("id")), indicator=str(raw.get("indicator", "")), value=str(raw.get("value", "")),
                    unit=raw.get("unit"), reference_period=raw.get("reference_period"),
                    source_span={"text": text[location[0]:location[1]], "start": location[0], "end": location[1]},
                ))
            for point in parsed.main_points:
                ids = [prefix + a for a in point.assertion_ids if prefix + a in kept_ids]
                if point.assertion_ids and not ids:
                    warnings.append(f"ponto central sem afirmação ancorada: {point.title}")
                candidates.append(point.model_copy(update={"id": prefix + point.id, "assertion_ids": ids}))
            entities += parsed.entities
            events += parsed.events
            detected += parsed.detected_terms

        main_points = self._aggregate(candidates, assertions, multi, warnings)

        glossary_hits = sorted({e.termo for e, _f, _p in self.glossary.find_in_text(text)})
        detected_terms = sorted(set(detected) | set(glossary_hits))
        pending_terms = []
        for term in find_pending_terms(sorted(set(detected)), self.glossary_terms):
            resolution = self.term_resolver.resolve(term)
            pending_terms.append(PendingTerm(term=term, proposed_definition=resolution.definition, source=resolution.source,
                                             source_url=resolution.source_url,
                                             status="pendente" if resolution.found else "sem_definicao"))

        result = ExtractionResult(
            main_points=main_points,
            assertions=assertions,
            numeric_data=numeric,
            entities=[_entity_from_dict(e) for e in normalize_entities(entities, self.aliases)],
            events=[_event_from_dict(e) for e in normalize_events(events, self.aliases)],
            detected_terms=detected_terms,
            pending_terms=pending_terms,
            source_complexity=SourceComplexity(word_count=len(text.split()), flesch=round(flesch_reading_ease_pt(text), 2),
                                               term_density=round(technical_density(text, self.glossary), 3)),
            warnings=warnings,
        )
        if persistence_conn is not None and document_hash:
            persist_extraction(persistence_conn, document_hash, text, result, chunks, source_metadata or {})
        return result

    def _aggregate(self, candidates: list[MainPoint], assertions: list[Assertion], multi: bool,
                   warnings: list[str]) -> list[MainPoint]:
        ordered = sorted(candidates, key=lambda p: (p.order, p.id))
        if not multi or len(candidates) <= 3:
            return [p.model_copy(update={"order": i}) for i, p in enumerate(ordered[:3], start=1)]
        by_id = {a.id: a for a in assertions}
        lines = []
        for p in candidates:
            texts = "; ".join(f"{aid}: {by_id[aid].text}" for aid in p.assertion_ids if aid in by_id)
            lines.append(f"- {p.id} (ordem na parte {p.order}): {p.title} | {texts or 'sem afirmações'}")
        try:
            response = self._call(PROMPT_AGGREGATE.format(candidates="\n".join(lines)), _Aggregation, "extraction_aggregate",
                                  {"n_candidates": len(candidates)})
            points = _Aggregation.model_validate(response).main_points
        except InvalidLLMOutput as exc:
            warnings.append(f"agregação inválida, usando ordem das partes: {exc}")
            return [p.model_copy(update={"order": i}) for i, p in enumerate(ordered[:3], start=1)]
        final = []
        for i, point in enumerate(sorted(points, key=lambda p: p.order)[:3], start=1):
            ids = [a for a in point.assertion_ids if a in by_id]
            final.append(point.model_copy(update={"id": f"p{i}", "order": i, "assertion_ids": ids}))
        return final


def _entity_from_dict(data: dict) -> Entity:
    return Entity(id=str(data.get("id") or data.get("name") or "entity"), name=data.get("name", ""),
                  canonical_name=data.get("canonical_name") or data.get("name", ""), type=data.get("type") or "instituicao")


def _event_from_dict(data: dict) -> Event:
    return Event(id=str(data.get("id") or data.get("name") or "event"), name=data.get("name", ""),
                 canonical_name=data.get("canonical_name") or data.get("name", ""),
                 reference_date=data.get("reference_date"), type=data.get("type") or "evento")


def persist_extraction(conn, document_hash: str, text: str, result: ExtractionResult, chunks,
                       source_metadata: dict[str, Any]) -> dict[str, str]:
    """Grava documento, trechos, pontos, afirmações, dados, entidades e eventos no grafo (PostgreSQL).

    Retorna o mapa id da afirmação -> id do nó, usado para ligar as frases geradas (BASEADA_EM).
    """
    from src.persistence.repositories.document_repository import DocumentRepository
    from src.persistence.repositories.graph_repository import GraphRepository

    graph = GraphRepository(conn)
    docs = DocumentRepository(conn)
    if docs.get(document_hash) is None:
        docs.create(document_hash, "texto", quantidade_palavras=len(text.split()), status_integridade="admitido")

    document_node = graph.add_node("documento", {"hash": document_hash, **source_metadata})
    chunk_nodes: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        chunk_id = graph.add_node("trecho", {"ordem": index, "texto": chunk.text, "inicio": chunk.start, "fim": chunk.end})
        graph.add_edge(document_node, chunk_id, "TEM_TRECHO")
        chunk_nodes.append(chunk_id)

    point_nodes = {p.id: graph.add_node("ponto_central", {"id": p.id, "ordem": p.order, "titulo": p.title,
                                                          "justificativa": p.justification}) for p in result.main_points}
    for point_node in point_nodes.values():  # ponto sem afirmação ligada ficava solto no grafo
        graph.add_edge(document_node, point_node, "TRATA_DE")
    assertion_nodes: dict[str, str] = {}
    for assertion in result.assertions:
        node = graph.add_node("afirmacao", {"id": assertion.id, "texto": assertion.text, "tipo": assertion.type,
                                            "papel": assertion.role, "variacao_declarada": assertion.variation_declared,
                                            "trecho": assertion.source_span.text, "inicio": assertion.source_span.start})
        assertion_nodes[assertion.id] = node
        target = _find_chunk(assertion.source_span, chunk_nodes, chunks)
        if target is not None:
            graph.add_edge(node, target, "EXTRAIDA_DE")
    for point in result.main_points:
        for aid in point.assertion_ids:
            if aid in assertion_nodes:
                graph.add_edge(assertion_nodes[aid], point_nodes[point.id], "SUSTENTA")
    for number in result.numeric_data:
        node = graph.add_node("dado", {"id": number.id, "indicador": number.indicator, "valor": number.value,
                                       "unidade": number.unit, "periodo": number.reference_period})
        target = _find_chunk(number.source_span, chunk_nodes, chunks)
        if target is not None:
            graph.add_edge(node, target, "EXTRAIDO_DE")
    for entity in result.entities:
        node = graph.add_node("entidade", {"id": entity.id, "nome": entity.name, "nome_canonico": entity.canonical_name,
                                           "tipo": entity.type})
        graph.add_edge(document_node, node, "MENCIONA")  # sem a aresta, a entidade ficava solta no grafo
    for event in result.events:
        node = graph.add_node("evento", {"id": event.id, "nome": event.name, "nome_canonico": event.canonical_name,
                                         "data_referencia": event.reference_date, "tipo": event.type})
        graph.add_edge(document_node, node, "TRATA_DE")
    return assertion_nodes


def _find_chunk(span, chunk_nodes: list[str], chunks) -> str | None:
    if not chunk_nodes or span.start is None:
        return None
    for index, chunk in enumerate(chunks):
        if chunk.start <= span.start < chunk.end:
            return chunk_nodes[index]
    return chunk_nodes[-1]
