"""Apply the initial schema to PostgreSQL when available."""
import os
from pathlib import Path

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None  # type: ignore

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "persistence" / "schema.sql"


def main() -> int:
    database_url = os.getenv("DATABASE_URL", "postgresql://suno:suno@localhost:5432/suno")
    if psycopg is None:
        print("psycopg is not available; migration skipped.")
        return 0

    if not SCHEMA_PATH.exists():
        print(f"Schema file not found: {SCHEMA_PATH}")
        return 0

    try:
        with psycopg.connect(database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
            conn.commit()
        print(f"Migration applied from {SCHEMA_PATH}")
        return 0
    except Exception as exc:  # pragma: no cover - environment dependent
        print(f"Migration skipped: {exc}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())