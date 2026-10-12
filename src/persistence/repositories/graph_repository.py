"""Graph-as-tables repository for Case Suno Content."""
import json
import uuid
from typing import Any, Dict, Iterable, List, Optional


class GraphRepository:
    def __init__(self, conn):
        self.conn = conn

    def add_node(self, node_type: str, properties: Optional[Dict[str, Any]] = None, node_id: Optional[str] = None) -> str:
        uid = node_id or str(uuid.uuid4())
        query = """
            INSERT INTO nos_grafo (id_no, tipo_no, propriedades)
            VALUES (%s, %s, %s::jsonb)
            ON CONFLICT (id_no) DO UPDATE SET tipo_no = EXCLUDED.tipo_no, propriedades = EXCLUDED.propriedades
            RETURNING id_no
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (uid, node_type, _jsonb(properties or {})))
            row = cur.fetchone()
        self.conn.commit()
        return str(row[0])

    def add_edge(
        self,
        from_node_id: str,
        to_node_id: str,
        relation_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> str:
        query = """
            INSERT INTO arestas_grafo (id_no_origem, id_no_destino, tipo_relacao, propriedades)
            VALUES (%s, %s, %s, %s::jsonb)
            RETURNING id_aresta
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (from_node_id, to_node_id, relation_type, _jsonb(properties or {})))
            row = cur.fetchone()
        self.conn.commit()
        return str(row[0])

    def traverse(self, start_id: str, relation_types: Optional[Iterable[str]] = None, max_depth: int = 5, direction: str = "out") -> List[dict]:
        allowed = list(relation_types) if relation_types is not None else None
        if direction not in {"out", "both"}:
            raise ValueError("direction must be 'out' or 'both'")

        if direction == "out":
            query = """
                WITH RECURSIVE traversal(id_no, path, depth) AS (
                    SELECT n.id_no, ARRAY[n.id_no], 0
                    FROM nos_grafo n
                    WHERE n.id_no = %s
                    UNION ALL
                    SELECT e.id_no_destino, t.path || e.id_no_destino, t.depth + 1
                    FROM traversal t
                    JOIN arestas_grafo e ON e.id_no_origem = t.id_no
                    WHERE t.depth < %s
                      AND (%s::text[] IS NULL OR e.tipo_relacao = ANY(%s::text[]))
                      AND NOT (e.id_no_destino = ANY(t.path))
                )
                SELECT id_no, path, depth FROM traversal ORDER BY depth, id_no
            """
            params = (start_id, max_depth, allowed, allowed)
        else:
            query = """
                WITH RECURSIVE traversal(id_no, path, depth) AS (
                    SELECT n.id_no, ARRAY[n.id_no], 0
                    FROM nos_grafo n
                    WHERE n.id_no = %s
                    UNION ALL
                    SELECT CASE WHEN e.id_no_origem = t.id_no THEN e.id_no_destino ELSE e.id_no_origem END,
                           t.path || CASE WHEN e.id_no_origem = t.id_no THEN e.id_no_destino ELSE e.id_no_origem END,
                           t.depth + 1
                    FROM traversal t
                    JOIN arestas_grafo e ON e.id_no_origem = t.id_no OR e.id_no_destino = t.id_no
                    WHERE t.depth < %s
                      AND (%s::text[] IS NULL OR e.tipo_relacao = ANY(%s::text[]))
                      AND NOT (CASE WHEN e.id_no_origem = t.id_no THEN e.id_no_destino ELSE e.id_no_origem END = ANY(t.path))
                )
                SELECT id_no, path, depth FROM traversal ORDER BY depth, id_no
            """
            params = (start_id, max_depth, allowed, allowed)

        with self.conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        return [{"node_id": str(r[0]), "path": [str(x) for x in r[1]], "depth": r[2]} for r in rows]

    def incoming(self, node_id: str, relation_type: Optional[str] = None) -> List[str]:
        params = [node_id]
        query = "SELECT id_no_origem FROM arestas_grafo WHERE id_no_destino = %s"
        if relation_type is not None:
            query += " AND tipo_relacao = %s"
            params.append(relation_type)
        with self.conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
        return [str(r[0]) for r in rows]

    def provenance_path(self, start_id: str, max_depth: int = 10) -> List[dict]:
        return self.traverse(start_id, direction="both", max_depth=max_depth)

    def count_nodes(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM nos_grafo")
            row = cur.fetchone()
        return int(row[0])


def _jsonb(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)