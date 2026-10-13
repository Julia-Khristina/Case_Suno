"""Human decision repository."""
import uuid


class DecisionRepository:
    def __init__(self, conn):
        self.conn = conn

    def create(self, material_id: str, decision: str, note: str | None = None) -> str:
        decision_id = str(uuid.uuid4())
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO decisoes_humanas (id_decisao, id_material, decisao, observacao) VALUES (%s, %s, %s, %s) RETURNING id_decisao",
                (decision_id, material_id, decision, note),
            )
            row = cur.fetchone()
        self.conn.commit()
        return str(row[0])