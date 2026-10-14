"""Tema visual compartilhado da interface Suno Asset.

Reproduz o mockup da tela inicial: sidebar escura com destaque vermelho,
barra superior branca, hero escuro, cards brancos e botão vermelho.
Todo o CSS fica aqui para que as telas só se preocupem com o conteúdo.
"""
from __future__ import annotations

import base64
import html
import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

TZ = ZoneInfo("America/Sao_Paulo")
USER_NAME = os.getenv("SUNO_USER_NAME", "Ju")
# Se o logotipo oficial existir neste caminho, ele substitui o logotipo em CSS.
LOGO_PATH = Path("assets/logo_suno.svg")

PAGES = [
    ("inicio", "Início", None),
    ("noticias", "Notícias", None),
    ("materiais", "Materiais", None),
    ("configuracoes", "Configurações", None),
]




_ICONS = {
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    "newspaper": '<path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8M15 18h-5M10 6h8v4h-8V6Z"/>',
    "filter": '<path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3Z"/>',
    "file": '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2Z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>',
    "arrow_up": '<path d="M12 19V5M5 12l7-7 7 7"/>',
    "arrow_down": '<path d="M12 5v14M19 12l-7 7-7-7"/>',
    "external": '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14 21 3"/>',
    "chevron_down": '<path d="m6 9 6 6 6-6"/>',
}


def svg(name: str, size: int = 20, stroke: float = 1.8) -> str:
    if name == "user":
        return (
            f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="currentColor">'
            '<circle cx="12" cy="8" r="4.2"/><path d="M4 21a8 8 0 0 1 16 0Z"/></svg>'
        )
    return (
        f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" stroke="currentColor" '
        f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{_ICONS[name]}</svg>'
    )


# ---------------------------------------------------------------- datas / textos
def agora() -> datetime:
    return datetime.now(TZ)


def saudacao(now: datetime | None = None) -> tuple[str, str]:
    """Retorna (texto, ícone) conforme a hora em São Paulo."""
    hour = (now or agora()).hour
    if hour < 12:
        return "Bom dia", "sun"
    if hour < 18:
        return "Boa tarde", "sun"
    return "Boa noite", "moon"


def parse_dt(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime(value.year, value.month, value.day)
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=TZ)


# Campos de data aceitos no dicionário do card (o primeiro que existir é usado).
CARD_DATE_FIELDS = ("publicado_em", "data_publicacao", "criado_em", "data_coleta")


def card_datetime(card: dict) -> datetime | None:
    for field in CARD_DATE_FIELDS:
        dt = parse_dt(card.get(field))
        if dt:
            return dt.astimezone(TZ)
    return None


