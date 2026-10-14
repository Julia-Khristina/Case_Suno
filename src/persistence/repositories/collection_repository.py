"""Collection run repository."""

import uuid
from datetime import UTC, datetime

class CollectionRepository:
    def __init__(self, conn):
        self.conn = conn

    def create(self, source_name: str, items_count: int = 0, errors: list[str] | None = None, started_at=None, finished_at=None) -> str:
        collection_id = str(uuid.uuid4())
        errors = errors or []
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO coletas (id_coleta, nome_fonte, iniciado_em, finalizado_em, quantidade_itens, erros)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id_coleta
                """,
                (
                    collection_id,
                    source_name,
                    started_at or datetime.now(UTC),
                    finished_at or datetime.now(UTC),
                    items_count,
                    errors,
                ),
            )
            row = cur.fetchone()
        self.conn.commit()
        return str(row[0])

    def list_recent(self, limit: int = 30) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM coletas ORDER BY iniciado_em DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in rows]