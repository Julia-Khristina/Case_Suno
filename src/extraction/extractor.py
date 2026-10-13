"""Document extraction and anchoring."""
import json
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import ValidationError

from src.shared.llm_client import LLMClient
from src.extraction.chunker import split_into_chunks
from src.extraction.entity_event import normalize_entities, normalize_events
from src.extraction.models import (
    Assertion,
    Event,
    ExtractionResult,
    MainPoint,
    NumericData,
    PendingTerm,
    SourceComplexity,
    SourceSpan,
)
from src.extraction.typology import normalize_assertion_role, normalize_assertion_type
from src.glossary.authorized_sources import AuthorizedTermResolver
from src.glossary.pending_terms import find_pending_terms
from src.glossary.reader import load_aliases, load_glossary_terms
from src.persistence.repositories.document_repository import DocumentRepository
from src.persistence.repositories.graph_repository import GraphRepository


PROMPT_SYSTEM = (Path(__file__).resolve().parent / "prompts" / "system.txt").read_text(encoding="utf-8")
PROMPT_EXTRACT = (Path(__file__).resolve().parent / "prompts" / "extract.txt").read_text(encoding="utf-8")


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
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.glossary_terms = glossary_terms if glossary_terms is not None else load_glossary_terms(glossary_path)
        self.aliases = aliases if aliases is not None else load_aliases(aliases_path)
        self.term_resolver = term_resolver or AuthorizedTermResolver()
        self.model_id = model_id
        self.cache_parts = {"glossary_version": "configured", "prompt_version": "block3"}

    def extract(
        self,
        text: str,
        document_hash: str | None = None,
        persistence_conn=None,
        source_metadata: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        chunks = split_into_chunks(text)
        all_main_points: list[MainPoint] = []
        all_assertions: list[Assertion] = []
        all_numeric: list[NumericData] = []
        all_entities: list[dict[str, Any]] = []
        all_events: list[dict[str, Any]] = []
        detected_terms: list[str] = []

        for chunk in chunks:
            prompt = PROMPT_SYSTEM + "\n\n" + PROMPT_EXTRACT.format(
                chunk_text=chunk.text,
                glossary_terms=", ".join(self.glossary_terms),
                aliases=self.aliases,
            )
            response = self.llm_client.generate(
                prompt,
                schema_name="extraction",
                model_id=self.model_id,
                cache_parts={"chunk_start": chunk.start, **self.cache_parts},
            )
            parsed = ExtractionResult.model_validate(response)
            all_main_points.extend(parsed.main_points)
            all_assertions.extend(parsed.assertions)
            all_numeric.extend(parsed.numeric_data)
            all_entities.extend([entity.model_dump() for entity in parsed.entities])
            all_events.extend([event.model_dump() for event in parsed.events])
            detected_terms.extend(parsed.detected_terms)

        main_points = sorted(all_main_points, key=lambda item: (item.order, item.id))[:3]
        assertions = [
            Assertion(
                id=item.id,
                text=item.text,
                type=normalize_assertion_type(item.type),
                role=normalize_assertion_role(item.role),
                source_span=item.source_span,
                variation_declared=item.variation_declared,
            )
            for item in all_assertions
        ]
        assertions = _enrich_spans(text, assertions, "assertion")
        numeric_data = _enrich_spans(text, all_numeric, "numeric")
        entities = normalize_entities(all_entities, self.aliases)
        events = normalize_events(all_events, self.aliases)

        pending_terms = []
        for term in find_pending_terms(detected_terms, self.glossary_terms):
            resolution = self.term_resolver.resolve(term)
            pending_terms.append(
                PendingTerm(
                    term=term,
                    proposed_definition=resolution.definition,
                    source=resolution.source,
                    source_url=resolution.source_url,
                    status="pendente" if resolution.found else "sem_definicao",
                )
            )

        source_complexity = SourceComplexity(
            word_count=len(text.split()),
        )

        result = ExtractionResult(
            main_points=main_points,
            assertions=assertions,
            numeric_data=numeric_data,
            entities=[_entity_from_dict(item) for item in entities],
            events=[_event_from_dict(item) for item in events],
            detected_terms=sorted(set(detected_terms)),
            pending_terms=pending_terms,
            source_complexity=source_complexity,
        )

        if persistence_conn is not None and document_hash:
            persist_extraction(persistence_conn, document_hash, text, result, chunks, source_metadata or {})

        return result


def _enrich_spans(text: str, items: list, kind: str) -> list:
    for item in items:
        span = item.source_span
        if span.start is None and span.text:
            index = text.find(span.text)
            if index >= 0:
                span.start = index
                span.end = index + len(span.text)
    return items


def _entity_from_dict(data: dict) -> Any:
    from src.extraction.models import Entity

    return Entity(
        id=data.get("id", data.get("name", "entity")),
        name=data.get("name", ""),
        canonical_name=data.get("canonical_name", data.get("name", "")),
        type=data.get("type", "instituicao"),
    )


def _event_from_dict(data: dict) -> Any:
    from src.extraction.models import Event

    return Event(
        id=data.get("id", data.get("name", "event")),
        name=data.get("name", ""),
        canonical_name=data.get("canonical_name", data.get("name", "")),
        reference_date=data.get("reference_date"),
        type=data.get("type", "evento"),
    )


def persist_extraction(conn, document_hash: str, text: str, result: ExtractionResult, chunks, source_metadata: dict[str, Any]) -> None:
    from src.extraction.models import NumericData

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

    main_point_nodes = {}
    for point in result.main_points:
        node_id = graph.add_node("ponto_central", {"id": point.id, "ordem": point.order, "titulo": point.title})
        main_point_nodes[point.id] = node_id

    for assertion in result.assertions:
        location = assertion.source_span
        target_chunk = _find_chunk(location, chunk_nodes, chunks)
        assertion_node = graph.add_node("afirmacao", {"id": assertion.id, "texto": assertion.text, "tipo": assertion.type, "papel": assertion.role, "variacao_declarada": assertion.variation_declared})
        if target_chunk is not None:
            graph.add_edge(assertion_node, target_chunk, "EXTRAIDA_DE")
        # Main point association is computed outside extraction in v0; no assertion-to-point edge is inferred here.

    for number in result.numeric_data:
        location = number.source_span
        target_chunk = _find_chunk(location, chunk_nodes, chunks)
        numeric_node = graph.add_node("dado", {"id": number.id, "indicador": number.indicator, "valor": number.value, "unidade": number.unit, "periodo": number.reference_period})
        if target_chunk is not None:
            graph.add_edge(numeric_node, target_chunk, "EXTRAIDO_DE")

    for entity in result.entities:
        entity_node = graph.add_node("entidade", {"id": entity.id, "nome": entity.name, "nome_canonico": entity.canonical_name, "tipo": entity.type})
    for event in result.events:
        event_node = graph.add_node("evento", {"id": event.id, "nome": event.name, "nome_canonico": event.canonical_name, "data_referencia": event.reference_date, "tipo": event.type})
        graph.add_edge(document_node, event_node, "TRATA_DE")


def _find_chunk(span, chunk_nodes: list[str], chunks) -> str | None:
    if not chunk_nodes:
        return None
    if span.start is None:
        return chunk_nodes[0]
    for index, chunk in enumerate(chunks):
        if chunk.start <= span.start < chunk.end:
            return chunk_nodes[index]
    return chunk_nodes[-1]