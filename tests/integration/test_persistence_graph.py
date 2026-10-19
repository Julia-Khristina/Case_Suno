import psycopg
import pytest

from src.persistence.database import get_database_url
from src.persistence.repositories.graph_repository import GraphRepository
from tests.integration.graph_cleanup import delete_component


@pytest.fixture
def db_conn():
    conn = psycopg.connect(get_database_url(), connect_timeout=5)
    created: list = []
    conn.created_nodes = created  # type: ignore[attr-defined]  nós criados pelo teste, apagados no fim
    yield conn
    conn.rollback()
    delete_component(conn, created)
    conn.close()


def _node(conn, repo, kind, props):
    node = repo.add_node(kind, props)
    conn.created_nodes.append(node)
    return node


def test_graph_traversal_follows_outgoing_edges(db_conn):
    repo = GraphRepository(db_conn)
    source = _node(db_conn, repo, "documento", {"hash": "doc-test"})
    target = _node(db_conn, repo, "trecho", {"ordem": 1, "texto": "trecho exato"})
    repo.add_edge(source, target, "TEM_TRECHO")

    paths = repo.traverse(source, relation_types=["TEM_TRECHO"], max_depth=3)

    assert any(item["node_id"] == target for item in paths)
    path_ids = next(item["path"] for item in paths if item["node_id"] == target)
    assert path_ids == [source, target]


def test_same_story_cards_can_be_traversed(db_conn):
    repo = GraphRepository(db_conn)
    card_one = _node(db_conn, repo, "card", {"card_id": "card-1"})
    card_two = _node(db_conn, repo, "card", {"card_id": "card-2"})
    repo.add_edge(card_one, card_two, "ATUALIZA")

    paths = repo.traverse(card_one, relation_types=["ATUALIZA"], max_depth=3)

    assert any(item["node_id"] == card_two for item in paths)