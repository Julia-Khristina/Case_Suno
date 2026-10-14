"""Material repository."""
from typing import Any


class MaterialRepository:

    def create(self, material_id: str | None = None, execution_id: str | None = None, level: str = "iniciante", output_format: str = "texto_analitico", state: str = "na_fila", generated_content: Any = None) -> str:
        import json
        import uuid

        material_id = material_id or str(uuid.uuid4())
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO materiais (id_material, id_execucao, nivel, formato, estado, conteudo_gerado)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id_material
                """,
                (
                    material_id,
                    execution_id,
                    level,
                    output_format,
                    state,
                    json.dumps(generated_content, default=str) if generated_content is not None else None,
                ),
            )
            row = cur.fetchone()
        self.conn.commit()
        return str(row[0])

    def __init__(self, conn):
        self.conn = conn

    def set_state(self, material_id: str, state: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute("UPDATE materiais SET estado = %s, atualizado_em = NOW() WHERE id_material = %s", (state, material_id))
        self.conn.commit()

    def set_edited_content(self, material_id: str, content: Any) -> None:
        import json

        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE materiais SET conteudo_editado = %s::jsonb, atualizado_em = NOW() WHERE id_material = %s",
                (json.dumps(content, default=str), material_id),
            )
        self.conn.commit()

    def get_state(self, material_id: str) -> str | None:
        with self.conn.cursor() as cur:
            cur.execute("SELECT estado FROM materiais WHERE id_material = %s", (material_id,))
            row = cur.fetchone()
        return row[0] if row else None

    def list_materials(self, limit: int = 100):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id_material, id_execucao, nivel, formato, estado, conteudo_gerado, conteudo_editado, criado_em
                FROM materiais
                ORDER BY criado_em DESC
                LIMIT %s
                """,
                (limit,),
            )
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]