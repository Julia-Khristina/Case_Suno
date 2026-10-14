import uuid

import psycopg

from src.persistence.database import get_database_url
from src.collection.scheduler import run_collection


def test_manual_collection_persists_cards():
    conn = psycopg.connect(get_database_url(), connect_timeout=5)
    created_cards = []
    try:
        def fetcher():
            return [
                {
                    "titulo": "IPCA sobe em setembro",
                    "nome_fonte": "BCB",
                    "tipo_fonte": "primaria",
                    "url": "https://example.test/ipca",
                    "descricao": "Inflacao medida pelo IPCA",
                    "data_publicacao": "2026-10-13",
                }
            ]

        result = run_collection(conn=conn, fetcher=fetcher, limit=1)
        assert len(result["cards"]) == 1
        assert len(result["errors"]) == 0

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM cards WHERE url_fonte = %s", ("https://example.test/ipca",))
            assert cur.fetchone()[0] == 1
            cur.execute("SELECT COUNT(*) FROM coletas")
            before = cur.fetchone()[0]
        assert before >= 1
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cards WHERE url_fonte = %s", ("https://example.test/ipca",))
            cur.execute("DELETE FROM coletas WHERE nome_fonte = %s", ("coleta_diaria",))
        conn.commit()
        conn.close()