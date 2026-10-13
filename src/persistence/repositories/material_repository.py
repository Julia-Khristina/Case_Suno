"""Material repository."""
from typing import Any


class MaterialRepository:
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