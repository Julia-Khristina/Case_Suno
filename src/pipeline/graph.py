"""LangGraph pipeline construction."""

from langgraph.graph import END, START, StateGraph

from src.pipeline.state import PipelineState


NODES = ["admit", "extract", "generate", "evaluate_deterministic", "judge", "route", "human_validation", "export"]


def _identity(state: PipelineState) -> PipelineState:
    return state


def build_graph(checkpointer=None):
    builder = StateGraph(PipelineState)
    for node in NODES:
        builder.add_node(node, _identity)
    builder.add_edge(START, "admit")
    for source, target in zip(NODES, NODES[1:]):
        builder.add_edge(source, target)
    builder.add_edge("export", END)
    if checkpointer is None:
        return builder.compile()
    return builder.compile(checkpointer=checkpointer)