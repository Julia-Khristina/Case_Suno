"""Conexão com o banco por sessão do Streamlit.

Diálogos (st.dialog) e fragmentos rodam em execuções posteriores do script; por isso a conexão guardada na
sessão precisa ser reaberta quando foi fechada ou quebrou, em vez de ser reaproveitada fechada.
"""
from __future__ import annotations

from typing import Any, MutableMapping

_KEY = "_db_connection"


def is_usable(conn: Any) -> bool:
    return conn is not None and not getattr(conn, "closed", True) and not getattr(conn, "broken", False)


def _alive(conn: Any) -> bool:
    """Testa a conexão antes de reaproveitá-la. O servidor pode tê-la encerrado (reinício do banco, comando de
    administrador) sem que o objeto saiba: `closed` só muda na próxima consulta, que então falha na tela
    (visto em 18/10/2026: AdminShutdown ao clicar em Editar). Só testa sem transação em curso, para não
    interferir em nada pendente; uma transação com erro é desfeita, como faria a próxima consulta."""
    try:
        from psycopg.pq import TransactionStatus

        status = conn.info.transaction_status
    except Exception:  # noqa: BLE001  objeto sem `info` (conexão de teste): considera viva
        return True
    try:
        if status == TransactionStatus.INERROR:
            conn.rollback()
        elif status != TransactionStatus.IDLE:
            return status != TransactionStatus.UNKNOWN
        conn.execute("SELECT 1")
        conn.rollback()
        return True
    except Exception:  # noqa: BLE001
        return False


def get_connection(store: MutableMapping | None = None, connect_fn=None):
    """Devolve uma conexão aberta da sessão, reconectando se necessário; None se o banco estiver indisponível."""
    if store is None:
        import streamlit as st

        store = st.session_state
    conn = store.get(_KEY)
    if is_usable(conn) and _alive(conn):
        return conn
    if conn is not None:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
    if connect_fn is None:
        from src.persistence.database import connect as connect_fn
    try:
        conn = connect_fn()
    except Exception as exc:  # noqa: BLE001
        store[_KEY] = None
        store["db_error"] = str(exc)
        return None
    store[_KEY] = conn
    store.pop("db_error", None)
    return conn


def end_read_transaction(conn: Any) -> None:
    """Fecha a transação que as leituras abriram (psycopg abre uma no primeiro SELECT e não fecha sozinho).

    Sem isso a conexão da sessão fica "idle in transaction" indefinidamente, segurando locks que travam
    alterações de schema (visto em 18/10/2026: o painel de qualidade segurou `cards` por 38 minutos).
    Todas as escritas do app fazem commit nos repositórios, então aqui só há leitura a descartar.
    """
    if not is_usable(conn):
        return
    try:
        from psycopg.pq import TransactionStatus

        if conn.info.transaction_status != TransactionStatus.IDLE:
            conn.rollback()
    except Exception:  # noqa: BLE001
        pass


def safe_rollback(conn: Any) -> None:
    """Rollback que não levanta erro quando a conexão já está fechada."""
    if is_usable(conn):
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
