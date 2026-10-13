"""Attempt repository."""
import uuid
from typing import Any

class AttemptRepository:
    def __init__(self, conn):
        self.conn = conn

    def create(
        self,
        material_id: str,
        attempt_number: int,
        content: Any = None,
        metrics: dict | None = None,
        failures: list[str] | None = None,
        rejection_reason: str | None = None,
        tokens: int = 0,
        latency: float = 0.0,
        model_id: str | None = None,
    ) -> str:
        import json
        attempt_id = str(uuid.uuid4())
        query = """
            INSERT INTO tentativas
            (id_tentativa, id_material, numero_tentativa, conteudo, metricas, falhas, motivo_reprovacao, tokens, latencia, id_modelo)
            VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s, %s)
            RETURNING id_tentativa
        """
        with self.conn.cursor() as cur:
            cur.execute(
                query,
                (
                    attempt_id,
                    material_id,
                    attempt_number,
                    json.dumps(content, default=str) if content is not None else None,
                    json.dumps(metrics or {}, default=str),
                    json.dumps(failures or [], default=str),
                    rejection_reason,
                    tokens,
                    latency,
                    model_id,
                ),
            )
            row = cur.fetchone()
        self.conn.commit()
        return str(row[0])

    def list_by_material(self, material_id: str) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM tentativas WHERE id_material = %s ORDER BY numero_tentativa", (material_id,))
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in rows]