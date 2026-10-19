import uuid

import psycopg

from src.persistence.database import get_database_url
from src.collection.acervo import PostgresAcervo
from src.collection.scheduler import run_collection
from tests.fakes import content

URL = "https://example.test/ipca"


def test_manual_collection_persists_cards():
    conn = psycopg.connect(get_database_url(), connect_timeout=5)
    _cleanup(conn)  # restos de uma execução anterior interrompida
    with conn.cursor() as cur:
        cur.execute("SELECT NOW()")
        started = cur.fetchone()[0]
    try:
        def fetcher():
            return [
                {
                    "titulo": "IPCA sobe em setembro",
                    "nome_fonte": "BCB",
                    "tipo_fonte": "primaria",
                    "url": URL,
                    "descricao": "Inflacao medida pelo IPCA",
                    "data_publicacao": "2026-10-13",
                    "prioridade": 1,
                    "conteudo": content.SOURCE,  # texto completo do feed: card gerável
                }
            ]

        result = run_collection(conn=conn, fetcher=fetcher, limit=1, acervo=_OnlyTestItem(conn))
        assert len(result["cards"]) == 1
        assert len(result["errors"]) == 0

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM cards WHERE url_fonte = %s", (URL,))
            assert cur.fetchone()[0] == 1
            cur.execute("SELECT COUNT(*) FROM coletas")
            before = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM documentos WHERE id_card = %s", (result["cards"][0]["id_card"],))
            assert cur.fetchone()[0] == 1  # documento do card gravado para a geração
        assert before >= 1
    finally:
        _cleanup(conn, since=started)
        conn.close()


class _OnlyTestItem(PostgresAcervo):
    """Acervo real (grava no banco), mas que só enxerga o item deste teste: sem isso a coleta de teste agruparia e
    transformaria em card as notícias reais do acervo, e o limite diário dependeria das coletas reais do dia."""

    def window(self, since):
        return [row for row in super().window(since) if row["url"] == URL]

    def pautas_with_cards_since(self, since):
        return 0


def _cleanup(conn, since=None) -> None:
    """Remove só o que este teste cria: o card de exemplo e, se `since` for dado, os registros de coleta criados
    depois do início do teste (nunca as coletas reais do banco)."""
    conn.rollback()
    with conn.cursor() as cur:
        # pautas criadas só para este item (acervo → cards → pautas, nessa ordem por causa das chaves estrangeiras)
        cur.execute("SELECT DISTINCT id_pauta FROM itens_coletados WHERE url = %s AND id_pauta IS NOT NULL", (URL,))
        pautas = [row[0] for row in cur.fetchall()]
        cur.execute("DELETE FROM itens_coletados WHERE url = %s", (URL,))
        # o mesmo texto pode estar ligado a execuções de outros testes: só desliga o documento do card
        cur.execute("UPDATE documentos SET id_card = NULL WHERE id_card IN (SELECT id_card FROM cards WHERE url_fonte = %s)",
                    (URL,))
        cur.execute("DELETE FROM cards WHERE url_fonte = %s", (URL,))
        for id_pauta in pautas:
            cur.execute("DELETE FROM pautas WHERE id_pauta = %s AND NOT EXISTS (SELECT 1 FROM cards WHERE id_pauta = %s) "
                        "AND NOT EXISTS (SELECT 1 FROM itens_coletados WHERE id_pauta = %s)", (id_pauta, id_pauta, id_pauta))
        if since is not None:
            cur.execute("DELETE FROM coletas WHERE nome_fonte = %s AND iniciado_em >= %s", ("coleta_diaria", since))
    conn.commit()