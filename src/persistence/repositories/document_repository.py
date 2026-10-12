"""Document repository."""
from typing import Any, Dict, Optional


class DocumentRepository:
    def __init__(self, conn):
        self.conn = conn

    def create(self, document_hash: str, origin_type: str, **kwargs: Any) -> str:
        fields = ["hash", "tipo_origem"] + list(kwargs.keys())
        values = [document_hash, origin_type] + list(kwargs.values())
        placeholders = ", ".join(["%s"] * len(fields))
        columns = ", ".join(fields)
        query = f"INSERT INTO documentos ({columns}) VALUES ({placeholders}) ON CONFLICT (hash) DO UPDATE SET tipo_origem = EXCLUDED.tipo_origem RETURNING hash"
        with self.conn.cursor() as cur:
            cur.execute(query, tuple(values))
            row = cur.fetchone()
        self.conn.commit()
        return str(row[0])

    def get(self, document_hash: str) -> Optional[Dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM documentos WHERE hash = %s", (document_hash,))
            row = cur.fetchone()
            if row is None:
                return None
            columns = [desc[0] for desc in cur.description]
        return dict(zip(columns, row))