"""LangGraph PostgreSQL checkpointer helper."""
from contextlib import contextmanager
from typing import Iterator

from langgraph.checkpoint.postgres import PostgresSaver

from src.persistence.database import get_database_url


@contextmanager
def postgres_checkpointer(database_url: str | None = None) -> Iterator[PostgresSaver]:
    url = database_url or get_database_url()
    with PostgresSaver.from_conn_string(url) as saver:
        saver.setup()
        yield saver