"""Status de geração em formato de etapas."""
import streamlit as st

from src.app.components.news_cards import LEVEL_LABELS
from src.app.theme import esc, table_html

STEPS = [
    ("na fila", "Na fila"),
    ("extraindo", "Extraindo"),
    ("gerando", "Gerando"),
    ("avaliando", "Avaliando"),
    ("aguardando revisao", "Aguardando revisão"),
]


def render_status(state: str):
    keys = [key for key, _ in STEPS]
    if state not in keys:
        st.write(f"Estado atual: {state}")
        return
    current = keys.index(state)
    items = ""
    for idx, (_, label) in enumerate(STEPS):
        cls = "now" if idx == current else ("done" if idx < current else "")
        items += f'<div class="step {cls}"><span class="dot"></span><span>{esc(label)}</span></div>'
    st.markdown(f'<div class="stepper">{items}</div>', unsafe_allow_html=True)


def render_queue(queue: list[dict]):
    """Lista as últimas solicitações de geração feitas nesta sessão."""
    if not queue:
        return
    rows = [
        [
            str(item.get("titulo") or item.get("id_card") or "—"),
            ", ".join(LEVEL_LABELS.get(n, n) for n in item.get("niveis", [])),
            dict(STEPS).get(item.get("estado", ""), item.get("estado", "")),
        ]
        for item in reversed(queue[-5:])
    ]
    st.markdown(table_html(["Notícia", "Níveis", "Estado"], rows), unsafe_allow_html=True)
    render_status(queue[-1].get("estado", "na fila"))