def tempo_relativo(dt: datetime | None) -> str:
    if dt is None:
        return ""
    seconds = max(0, int((agora() - dt).total_seconds()))
    if seconds < 3600:
        minutes = max(1, seconds // 60)
        return f"Há {minutes} min"
    if seconds < 86400:
        hours = seconds // 3600
        return f"Há {hours} hora" + ("" if hours == 1 else "s")
    days = seconds // 86400
    return f"Há {days} dia" + ("" if days == 1 else "s")


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


# ---------------------------------------------------------------- navegação
def navigate(page: str) -> None:
    st.session_state["page"] = page


def sidebar_nav() -> None:
    with st.sidebar:
        st.markdown(_brand_html(), unsafe_allow_html=True)
        current = st.session_state.get("page", "inicio")
        for key, label, icon in PAGES:
            prefix = "navactive_" if key == current else "nav_"
            st.button(label, key=prefix + key, icon=icon, on_click=navigate, args=(key,))


def _brand_html() -> str:
    if LOGO_PATH.exists():
        data = base64.b64encode(LOGO_PATH.read_bytes()).decode()
        return f'<div class="brand"><img src="data:image/svg+xml;base64,{data}" alt="Suno Asset"/></div>'
    return (
        '<div class="brand"><div class="brand-row"><span class="bk l"></span>'
        '<span class="brand-name">SUNO</span><span class="bk r"></span></div>'
        '<div class="brand-sub">ASSET</div></div>'
    )


# ---------------------------------------------------------------- componentes
def topbar() -> None:
    texto, icone = saudacao()
    st.markdown(
        '<div class="topbar"><div class="greet">'
        f'<span class="greet-ico">{svg(icone, 22)}</span>'
        f'<span>{esc(texto)}, {esc(USER_NAME)}</span>'
        f'<span class="greet-chev">{svg("chevron_down", 16)}</span></div>'
        f'<div class="sep"></div><div class="avatar">{svg("user", 22)}</div></div>',
        unsafe_allow_html=True,
    )


def hero() -> None:
    texto, icone = saudacao()
    st.markdown(
        '<div class="hero">'
        f'<div class="hero-ico">{svg(icone, 34, 1.6)}</div>'
        f'<h1>{esc(texto)}, <span>{esc(USER_NAME)}!</span></h1>'
        '<p>Aqui você encontra as principais notícias do mercado financeiro e de economia, '
        'além de acompanhar a seleção das melhores informações e os materiais gerados no dia.</p>'
        '</div>',
        unsafe_allow_html=True,
    )


def kpi_card(icon: str, label: str, value, sub: str = "", delta: float | None = None) -> None:
    if delta is not None:
        arrow = "arrow_up" if delta >= 0 else "arrow_down"
        sub_html = f'<div class="kpi-sub delta">{svg(arrow, 16, 2.2)}<span>{esc(sub)}</span></div>'
    else:
        sub_html = f'<div class="kpi-sub">{esc(sub)}</div>'
    st.markdown(
        '<div class="kpi">'
        f'<div class="kpi-ico">{svg(icon, 20)}</div>'
        f'<div class="kpi-label">{esc(label)}</div>'
        f'<div class="kpi-value">{esc(value)}</div>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str = "") -> None:
    sub = f'<p class="page-sub">{esc(subtitle)}</p>' if subtitle else ""
    st.markdown(f'<div class="page-head"><h2>{esc(title)}</h2>{sub}</div>', unsafe_allow_html=True)


def section_title(text: str) -> None:
    st.markdown(f'<h3 class="sec-title">{esc(text)}</h3>', unsafe_allow_html=True)


def chip(text: str) -> str:
    return f'<span class="chip">{esc(text)}</span>'


def empty_state(message: str) -> None:
    st.markdown(f'<div class="empty">{esc(message)}</div>', unsafe_allow_html=True)


def table_html(headers: list[str], rows: list[list]) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in rows)
    return f'<div class="tbl-wrap"><table class="tbl"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def inject_theme() -> None:
    st.markdown("<style>" + _CSS + "</style>", unsafe_allow_html=True)


_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20,400,0,0&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
:root{
  --red:#B3141F; --red-strong:#A4172A; --red-soft:#FBE6E6; --red-active:#6E1B25;
  --ink:#16161A; --muted:#6B6B70; --line:#ECE9E7; --bg:#F6F5F4; --side:#0E0E10;
  --delta-up:#B3141F;
}
html, body, .stApp, [class*="st-"], button, input, textarea{font-family:'Plus Jakarta Sans',system-ui,-apple-system,'Segoe UI',sans-serif;}
[data-testid="stIconMaterial"], [data-testid="stIconMaterial"] * {
  font-feature-settings: 'liga' !important;
  -webkit-font-feature-settings: 'liga' !important;
  font-family: "Material Symbols Rounded", "Material Symbols Outlined", "Material Icons", sans-serif !important;
  font-size: 20px;
  line-height: 1;
  font-weight: 400;
  font-style: normal;
}
.stApp{background:var(--bg); color:var(--ink);}
header[data-testid="stHeader"], #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"]{display:none !important;}
.block-container, [data-testid="stMainBlockContainer"]{padding:0 2rem 3rem 2rem !important; max-width:100% !important;}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"]{background:var(--side); width:240px !important; min-width:240px !important; border:none;}
[data-testid="stSidebar"] > div:first-child{background:var(--side);}
[data-testid="stSidebar"]::after{content:""; position:absolute; left:0; bottom:0; width:100%; height:320px; pointer-events:none;
  background:repeating-radial-gradient(circle at 0% 100%, transparent 0 22px, rgba(196,22,42,.55) 22px 23px);
  -webkit-mask-image:linear-gradient(to top, #000 10%, transparent 100%); mask-image:linear-gradient(to top, #000 10%, transparent 100%);}
[data-testid="stSidebarHeader"]{display:none;}
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{padding-top:1.6rem;}
.brand{text-align:center; margin:0 0 2rem 0;}
.brand img{max-width:150px;}
.brand-row{display:flex; align-items:center; justify-content:center; gap:10px;}
.brand-name{color:#fff; font-weight:500; font-size:22px; letter-spacing:.42em; margin-right:-.42em;}
.bk{display:inline-block; width:9px; height:30px;}
.bk.l{border-left:4px solid #D81B2C; border-radius:100% 0 0 100% / 50% 0 0 50%;}
.bk.r{border-right:4px solid #D81B2C; border-radius:0 100% 100% 0 / 0 50% 50% 0;}
.brand-sub{color:#fff; font-size:10px; letter-spacing:.5em; margin-top:2px; margin-right:-.5em;}
[data-testid="stSidebar"] [class*="st-key-nav"]{width:100%;}
[data-testid="stSidebar"] [class*="st-key-nav"] button{width:100%; justify-content:flex-start; gap:12px; background:transparent; border:none; color:#EDEDED;
  padding:.72rem .95rem; border-radius:8px; font-weight:500; box-shadow:none;}
[data-testid="stSidebar"] [class*="st-key-nav"] button p{font-size:14px; font-weight:500;}
[data-testid="stSidebar"] [class*="st-key-nav"] button:hover{background:rgba(255,255,255,.07); color:#fff;}
[data-testid="stSidebar"] [class*="st-key-navactive_"] button{background:var(--red-active); color:#fff; box-shadow:inset 0 0 0 1px rgba(216,27,44,.35);}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"]{color:#8d8d92;}

/* ---------- barra superior ---------- */
.topbar{margin:0 -2rem 1.6rem -2rem; height:64px; background:#fff; border-bottom:1px solid #E6E3E1; box-shadow:0 1px 3px rgba(0,0,0,.04);
  display:flex; align-items:center; justify-content:flex-end; gap:18px; padding:0 2.2rem;}
.greet{display:flex; align-items:center; gap:10px; font-size:14px; font-weight:500; color:var(--ink);}
.greet-ico{color:var(--red); display:flex;}
.greet-chev{display:flex; color:var(--ink);}
.sep{width:1px; height:26px; background:#E6E3E1;}
.avatar{width:40px; height:40px; border-radius:50%; background:#111; color:#fff; display:flex; align-items:center; justify-content:center;}

/* ---------- hero ---------- */
.hero{position:relative; overflow:hidden; background:linear-gradient(135deg,#0B0B0C 0%,#1B1B1D 55%,#0F0F10 100%); border-radius:14px; padding:36px 40px 40px 40px; margin-bottom:1.6rem;}
.hero::after{content:""; position:absolute; right:-170px; top:-10px; width:640px; height:640px; border:2px solid #C4162A; border-radius:50%; pointer-events:none;}
.hero-ico{color:#E0202F; display:flex; margin-bottom:6px;}
.hero h1{color:#fff; font-size:44px; font-weight:700; margin:0 0 14px 0; padding:0; letter-spacing:-.01em; line-height:1.15;}
.hero h1 span{color:#E0202F;}
.hero p{color:#E7E7E9; font-size:15px; line-height:1.55; max-width:430px; margin:0;}

/* ---------- KPIs ---------- */
.kpi{background:#fff; border:1px solid var(--line); border-radius:12px; padding:22px 24px 20px 24px; height:100%;}
.kpi-ico{width:44px; height:44px; border-radius:50%; background:var(--red-soft); color:var(--red); display:flex; align-items:center; justify-content:center;}
.kpi-label{font-size:15.5px; font-weight:600; margin-top:16px; color:var(--ink);}
.kpi-value{font-size:44px; font-weight:700; line-height:1.1; margin:2px 0 6px 0; color:var(--ink);}
.kpi-sub{font-size:12.5px; color:var(--muted); display:flex; align-items:center; gap:8px;}
.kpi-sub.delta{color:var(--muted);}
.kpi-sub.delta svg{color:var(--delta-up);}

/* ---------- títulos ---------- */
.sec-title{font-size:26px; font-weight:600; margin:1.6rem 0 .4rem 0; padding:0; color:var(--ink);}
.page-head h2{font-size:28px; font-weight:700; margin:.4rem 0 .2rem 0; padding:0;}
.page-sub{color:var(--muted); font-size:14px; margin:0 0 1rem 0;}
[class*="st-key-link_"]{display:flex; justify-content:flex-end; margin-top:1.9rem;}
[class*="st-key-link_"] button{background:transparent; border:none; color:var(--red); font-weight:500; box-shadow:none; padding:.25rem .4rem;}
[class*="st-key-link_"] button:hover{background:var(--red-soft); color:var(--red);}

/* ---------- cards de notícia ---------- */
div[class*="st-key-newscard_"]{background:#fff; border:1px solid var(--line); border-radius:12px; padding:20px 22px 12px 22px; gap:.25rem; margin-bottom:.4rem;}
.chip{display:inline-block; background:var(--red-soft); color:var(--red); font-size:12.5px; font-weight:500; padding:4px 14px; border-radius:999px;}
.news-title{font-size:17px; font-weight:600; line-height:1.35; margin:12px 0 8px 0; color:var(--ink);}
.news-desc{font-size:13.5px; line-height:1.55; color:#6F6F74; margin:0 0 6px 0; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden;}
.src{display:flex; align-items:center; gap:10px; font-size:12px; color:#55555A; white-space:nowrap;}
.src-av{width:26px; height:26px; border-radius:50%; background:#0F0F10; color:#fff; font-size:10px; font-weight:700; display:flex; align-items:center; justify-content:center; flex:none;}
.src-div{width:1px; height:12px; background:#D9D6D4;}
.src-time{color:#9A9A9F;}
.ext{display:flex; justify-content:flex-end; color:var(--red);}
[class*="st-key-gen_"] button{background:transparent; border:none; color:var(--red); font-size:12.5px; font-weight:600; box-shadow:none; padding:.2rem .5rem; min-height:0;}
[class*="st-key-gen_"] button:hover{background:var(--red-soft); color:var(--red);}

/* ---------- botão principal (adicionar manualmente) ---------- */
[class*="st-key-add_manual"]{display:flex; justify-content:center; margin-top:1.4rem;}
button[kind="primary"], button[data-testid="stBaseButton-primary"]{background:var(--red-strong) !important; border:none !important; color:#fff !important; border-radius:8px; font-weight:600;}
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover{background:#8E1322 !important;}
[class*="st-key-add_manual"] button{min-width:290px; height:48px; font-size:14px; box-shadow:0 2px 6px rgba(164,23,42,.25);}

/* ---------- painéis, tabelas, estados ---------- */
div[class*="st-key-panel_"]{background:#fff; border:1px solid var(--line); border-radius:12px; padding:22px 24px; margin-bottom:1rem;}
.empty{background:#fff; border:1px dashed #D9D6D4; border-radius:12px; padding:28px; text-align:center; color:var(--muted); font-size:14px;}
.tbl-wrap{background:#fff; border:1px solid var(--line); border-radius:12px; overflow:auto;}
.tbl{width:100%; border-collapse:collapse; font-size:14px;}
.tbl th{text-align:left; font-weight:600; padding:12px 18px; color:var(--muted); font-size:13px; border-bottom:1px solid var(--line);}
.tbl td{padding:12px 18px; border-bottom:1px solid #F2F0EE;}
.tbl tr:last-child td{border-bottom:none;}
.meta{font-size:13.5px; color:var(--muted); margin-bottom:.6rem;}
.meta b{color:var(--ink); font-weight:600;}
.stepper{display:flex; flex-wrap:wrap; gap:10px; margin:.2rem 0 .8rem 0;}
.step{display:flex; align-items:center; gap:8px; font-size:12.5px; color:#9A9A9F; padding:5px 12px; border-radius:999px; background:#F1EFED;}
.step .dot{width:8px; height:8px; border-radius:50%; background:#CFCBC8;}
.step.done{color:#55555A;} .step.done .dot{background:#55555A;}
.step.now{background:var(--red-soft); color:var(--red); font-weight:600;} .step.now .dot{background:var(--red);}

/* ---------- inputs e abas ---------- */
div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] > div{background:#fff; border-radius:8px;}
div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within{border-color:var(--red) !important;}
span[data-baseweb="tag"]{background:var(--red-soft) !important; color:var(--red) !important;}
span[data-baseweb="tag"] svg{fill:var(--red);}
button[data-baseweb="tab"]{font-weight:500;}
button[data-baseweb="tab"][aria-selected="true"]{color:var(--red);}
[data-baseweb="tab-highlight"]{background:var(--red) !important;}
"""