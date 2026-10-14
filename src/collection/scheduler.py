"""Collection scheduler and manual runner."""

import sys
import time
from datetime import datetime, timezone
from typing import Any, Callable

from zoneinfo import ZoneInfo

from src.collection.card_builder import build_card, insert_cards
from src.collection.dedup import deduplicate_items
from src.collection.fetchers import fetch_all_sources, load_sources, SourceDefinition
from src.collection.ranker import rank_items
from src.persistence.repositories.collection_repository import CollectionRepository


BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")


def _load_config() -> dict[str, Any]:
    try:
        import yaml

        with open("config/coleta_fontes.yaml", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        return data
    except Exception:
        return {}


def run_collection(conn=None, fetcher: Callable[[], Any] | None = None, sources=None, limit: int | None = None, now=None) -> dict[str, Any]:
    config = _load_config()
    if limit is None:
        limit = int(config.get("limite_cards_diario_padrao", 8))
    if sources is None:
        sources = load_sources()

    if fetcher is not None:
        fetched = fetcher()
        if isinstance(fetched, tuple):
            items, errors = fetched
        else:
            items = fetched
            errors = []
    else:
        items, errors = fetch_all_sources()

    deduped = deduplicate_items(items)
    ranked = rank_items(deduped, limit=limit)
    cards = [build_card(item) for item in ranked]

    if conn is not None:
        insert_cards(conn, cards)
        try:
            CollectionRepository(conn).create(source_name="coleta_diaria", items_count=len(items), errors=errors)
        except Exception:
            pass

    return {
        "started_at": now or datetime.now(timezone.utc),
        "items": items,
        "deduped": deduped,
        "cards": cards,
        "errors": errors,
        "card_ids": [],
    }


def should_run_scheduled(last_run_date, config_time: str = "08:00", now=None) -> bool:
    now = now or datetime.now(BRAZIL_TZ)
    if last_run_date == now.date():
        return False
    return now.strftime("%H:%M") == config_time


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        conn = None
        try:
            from src.persistence.database import connect

            conn = connect()
        except Exception:
            conn = None
        result = run_collection(conn=conn)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        print(f"Coleta manual finalizada: {len(result['cards'])} cards, {len(result['errors'])} erros")
        return

    config = _load_config()
    scheduled_time = str(config.get("horario_coleta_padrao", "08:00"))
    last_run_date = None
    while True:
        now = datetime.now(BRAZIL_TZ)
        if should_run_scheduled(last_run_date, scheduled_time, now=now):
            try:
                from src.persistence.database import connect

                conn = connect()
            except Exception:
                conn = None
            run_collection(conn=conn)
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            last_run_date = now.date()
        time.sleep(30)


if __name__ == "__main__":
    main()