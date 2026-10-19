"""Conexão por sessão: diálogos rodam em execuções posteriores e não podem reaproveitar uma conexão fechada."""
from __future__ import annotations

import psycopg
import pytest

from src.app.db import get_connection, is_usable, safe_rollback
from src.admission.models import AdmissionResult, OriginMetadata


class _Conn:
    def __init__(self, closed=False):
        self.closed = closed
        self.broken = False
        self.rollbacks = 0

    def cursor(self):
        if self.closed:
            raise psycopg.OperationalError("the connection is closed")
        raise AssertionError("não deveria consultar")

    def rollback(self):
        if self.closed:
            raise psycopg.OperationalError("the connection is closed")
        self.rollbacks += 1


def test_closed_connection_in_session_is_replaced():
    store = {"_db_connection": _Conn(closed=True)}
    fresh = _Conn()
    assert get_connection(store, connect_fn=lambda: fresh) is fresh
    assert store["_db_connection"] is fresh


def test_open_connection_is_reused():
    conn = _Conn()
    store = {"_db_connection": conn}
    assert get_connection(store, connect_fn=lambda: pytest.fail("não deveria reconectar")) is conn


def test_connection_terminated_by_the_server_is_replaced_before_use():
    """O objeto ainda parece aberto, mas o servidor encerrou a sessão (AdminShutdown): reconecta antes da tela."""
    from psycopg.pq import TransactionStatus

    class Terminated(_Conn):
        class info:
            transaction_status = TransactionStatus.IDLE

        def execute(self, sql):
            raise psycopg.errors.AdminShutdown("terminating connection due to administrator command")

        def close(self):
            self.closed = True

    stale, fresh = Terminated(), _Conn()
    store = {"_db_connection": stale}
    assert get_connection(store, connect_fn=lambda: fresh) is fresh
    assert stale.closed and store["_db_connection"] is fresh


def test_live_connection_passes_the_check_and_is_reused():
    from psycopg.pq import TransactionStatus

    class Live(_Conn):
        executed = 0

        class info:
            transaction_status = TransactionStatus.IDLE

        def execute(self, sql):
            self.executed += 1

    conn = Live()
    assert get_connection({"_db_connection": conn}, connect_fn=lambda: pytest.fail("não deveria reconectar")) is conn
    assert conn.executed == 1 and conn.rollbacks == 1


def test_unavailable_database_returns_none_with_reason():
    def boom():
        raise psycopg.OperationalError("connection timeout")
    store: dict = {}
    assert get_connection(store, connect_fn=boom) is None
    assert "timeout" in store["db_error"]


def test_safe_rollback_ignores_closed_connection():
    safe_rollback(_Conn(closed=True))  # não levanta
    assert not is_usable(_Conn(closed=True))


def test_card_document_with_closed_connection_falls_back_to_link(monkeypatch):
    """Reproduz o erro relatado: OperationalError 'the connection is closed' no diálogo do card."""
    from src.app.components import news_cards

    admitted = AdmissionResult(is_partial=False, partial_reasons=[], is_financial=True, financial_rule_passed=True,
                               distinct_glossary_terms=6, word_count=300, structured_type="ata", language="pt",
                               origin=OriginMetadata(), status="admitido", text="Texto completo da ata.")
    monkeypatch.setattr("src.admission.service.admit_url", lambda url: admitted)
    card = {"id_card": "c1", "titulo": "Ata", "url_fonte": "https://www.bcb.gov.br/ata"}
    text, _admission, error = news_cards.card_document(card, _Conn(closed=True))
    assert error is None and text == "Texto completo da ata."
