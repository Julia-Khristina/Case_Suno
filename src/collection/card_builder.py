"""Card construction and persistence for collected items."""

import uuid
from datetime import date
from typing import Any

from .cleaner import clean_item

ONGOING_KEYWORDS = ("andamento", "desdobramento", "atualiza", "investig", "continua")
EVENT_KEYWORDS = ("decide", "decid", "calcul", "divulg", "result", "fato relev")


def categorize_item(item: Any) -> str:
    text = f"{_field(item, 'titulo')} {_field(item, 'descricao')}".lower()
    if any(keyword in text for keyword in ONGOING_KEYWORDS):
        return "em_andamento"
    return "acabou_de_acontecer"


def build_entry_reason(item: Any) -> str:
    source = _field(item, "nome_fonte") or _field(item, "source_name") or "fonte"
    title = _field(item, "titulo") or _field(item, "title") or "item"
    text = str(title).lower()
    if any(keyword in text for keyword in EVENT_KEYWORDS):
        return f"{source}: fato/evento financeiro coletado para card de entrada"
    return f"{source}: material disponivel para acompanhamento e leitura"


def _field(item: Any, name: str):
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


def _card_date(item: Any) -> date:
    value = _field(item, "data_publicacao") or _field(item, "card_date")
    if isinstance(value, date):
        return value
    if value:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            pass
    return date.today()


def build_card(item: Any, card_id: str | None = None) -> dict[str, Any]:
    item = clean_item(item)
    title = str(_field(item, "titulo") or _field(item, "title") or "Card sem titulo")
    return {
        "id_card": card_id or str(uuid.uuid4()),
        "titulo": title,
        "descricao": _field(item, "descricao") or _field(item, "description") or title,
        "tipo_fonte": _field(item, "tipo_fonte") or _field(item, "source_type") or "primaria",
        "nome_fonte": _field(item, "nome_fonte") or _field(item, "source_name") or "fonte",
        "url_fonte": _field(item, "url") or _field(item, "source_url"),
        "categoria": _field(item, "categoria") or categorize_item(item),
        "motivo_entrada": _field(item, "motivo_entrada") or build_entry_reason(item),
        "data_card": _card_date(item),
        "estado": "ativo",
    }


def insert_cards(conn, cards: list[dict[str, Any]]) -> list[str]:
    from src.persistence.repositories.card_repository import CardRepository

    repo = CardRepository(conn)
    ids: list[str] = []
    for card in cards:
        title = card.get("titulo", "Card")
        source_name = card.get("nome_fonte", "fonte")
        card_id = repo.create(title=title, source_name=source_name, **{k: v for k, v in card.items() if k not in {"titulo", "nome_fonte"}})
        ids.append(card_id)
    return ids