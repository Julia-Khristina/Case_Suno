"""Testes de integração com PostgreSQL: pulados (com motivo) quando o banco não responde, em vez de falhar
por timeout de conexão em cada teste. Para rodar: docker compose up -d postgres && python scripts/migrate.py"""
from __future__ import annotations

import pytest

_DB_TESTS = {"test_block6_persistence.py", "test_checkpointer_roundtrip.py", "test_collection_block9.py",
             "test_extraction_persistence.py", "test_human_validation_block7.py", "test_persistence_graph.py",
             "test_pipeline_postgres.py"}
_state: dict[str, object] = {}


def _db_available() -> tuple[bool, str]:
    if "ok" not in _state:
        try:
            from src.persistence.database import connect

            conn = connect()
            conn.close()
            _state.update(ok=True, reason="")
        except Exception as exc:  # noqa: BLE001
            _state.update(ok=False, reason=f"PostgreSQL indisponível: {type(exc).__name__}")
    return bool(_state["ok"]), str(_state["reason"])


def pytest_collection_modifyitems(config, items):
    for item in items:
        if item.fspath.basename in _DB_TESTS:
            ok, reason = _db_available()
            if not ok:
                item.add_marker(pytest.mark.skip(reason=reason))
