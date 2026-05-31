"""Selçuk-AI Streamlit UI helpers.

The helpers in this module are intentionally presentation-only. They do not
touch retrieval, routing, ingestion, provider, or ChromaDB behavior.
"""

from __future__ import annotations

from html import escape
from typing import Any


APP_NAME = "Selçuk-AI"
APP_TAGLINE = "Üniversite Araştırma Asistanı"
PALETTE = {
    "background": "#121212",
    "surface": "#1f1f1f",
    "surface_soft": "#252525",
    "border": "#343a40",
    "text": "#e0e0e0",
    "muted": "#a7b0b8",
    "accent": "#00a8cc",
}

NAV_ITEMS = [
    ("chat", "Sohbet", "▣"),
    ("sources", "Veri Kaynakları", "◎"),
    ("dashboard", "Kontrol Paneli", "◫"),
    ("ai_tools", "YZ Araçları", "⚙"),
    ("admin", "Admin Paneli", "◈"),
    ("hakkinda", "Yardım", "?"),
]


def inject_selcuk_ai_theme(st) -> None:
    """Inject the final Selçuk-AI visual shell."""

    st.markdown(
        f"""
<style>
:root {{
    --selcuk-bg: {PALETTE["background"]};
    --selcuk-surface: {PALETTE["surface"]};
    --selcuk-surface-soft: {PALETTE["surface_soft"]};
    --selcuk-border: {PALETTE["border"]};
    --selcuk-text: {PALETTE["text"]};
    --selcuk-muted: {PALETTE["muted"]};
    --selcuk-accent: {PALETTE["accent"]};
}}

html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"] {{
    background: var(--selcuk-bg) !important;
    color: var(--selcuk-text) !important;
}}
[data-testid="stHeader"] {{
    background: rgba(18,18,18,0.86) !important;
    border-bottom: 1px solid rgba(255,255,255,0.06) !important;
    backdrop-filter: blur(12px);
}}
.block-container {{
    max-width: 1060px !important;
    padding-top: 1.8rem !important;
    padding-bottom: 8rem !important;
}}
section[data-testid="stSidebar"] {{
    background: #1d1d1f !important;
    border-right: 1px solid rgba(224,224,224,0.12) !important;
}}
section[data-testid="stSidebar"] .stTextInput input,
section[data-testid="stSidebar"] textarea {{
    background: #242424 !important;
    border: 1px solid rgba(224,224,224,0.15) !important;
    color: var(--selcuk-text) !important;
    border-radius: 12px !important;
}}
.selcuk-brand {{
    display: flex; gap: 12px; align-items: center;
    padding: 24px 4px 20px 4px; margin-bottom: 14px;
    border-bottom: 1px solid rgba(224,224,224,0.1);
}}
.selcuk-brand-icon {{
    width: 46px; height: 46px; border-radius: 14px;
    background: linear-gradient(135deg, var(--selcuk-accent), #007a95);
    color: #071114; display: flex; align-items: center; justify-content: center;
    font-size: 24px; font-weight: 900; box-shadow: 0 0 24px rgba(0,168,204,0.22);
}}
.selcuk-brand h1 {{
    margin: 0; color: #67ddf2; font-size: 2rem; line-height: 1; letter-spacing: -0.04em;
}}
.selcuk-brand p {{
    margin: 6px 0 0 0; color: var(--selcuk-muted); font-size: .78rem;
    text-transform: uppercase; letter-spacing: .08em; font-weight: 700;
}}
.nav-label {{
    color: #8d989f !important; font-size: .72rem !important;
    letter-spacing: .12em; text-transform: uppercase; font-weight: 800;
    margin: 18px 0 6px 4px !important;
}}
.selcuk-mini-item {{
    display: flex; align-items: center; gap: 8px; color: #c8d0d4;
    padding: 8px 10px; border-radius: 10px; font-size: .86rem;
    background: rgba(255,255,255,0.03); margin: 5px 0;
    overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
}}
.selcuk-topbar {{
    display: flex; align-items: center; justify-content: space-between; gap: 16px;
    padding: 0 0 18px 0; border-bottom: 1px solid rgba(224,224,224,0.14);
    margin-bottom: 34px;
}}
.selcuk-breadcrumb {{ color: var(--selcuk-muted); font-size: .95rem; }}
.selcuk-top-actions {{ display:flex; gap:10px; align-items:center; color: var(--selcuk-muted); }}
.selcuk-page-title h2 {{
    color: var(--selcuk-text); font-size: clamp(2rem, 4vw, 3.8rem);
    line-height: 1.04; margin: 0 0 10px 0; letter-spacing: -0.055em;
}}
.selcuk-page-title p {{ color: #c7ced3; font-size: 1.12rem; margin: 0; max-width: 820px; }}
.selcuk-card {{
    background: var(--selcuk-surface) !important;
    border: 1px solid rgba(224,224,224,0.12) !important;
    border-radius: 14px; padding: 20px;
    box-shadow: 0 16px 42px rgba(0,0,0,0.22);
}}
.selcuk-card h3 {{ margin-top: 0; color: var(--selcuk-text); }}
.selcuk-muted {{ color: var(--selcuk-muted); }}
.selcuk-badge {{
    display: inline-flex; align-items: center; gap: 6px;
    border: 1px solid rgba(0,168,204,.36); color: #77e8ff;
    background: rgba(0,168,204,.11); border-radius: 999px;
    padding: 4px 10px; font-size: .76rem; font-weight: 800; letter-spacing: .02em;
}}
.selcuk-badge-neutral {{
    border-color: rgba(224,224,224,.16); color: #cdd5d9; background: rgba(255,255,255,.04);
}}
[data-testid="stChatMessage"] {{
    background: transparent !important; padding: 10px 0 !important;
}}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {{
    color: var(--selcuk-text) !important;
}}
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {{
    border-left: 3px solid var(--selcuk-accent) !important;
    background: rgba(31,31,31,.86) !important;
    border-radius: 14px !important; padding: 16px 20px !important;
}}
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {{
    border: 1px solid rgba(224,224,224,0.16) !important;
    background: rgba(255,255,255,.035) !important;
    border-radius: 14px !important; padding: 16px 20px !important;
}}
[data-testid="stChatInput"] > div {{
    background: #1f1f1f !important;
    border: 1px solid rgba(0,168,204,.33) !important;
    border-radius: 16px !important; box-shadow: 0 0 0 1px rgba(0,168,204,.08);
}}
[data-testid="stChatInput"] textarea {{
    color: var(--selcuk-text) !important; font-size: 1rem !important;
}}
[data-testid="stChatInput"] button {{
    background: var(--selcuk-accent) !important; color: #041113 !important;
    border-radius: 12px !important;
}}
.stButton > button, .stDownloadButton > button {{
    border-radius: 12px !important;
    border: 1px solid rgba(224,224,224,.14) !important;
    background: #242424 !important; color: var(--selcuk-text) !important;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
    border-color: rgba(0,168,204,.62) !important;
    background: rgba(0,168,204,.13) !important; color: #aef4ff !important;
}}
.new-chat-btn > button {{
    background: var(--selcuk-accent) !important;
    color: #071114 !important; border: none !important; font-weight: 850 !important;
    min-height: 58px; font-size: 1rem !important;
}}
.selcuk-composer-tools {{
    background: rgba(31,31,31,.72); border: 1px solid rgba(224,224,224,.12);
    border-radius: 16px; padding: 12px 14px; margin: 22px 0 10px 0;
}}
.curator-footer {{
    color: #667278 !important;
    font-size: .78rem !important; text-align: center; padding-bottom: 8px;
}}
hr {{ border-color: rgba(224,224,224,0.1) !important; }}
</style>
""",
        unsafe_allow_html=True,
    )


