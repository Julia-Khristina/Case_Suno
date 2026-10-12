"""Database helpers for Case Suno Content."""
import os
from typing import Any


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql://suno:suno@localhost:5432/suno")


def connect(**kwargs: Any):
    import psycopg

    return psycopg.connect(get_database_url(), connect_timeout=5, **kwargs)