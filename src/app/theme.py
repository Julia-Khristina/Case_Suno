"""Tema visual compartilhado da interface Suno Asset.

Reproduz o mockup da tela inicial: sidebar escura com destaque vermelho,
barra superior branca, hero escuro, cards brancos e botão vermelho.
Todo o CSS fica aqui para que as telas só se preocupem com o conteúdo.
"""
from __future__ import annotations

import html
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

TZ = ZoneInfo("America/Sao_Paulo")

PAGES = [
    ("inicio", "Início", ":material/home:"),
    ("noticias", "Notícias", ":material/newspaper:"),
    ("materiais", "Materiais", ":material/description:"),
    ("configuracoes", "Configurações", ":material/settings:"),
]
SOURCES_CONFIG = Path("config/coleta_fontes.yaml")
_WEEKDAYS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
_MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
           "novembro", "dezembro"]


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
    "layers": '<path d="m12 2 10 5-10 5L2 7l10-5Z"/><path d="m2 17 10 5 10-5M2 12l10 5 10-5"/>',
    "sprout": '<path d="M7 20h10M12 20v-8M12 12c0-4 3-7 8-7 0 5-3 8-8 7ZM12 12C12 8.7 9.8 6 5 6c0 4.2 2.6 6.4 7 6Z"/>',
    "chart": '<path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 5-6"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "slides": '<rect x="3" y="4" width="14" height="16" rx="2"/><path d="M21 7v10M7 9h6M7 13h6"/>',
    "video": '<rect x="2" y="5" width="14" height="14" rx="2"/><path d="m16 10 6-3v10l-6-3"/>',
    "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5v14Z"/><path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "alert": '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/>',
}


def svg(name: str, size: int = 20, stroke: float = 1.8) -> str:
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


def data_extenso(now: datetime | None = None) -> str:
    """Ex.: "Sexta-feira, 17 de outubro de 2026"."""
    day = now or agora()
    return f"{_WEEKDAYS[day.weekday()].capitalize()}, {day.day} de {_MONTHS[day.month - 1]} de {day.year}"


def monitored_sources(path: Path = SOURCES_CONFIG) -> int | None:
    """Quantidade de fontes ativas na coleta diária (None se a configuração não puder ser lida)."""
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    except Exception:  # noqa: BLE001
        return None
    return sum(1 for fonte in data.get("fontes") or [] if fonte.get("ativa", True))


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
        total = monitored_sources()
        if total is not None:
            st.markdown(
                f'<div class="side-foot"><div class="side-foot-label">Fontes monitoradas</div>'
                f'<div class="side-foot-value">{total}</div>'
                '<div class="side-foot-sub">feeds financeiros ativos na coleta diária</div></div>',
                unsafe_allow_html=True,
            )


@lru_cache(maxsize=1)
def _sidebar_logo() -> str | None:
    """Logo oficial (asset/logo.png, o mesmo dos slides) na variante para fundo escuro; None se faltar o arquivo."""
    try:
        from src.rendering.playwright_renderer import logo_data_uri

        return logo_data_uri("fundo_escuro")
    except Exception:  # noqa: BLE001
        return None


def _brand_html() -> str:
    logo = _sidebar_logo()
    if logo:
        return f'<div class="brand"><img class="brand-logo" src="{logo}" alt="Suno Asset"/></div>'
    return (
        '<div class="brand"><div class="brand-row"><span class="bk l"></span>'
        '<span class="brand-name">SUNO</span><span class="bk r"></span></div>'
        '<div class="brand-sub">ASSET</div></div>'
    )


# ---------------------------------------------------------------- componentes
def topbar() -> None:
    texto, icone = saudacao()
    st.markdown(
        f'<div class="topbar"><div class="today">{esc(data_extenso())}</div><div class="greet">'
        f'<span class="greet-ico">{svg(icone, 20)}</span><span>{esc(texto)}</span></div></div>',
        unsafe_allow_html=True,
    )


