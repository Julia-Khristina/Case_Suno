"""Judge evaluation repository."""
import json
import uuid
from typing import Any

class JudgeRepository:
    def __init__(self, conn):
        self.conn = conn

    def create(
        self,
        attempt_id: str,
        rubric_version: str,
        judge_model_id: str,
        scores: dict[str, float] | None = None,
        justification: str | None = None,
        text_length: int | None = None,
        evidence: list[str] | None = None,
    ) -> str:
        judge_id = str(uuid.uuid4())
        query = """
            INSERT INTO avaliacoes_juiz
            (id_avaliacao_juiz, id_tentativa, versao_rubrica, id_modelo_juiz, notas, justificativa, tamanho_texto, evidencias)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb)
            RETURNING id_avaliacao_juiz
        """
        with self.conn.cursor() as cur:
            cur.execute(
                query,
                (
                    judge_id,
                    attempt_id,
                    rubric_version,
                    judge_model_id,
                    json.dumps(scores or {}, default=str),
                    justification,
                    text_length,
                    json.dumps(evidence or [], default=str),
                ),
            )
            row = cur.fetchone()
        self.conn.commit()
        return str(row[0])

    def list_by_attempt(self, attempt_id: str) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM avaliacoes_juiz WHERE id_tentativa = %s", (attempt_id,))
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in rows]