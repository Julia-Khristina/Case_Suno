import psycopg
import pytest

from src.persistence.database import get_database_url
from src.persistence.repositories.graph_repository import GraphRepository


@pytest.fixture
def db_conn():
    conn = psycopg.connect(get_database_url(), connect_timeout=5)
    yield conn
    conn.rollback()
    conn.close()


def test_graph_traversal_follows_outgoing_edges(db_conn):
    repo = GraphRepository(db_conn)
    source = repo.add_node("documento", {"hash": "doc-test"})
    target = repo.add_node("trecho", {"ordem": 1, "texto": "trecho exato"})
    repo.add_edge(source, target, "TEM_TRECHO")

    paths = repo.traverse(source, relation_types=["TEM_TRECHO"], max_depth=3)

    assert any(item["node_id"] == target for item in paths)
    path_ids = next(item["path"] for item in paths if item["node_id"] == target)
    assert path_ids == [source, target]


def test_same_story_cards_can_be_traversed(db_conn):
    repo = GraphRepository(db_conn)
    card_one = repo.add_node("card", {"card_id": "card-1"})
    card_two = repo.add_node("card", {"card_id": "card-2"})
    repo.add_edge(card_one, card_two, "ATUALIZA")

    paths = repo.traverse(card_one, relation_types=["ATUALIZA"], max_depth=3)

    assert any(item["node_id"] == card_two for item in paths)