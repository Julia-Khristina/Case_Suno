import uuid
from unittest.mock import patch

import psycopg

from src.extraction.extractor import Extractor
from tests.fakes.llm import FakeLLMClient
from src.persistence.database import get_database_url
from src.persistence.repositories.document_repository import DocumentRepository
from tests.integration.graph_cleanup import delete_component

CANNED_RESPONSE = {
    "main_points": [{"id": "mp1", "order": 1, "title": "Ponto central", "assertion_ids": []}],
    "assertions": [
        {
            "id": "a1",
            "text": "A taxa Selic subiu.",
            "type": "fato",
            "role": "impacto",
            "source_span": {"text": "A taxa Selic subiu.", "start": None, "end": None},
            "variation_declared": True,
        }
    ],
    "numeric_data": [
        {
            "id": "n1",
            "indicator": "Selic",
            "value": "10,50",
            "unit": "%",
            "reference_period": "outubro/2026",
            "source_span": {"text": "10,50%", "start": None, "end": None},
        }
    ],
    "entities": [{"id": "e1", "name": "BC", "canonical_name": "Banco Central"}],
    "events": [{"id": "ev1", "name": "Copom", "canonical_name": "Copom", "reference_date": "2026-10-13"}],
    "detected_terms": ["selic"],
    "pending_terms": [],
    "source_complexity": {"word_count": 12},
}


def test_extraction_persists_document_and_graph_nodes():
    document_hash = f"doc-{uuid.uuid4()}"
    text = "A taxa Selic subiu. A Selic está em 10,50% hoje."
    conn = psycopg.connect(get_database_url(), connect_timeout=5)
    try:
        extractor = Extractor(llm_client=FakeLLMClient(responses={"extraction": [CANNED_RESPONSE]}), glossary_terms=[])
        result = extractor.extract(text, document_hash=document_hash, persistence_conn=conn)

        assert len(result.assertions) == 1
        document = DocumentRepository(conn).get(document_hash)
        assert document is not None

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM nos_grafo WHERE propriedades->>'hash' = %s", (document_hash,))
            document_nodes = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM nos_grafo WHERE tipo_no = 'afirmacao'")
            assertion_nodes = cur.fetchone()[0]
        assert document_nodes == 1
        assert assertion_nodes >= 1
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("SELECT id_no, criado_em FROM nos_grafo WHERE propriedades->>'hash' = %s", (document_hash,))
            rows = cur.fetchall()
        # o documento e tudo o que a extração ligou a ele (trechos, afirmações, pontos, dados, entidades, eventos)
        delete_component(conn, [r[0] for r in rows], since=min((r[1] for r in rows), default=None))
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documentos WHERE hash = %s", (document_hash,))
        conn.commit()
        conn.close()