def hero() -> None:
    texto, icone = saudacao()
    st.markdown(
        '<div class="hero">'
        f'<div class="hero-ico">{svg(icone, 34, 1.6)}</div>'
        f'<h1>{esc(texto)}<b class="bang">!</b></h1>'
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


STATUS_TONE = {
    "aprovado": "ok", "aprovado_pelo_juiz": "ok", "editado": "info", "aguardando_revisao": "warn", "gerando": "info",
    "em_andamento": "info", "rejeitado": "bad", "reprovado_pelo_juiz": "bad", "reprovado_nas_metricas": "bad",
    "falhou": "bad", "bloqueado_por_termos_pendentes": "warn", "pendente": "warn", "sem_definicao": "mute",
    "autoria_manual": "ok",
}


def humanize(value) -> str:
    """"aguardando_revisao" vira "Aguardando revisão" (acentos dos termos mais comuns do sistema)."""
    text = str(value or "—").replace("_", " ").strip()
    for plain, accented in (("revisao", "revisão"), ("metricas", "métricas"), ("definicao", "definição"), ("conclusao", "conclusão"), ("medio", "médio"),
                            ("intermediario", "intermediário"), ("avancado", "avançado")):
        text = text.replace(plain, accented)
    return text[:1].upper() + text[1:]


def status_chip(value, label: str | None = None) -> str:
    tone = STATUS_TONE.get(str(value or ""), "mute")
    return f'<span class="st-chip {tone}">{esc(label or humanize(value))}</span>'


def stepper(steps: list[str], current: int) -> None:
    """Trilha de etapas: concluídas, atual e próximas."""
    items = []
    for index, label in enumerate(steps):
        css = "done" if index < current else "now" if index == current else ""
        items.append(f'<span class="step {css}"><span class="dot"></span>{esc(label)}</span>')
    st.markdown(f'<div class="stepper">{"".join(items)}</div>', unsafe_allow_html=True)


def option_card_html(icon: str, title: str, subtitle: str = "", meta: str = "", badge: str = "") -> str:
    """Topo de card de escolha (notícia, nível, formato) no estilo dos cards da tela inicial."""
    sub = f'<div class="opt-sub">{esc(subtitle)}</div>' if subtitle else ""
    meta_html = f'<div class="opt-meta">{meta}</div>' if meta else ""
    return (f'<div class="opt-head"><div class="kpi-ico">{svg(icon, 20)}</div>{badge}</div>'
            f'<div class="opt-title">{esc(title)}</div>{sub}{meta_html}')


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
.brand img.brand-logo{width:176px; max-width:100%; height:auto; display:block; margin:6px auto 0 auto;}
.brand-row{display:flex; align-items:center; justify-content:center; gap:10px;}
.brand-name{color:#fff; font-weight:500; font-size:22px; letter-spacing:.42em; margin-right:-.42em;}
.bk{display:inline-block; width:9px; height:30px;}
.bk.l{border-left:4px solid #D81B2C; border-radius:100% 0 0 100% / 50% 0 0 50%;}
.bk.r{border-right:4px solid #D81B2C; border-radius:0 100% 100% 0 / 0 50% 50% 0;}
.brand-sub{color:#fff; font-size:10px; letter-spacing:.5em; margin-top:2px; margin-right:-.5em;}
[data-testid="stSidebar"] [class*="st-key-nav"]{width:100%;}
[data-testid="stSidebar"] [class*="st-key-nav"] button{width:100%; justify-content:flex-start; gap:12px; background:transparent; border:none; color:#C9C9CE;
  padding:.72rem 1rem; border-radius:10px; font-weight:500; box-shadow:none; transition:background .15s, color .15s;}
[data-testid="stSidebar"] [class*="st-key-nav"] button > div{justify-content:flex-start; gap:12px; width:100%;}
[data-testid="stSidebar"] [class*="st-key-nav"] button p{font-size:14px; font-weight:500;}
[data-testid="stSidebar"] [class*="st-key-nav"] button [data-testid="stIconMaterial"]{color:#8F8F95;}
[data-testid="stSidebar"] [class*="st-key-nav"] button:hover{background:rgba(255,255,255,.06); color:#fff;}
[data-testid="stSidebar"] [class*="st-key-navactive_"] button, [data-testid="stSidebar"] [class*="st-key-navactive_"] button:hover{background:linear-gradient(90deg,rgba(179,20,31,.95),rgba(143,23,34,.85)); color:#fff;
  box-shadow:0 6px 18px rgba(179,20,31,.28);}
[data-testid="stSidebar"] [class*="st-key-navactive_"] button [data-testid="stIconMaterial"]{color:#fff;}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"]{color:#8d8d92;}
.side-foot{position:relative; z-index:1; margin:2.4rem .2rem 0 .2rem; padding:16px 16px 14px 16px; border-radius:12px;
  background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.08);}
.side-foot-label{color:#A5A5AB; font-size:12px; font-weight:500;}
.side-foot-value{color:#fff; font-size:26px; font-weight:700; line-height:1.2; margin-top:2px;}
.side-foot-sub{color:#7E7E84; font-size:11.5px; line-height:1.4; margin-top:2px;}

/* ---------- barra superior ---------- */
.topbar{margin:0 -2rem 1.6rem -2rem; height:64px; background:#fff; border-bottom:1px solid #E6E3E1; box-shadow:0 1px 3px rgba(0,0,0,.04);
  display:flex; align-items:center; justify-content:space-between; gap:18px; padding:0 2.2rem;}
.today{font-size:13.5px; color:var(--muted); font-weight:500;}
.greet{display:flex; align-items:center; gap:8px; font-size:13.5px; font-weight:600; color:var(--ink);
  background:var(--bg); border:1px solid var(--line); border-radius:999px; padding:6px 14px 6px 10px;}
.greet-ico{color:var(--red); display:flex;}

/* ---------- hero ---------- */
.hero{position:relative; overflow:hidden; background:linear-gradient(135deg,#0B0B0C 0%,#1B1B1D 55%,#0F0F10 100%); border-radius:16px; padding:36px 40px 40px 40px; margin-bottom:1.6rem;
  box-shadow:0 10px 30px rgba(14,14,16,.18);}
.hero::before{content:""; position:absolute; right:60px; top:-120px; width:360px; height:360px; border-radius:50%; pointer-events:none;
  background:radial-gradient(circle, rgba(196,22,42,.28) 0%, transparent 70%);}
.hero::after{content:""; position:absolute; right:-170px; top:-10px; width:640px; height:640px; border:2px solid #C4162A; border-radius:50%; pointer-events:none;}
.hero-ico{color:#E0202F; display:flex; margin-bottom:6px;}
.hero h1{color:#fff !important; font-size:44px; font-weight:700; margin:0 0 14px 0; padding:0; letter-spacing:-.015em; line-height:1.15;}
.hero h1, .hero h1 *{color:#fff !important;}
.hero h1 .bang{color:#E0202F !important; font-weight:700;}
.hero p{color:#D9D9DD; font-size:15px; line-height:1.6; max-width:470px; margin:0;}

/* ---------- KPIs ---------- */
.kpi{background:#fff; border:1px solid var(--line); border-radius:14px; padding:22px 24px 20px 24px; height:100%;
  box-shadow:0 1px 2px rgba(16,16,20,.04); transition:box-shadow .2s, transform .2s, border-color .2s;}
.kpi:hover{box-shadow:0 10px 24px rgba(16,16,20,.08); transform:translateY(-2px); border-color:#F0D3D5;}
.kpi-ico{width:44px; height:44px; border-radius:12px; background:var(--red-soft); color:var(--red); display:flex; align-items:center; justify-content:center;}
.kpi-label{font-size:14.5px; font-weight:600; margin-top:16px; color:#3A3A40;}
.kpi-value{font-size:44px; font-weight:700; line-height:1.1; margin:4px 0 8px 0; color:var(--ink); letter-spacing:-.02em;}
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
div[class*="st-key-newscard_"]{background:#fff; border:1px solid var(--line); border-radius:14px; padding:20px 22px 14px 22px; gap:.3rem; margin-bottom:.6rem;
  box-shadow:0 1px 2px rgba(16,16,20,.04); transition:box-shadow .2s, border-color .2s;}
div[class*="st-key-newscard_"]:hover{box-shadow:0 10px 24px rgba(16,16,20,.08); border-color:#F0D3D5;}
.chip{display:inline-block; background:var(--red-soft); color:var(--red); font-size:12px; font-weight:600; padding:4px 12px; border-radius:999px;}
.news-title{font-size:17px; font-weight:700; line-height:1.38; margin:12px 0 8px 0; color:var(--ink);
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; min-height:2.76em;}
.news-desc{font-size:13.5px; line-height:1.55; color:#6F6F74; margin:0 0 4px 0; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; min-height:4.65em;}
.news-rule{height:1px; background:#F1EEEC; margin:4px 0 2px 0;}
.src{display:flex; align-items:center; gap:10px; font-size:12.5px; color:#3A3A40; white-space:nowrap; overflow:hidden;}
.src-av{width:28px; height:28px; border-radius:50%; background:#16161A; color:#fff; font-size:10.5px; font-weight:700; display:flex; align-items:center; justify-content:center; flex:none;}
.src-name{font-weight:600; overflow:hidden; text-overflow:ellipsis;}
.src-div{width:1px; height:12px; background:#D9D6D4; flex:none;}
.src-time{color:#9A9A9F; flex:none;}
[class*="st-key-gen_"]{display:flex; justify-content:flex-end;}
[class*="st-key-gen_"] button{background:transparent; border:none; color:var(--red); font-size:13px; font-weight:600; box-shadow:none; padding:.3rem .7rem; min-height:0; white-space:nowrap;}
[class*="st-key-gen_"] button > div{flex-direction:row-reverse; gap:6px;}
[class*="st-key-gen_"] button p{white-space:nowrap;}
[class*="st-key-gen_"] button:hover{background:var(--red-soft); color:var(--red);}
[class*="st-key-cmp_"] label p{font-size:13px; color:#55555A;}
div[class*="st-key-newscard_"][class*="_pauta_"]{border-color:#F0D3D5; box-shadow:inset 4px 0 0 var(--red), 0 1px 2px rgba(16,16,20,.04);}
.chips-row{display:flex; flex-wrap:wrap; gap:8px;}
.chip.pauta-chip{background:var(--red); color:#fff;} .chip.pauta-chip.mute{background:#F1EFED; color:#6B6B70;}
.pauta-list{margin:6px 0 4px 0; border:1px solid #F1EEEC; border-radius:10px; background:#FCFBFA;}
.pauta-row{padding:9px 12px; border-bottom:1px solid #F1EEEC;} .pauta-row:last-child{border-bottom:none;}
.pauta-title{font-size:12.5px; color:#55555A; margin:4px 0 0 38px; display:-webkit-box; -webkit-line-clamp:1;
  -webkit-box-orient:vertical; overflow:hidden;}
[class*="st-key-cmpgen_"] button{white-space:nowrap; border-radius:8px;}

/* ---------- diálogo ---------- */
div[role="dialog"]{border-radius:16px !important;}
div[role="dialog"] h2{font-weight:700; letter-spacing:-.01em;}
div[role="dialog"] label p{font-weight:600; color:#3A3A40;}
div[role="dialog"] div[data-baseweb="input"], div[role="dialog"] div[data-baseweb="textarea"]{background:#F7F6F5; border:1px solid var(--line);}
[data-testid="stFileUploaderDropzone"]{background:#F7F6F5; border:1px dashed #D9D6D4; border-radius:10px;}

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

/* ---------- materiais: cards de escolha, chips de estado, painéis ---------- */
div[class*="st-key-opt_"]{background:#fff; border:1px solid var(--line); border-radius:14px; padding:20px 22px 16px 22px; gap:.4rem; height:100%;
  box-shadow:0 1px 2px rgba(16,16,20,.04); transition:box-shadow .2s, border-color .2s, transform .2s;}
div[class*="st-key-opt_"]:hover{box-shadow:0 10px 24px rgba(16,16,20,.08); border-color:#F0D3D5; transform:translateY(-2px);}
.opt-head{display:flex; align-items:center; justify-content:space-between; gap:10px;}
.opt-title{font-size:16.5px; font-weight:700; line-height:1.38; color:var(--ink); margin-top:12px;
  display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden;}
.opt-sub{font-size:13px; color:var(--muted); line-height:1.5; margin-top:4px;}
.opt-meta{display:flex; flex-wrap:wrap; align-items:center; gap:8px 14px; font-size:12.5px; color:#55555A; margin-top:10px;}
.opt-meta .m{display:inline-flex; align-items:center; gap:6px;}
.opt-meta svg{color:#9A9A9F;}
div[class*="st-key-opt_"] button{border-radius:8px; font-weight:600; border:1px solid #EAD3D5; color:var(--red); background:#fff;}
div[class*="st-key-opt_"] button:hover{background:var(--red-soft); border-color:var(--red); color:var(--red);}
div[class*="st-key-opt_"] button:disabled{color:#A5A5AB; border-color:var(--line); background:#FAFAF9;}
.st-chip{display:inline-flex; align-items:center; font-size:12px; font-weight:600; padding:4px 11px; border-radius:999px; white-space:nowrap;}
.st-chip.ok{background:#E7F5EC; color:#1E7A43;} .st-chip.warn{background:#FFF4DB; color:#8A5A00;}
.st-chip.bad{background:var(--red-soft); color:var(--red);} .st-chip.info{background:#E9F0FB; color:#2350A0;}
.st-chip.mute{background:#F1EFED; color:#6B6B70;}
.chips{display:flex; flex-wrap:wrap; gap:8px; margin:.2rem 0 .6rem 0;}
.detail-head{background:#fff; border:1px solid var(--line); border-radius:14px; padding:20px 24px; margin-bottom:1rem; position:relative; overflow:hidden;}
.detail-head::before{content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--red);}
.detail-kicker{font-size:12px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:var(--red);}
.detail-title{font-size:22px; font-weight:700; color:var(--ink); line-height:1.3; margin:4px 0 10px 0;}
.panel-title{font-size:15px; font-weight:700; color:var(--ink); margin:0 0 .3rem 0; display:flex; align-items:center; gap:8px;}
.panel-title svg{color:var(--red);}
[class*="st-key-back_"] button{background:transparent; border:none; color:var(--red); font-weight:600; box-shadow:none; padding:.25rem .5rem;}
[class*="st-key-back_"] button:hover{background:var(--red-soft); color:var(--red);}
div[class*="st-key-panel_"] [data-testid="stExpander"]{border:1px solid var(--line); border-radius:10px; background:#FCFBFA;}
.slide-row{padding:10px 0; border-bottom:1px solid #F1EEEC;} .slide-row:last-child{border-bottom:none;}
.slide-n{display:inline-flex; width:24px; height:24px; border-radius:50%; background:var(--red); color:#fff; font-size:12px; font-weight:700;
  align-items:center; justify-content:center; margin-right:8px;}
.slide-t{font-weight:700; color:var(--ink);} .slide-r{font-size:12px; color:var(--muted); margin-left:6px;}
.slide-b{font-size:13.5px; color:#55555A; line-height:1.55; margin:4px 0 0 32px;}

div[class*="st-key-opt_"] [data-testid="stMarkdown"], div[class*="st-key-term_"] [data-testid="stMarkdown"]{padding-bottom:1rem;}
h1, h2, h3, h4, h5, h6, [data-testid="stHeading"] *{font-family:'Plus Jakarta Sans',system-ui,-apple-system,'Segoe UI',sans-serif !important; letter-spacing:-.01em;}
div[class*="st-key-panel_conteudo"] h1{font-size:28px; line-height:1.25; font-weight:800;}
div[class*="st-key-panel_conteudo"] h2{font-size:21px; font-weight:700; margin-top:.6rem;}
div[class*="st-key-panel_conteudo"] h3, div[class*="st-key-panel_conteudo"] h4{font-size:17px; font-weight:700;}
div[class*="st-key-panel_conteudo"] p, div[class*="st-key-panel_conteudo"] li{font-size:15px; line-height:1.7; color:#2A2A30;}
div[class*="st-key-panel_conteudo"] blockquote{border-left:3px solid var(--red); background:#FCF6F6; padding:.4rem 1rem; border-radius:0 8px 8px 0;}

/* ---------- glossário ---------- */
div[class*="st-key-term_"]{background:#fff; border:1px solid var(--line); border-radius:12px; padding:16px 20px; gap:.2rem; margin-bottom:.5rem;}
.term-top{display:flex; flex-wrap:wrap; align-items:center; gap:8px;}
.term-name{font-size:16px; font-weight:700; color:var(--ink); margin-right:4px;}
.term-def{font-size:13.5px; color:#55555A; line-height:1.55; margin-top:8px;}
.term-def.none{color:#9A9A9F; font-style:italic;}
.term-src{font-size:12px; color:#9A9A9F; margin-top:8px;}
.term-src a{color:var(--red); text-decoration:none;}
.term-var{font-size:12px; color:var(--muted); margin-top:4px;}

/* ---------- inputs e abas ---------- */
div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] > div{background:#fff; border-radius:8px;}
div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within{border-color:var(--red) !important;}
span[data-baseweb="tag"]{background:var(--red-soft) !important; color:var(--red) !important;}
span[data-baseweb="tag"] svg{fill:var(--red);}
button[data-baseweb="tab"]{font-weight:500;}
button[data-baseweb="tab"][aria-selected="true"]{color:var(--red);}
[data-baseweb="tab-highlight"]{background:var(--red) !important;}
"""