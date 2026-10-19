"""Card repository."""
import uuid
from typing import Any, Dict, Optional


class CardRepository:
    def __init__(self, conn):
        self.conn = conn

    def create(self, title: str, source_name: str, **kwargs: Any) -> str:
        # Callers must pass Portuguese column names, e.g. source_type -> tipo_fonte.
        card_id = str(kwargs.pop("card_id", kwargs.pop("id_card", uuid.uuid4())))
        fields = ["id_card", "titulo", "nome_fonte"] + list(kwargs.keys())
        values = [card_id, title, source_name] + list(kwargs.values())
        placeholders = ", ".join(["%s"] * len(fields))
        columns = ", ".join(fields)
        query = f"INSERT INTO cards ({columns}) VALUES ({placeholders}) RETURNING id_card"
        with self.conn.cursor() as cur:
            cur.execute(query, tuple(values))
            row = cur.fetchone()
        self.conn.commit()
        return str(row[0])

    def get(self, card_id: str) -> Optional[Dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM cards WHERE id_card = %s", (card_id,))
            row = cur.fetchone()
            if row is None:
                return None
            columns = [desc[0] for desc in cur.description]
        return dict(zip(columns, row))

    def list_recent(self, days: int = 7) -> list[dict]:
        query = ("SELECT c.*, p.fontes_independentes AS pauta_independentes FROM cards c "
                 "LEFT JOIN pautas p ON p.id_pauta = c.id_pauta "
                 "WHERE c.data_card >= CURRENT_DATE - (%s * INTERVAL '1 day') ORDER BY c.data_card DESC")
        with self.conn.cursor() as cur:
            cur.execute(query, (days,))
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in rows]