"""Limpeza do grafo nos testes de integração: remove só o que o teste criou, para não poluir o banco de
desenvolvimento (que é o mesmo usado pelo app)."""
from __future__ import annotations


def delete_component(conn, start_ids: list, since=None) -> int:
    """Apaga os nós alcançáveis a partir de `start_ids` (arestas em qualquer direção) e as arestas deles.

    Com `since`, a busca só atravessa nós criados a partir desse instante (com 5 s de folga), então nós antigos
    ligados por acaso nunca são tocados. Devolve quantos nós foram apagados.
    """
    seen = {str(i) for i in start_ids if i}
    frontier = set(seen)
    with conn.cursor() as cur:
        while frontier:
            cur.execute("""SELECT n.id_no::text FROM arestas_grafo e JOIN nos_grafo n
                             ON n.id_no = CASE WHEN e.id_no_origem = ANY(%(ids)s::uuid[]) THEN e.id_no_destino
                                               ELSE e.id_no_origem END
                           WHERE (e.id_no_origem = ANY(%(ids)s::uuid[]) OR e.id_no_destino = ANY(%(ids)s::uuid[]))
                             AND (%(since)s::timestamptz IS NULL OR n.criado_em >= %(since)s::timestamptz - INTERVAL '5 seconds')""",
                        {"ids": list(frontier), "since": since})
            found = {r[0] for r in cur.fetchall()} - seen
            seen |= found
            frontier = found
        ids = list(seen)
        if ids:
            cur.execute("DELETE FROM arestas_grafo WHERE id_no_origem = ANY(%s::uuid[]) OR id_no_destino = ANY(%s::uuid[])",
                        (ids, ids))
            cur.execute("DELETE FROM nos_grafo WHERE id_no = ANY(%s::uuid[])", (ids,))
    conn.commit()
    return len(seen)
