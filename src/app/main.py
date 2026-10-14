"""Streamlit application entrypoint for Case Suno Content."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import streamlit as st

st.set_page_config(page_title="Suno Asset", layout="wide")

from src.app.theme import inject_theme, sidebar_nav, topbar  # noqa: E402

inject_theme()
st.session_state.setdefault("page", "inicio")

try:
    from src.persistence.database import connect

    db_connection = connect()
except Exception as exc:  # noqa: BLE001
    db_connection = None
    st.sidebar.caption(f"Banco indisponível: {exc}")

sidebar_nav()
topbar()

flash = st.session_state.pop("flash", None)
if flash:
    st.toast(flash)

page = st.session_state["page"]

if page == "inicio":
    from src.app.dashboard import render_suno_dashboard

    render_suno_dashboard(db_connection)
elif page == "noticias":
    from src.app.cards_screen import render_cards_screen

    render_cards_screen(db_connection)
elif page == "materiais":
    from src.app.theme import page_header

    page_header("Materiais", "Escolha a noticia, o nivel e o formato gerado.")

    from src.app.components.material_cards import render_materials_hub

    render_materials_hub(db_connection)
else:
    from src.app.glossary_panel import render_glossary_panel
    from src.app.theme import page_header

    page_header("Configurações", "Glossário de termos técnicos usado na geração dos materiais.")
    render_glossary_panel()

if db_connection is not None:
    db_connection.close()