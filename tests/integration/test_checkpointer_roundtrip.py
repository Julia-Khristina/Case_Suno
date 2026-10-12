from langgraph.graph import StateGraph, START, END

from src.persistence.database import get_database_url
from src.pipeline.checkpointer import postgres_checkpointer


def _node(state):
    return {"x": state["x"] + 1}


def test_checkpointer_roundtrip():
    graph = StateGraph(dict)
    graph.add_node("inc", _node)
    graph.add_edge(START, "inc")
    graph.add_edge("inc", END)

    url = get_database_url()
    with postgres_checkpointer(url) as checkpointer:
        app = graph.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "test-roundtrip"}}
        output = app.invoke({"x": 1}, config)
        state = app.get_state(config)

    assert output["x"] == 2
    assert state.values["x"] == 2