def render_brand(st) -> None:
    st.markdown(
        f"""
<div class="selcuk-brand">
  <div class="selcuk-brand-icon">◈</div>
  <div>
    <h1>{APP_NAME}</h1>
    <p>{APP_TAGLINE}</p>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_topbar(st, current_page: str = "Sohbet") -> None:
    st.markdown(
        f"""
<div class="selcuk-topbar">
  <div class="selcuk-breadcrumb">Yeni Oturum <span style="opacity:.55">›</span> {escape(current_page)}</div>
  <div class="selcuk-top-actions"><span title="Bildirimler">◌</span><span title="Geçmiş">↺</span><span class="selcuk-badge selcuk-badge-neutral">P</span></div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_page_title(st, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
<div class="selcuk-page-title">
  <h2>{escape(title)}</h2>
  <p>{escape(subtitle)}</p>
</div>
""",
        unsafe_allow_html=True,
    )


def render_status_badges(st, badges: list[tuple[str, str]]) -> None:
    rendered = " ".join(
        f'<span class="selcuk-badge {escape(kind)}">{escape(label)}</span>'
        for label, kind in badges
    )
    st.markdown(f"<div style='margin: 12px 0 24px 0;'>{rendered}</div>", unsafe_allow_html=True)


def recent_user_questions(messages: list[dict[str, Any]], limit: int = 5) -> list[str]:
    questions = []
    for message in reversed(messages or []):
        if message.get("rol") == "user":
            text = " ".join(str(message.get("icerik", "")).split())
            if text:
                questions.append(text[:54] + ("…" if len(text) > 54 else ""))
        if len(questions) >= limit:
            break
    return questions


def session_source_label(source: Any | None) -> str:
    if not source:
        return "Geçici kaynak yok"
    label = getattr(source, "source_label", "") or getattr(source, "title", "") or "Geçici kaynak"
    status = getattr(source, "status", "")
    return f"{label} · {status}" if status else label


def route_badge_for_message(message: dict[str, Any]) -> str:
    if message.get("docs"):
        first = message["docs"][0]
        metadata = getattr(first, "metadata", {}) or {}
        source_type = str(metadata.get("source_type", "")).lower()
        if source_type in {"pdf", "pdf_url", "pasted_text", "url"} and metadata.get("session_source_id"):
            return "Geçici Kaynak"
        if source_type == "dynamic_dining_menu":
            return "Yemekhane Menüsü"
        if source_type or metadata.get("source_family"):
            return "RAG"
    if message.get("sources_checked"):
        return "Kaynak Kontrolü"
    return "Cevap"

