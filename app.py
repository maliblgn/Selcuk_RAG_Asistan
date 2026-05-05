import streamlit as st
import os
import tempfile
import logging
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rag_engine import (
    KnowledgeBaseUnavailableError,
    LIVE_INDEX_UNAVAILABLE_MESSAGE,
    MAX_CHAT_HISTORY_CHARS,
    SelcukRAGEngine,
    is_chroma_collection_error,
    is_long_inventory_answer,
    sanitize_chat_history,
    trim_text_for_prompt,
)
from check_chroma_health import check_chroma_health
from web_scraper import WebScraper, ScraperConfig, parse_urls_from_text

# .env dosyasından ortam değişkenlerini yükle
load_dotenv()


def load_streamlit_secrets_to_env():
    """Streamlit Cloud secrets degerlerini os.environ icine guvenli sekilde aktar."""
    for key in ("GROQ_API_KEY", "ADMIN_PASSWORD"):
        if os.environ.get(key):
            os.environ[key] = os.environ[key].strip().strip('"').strip("'")
            continue
        try:
            value = st.secrets.get(key)
        except Exception:
            value = None
        if value:
            os.environ[key] = str(value).strip().strip('"').strip("'")


load_streamlit_secrets_to_env()

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def build_prompt_chat_history(messages, max_pairs=3, per_message_chars=800):
    """Prompt icin son sohbet gecmisini kisa ve guvenli bicimde uret."""
    safe_messages = []
    for message in (messages or [])[-(max_pairs * 2):]:
        role = message.get("rol", "")
        content = str(message.get("icerik", "") or "")
        if is_long_inventory_answer(content):
            content = "[Onceki mesajda kaynak envanteri listelendi; detaylar prompttan cikarildi.]"
        else:
            content = trim_text_for_prompt(content, per_message_chars)
        safe_messages.append(f"{role}: {content}")
    return sanitize_chat_history(
        "\n".join(safe_messages),
        max_chars=MAX_CHAT_HISTORY_CHARS,
    )

# ─────────────────── SAYFA AYARLARI ───────────────────
st.set_page_config(page_title="Selçuk RAG Asistanı", page_icon="🎓", layout="centered")

# ══════════════════════════════════════════════════════════
#  CURATOR AI – MEGA CSS
# ══════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ─── Google Font ─── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ─── Global Reset ─── */
*, *::before, *::after { box-sizing: border-box; }
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: #E2E8F0;
}

/* ─── Ana Arka Plan ─── */
[data-testid="stAppViewContainer"] {
    background: #0B0D14 !important;
}
[data-testid="stHeader"] {
    background: transparent !important;
    border-bottom: none !important;
}

/* ─── Sidebar Toggle Butonları (her zaman görünür) ─── */
[data-testid="stSidebarCollapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
    position: fixed !important;
    top: 12px !important;
    left: 12px !important;
    z-index: 999999 !important;
}
[data-testid="stSidebarCollapsedControl"] * {
    visibility: visible !important;
    opacity: 1 !important;
    display: inherit !important;
}
[data-testid="stSidebarCollapsedControl"] button {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
    background: rgba(17, 20, 34, 0.95) !important;
    border: 1px solid rgba(59, 130, 246, 0.25) !important;
    border-radius: 10px !important;
    color: #94A3B8 !important;
    padding: 8px !important;
    backdrop-filter: blur(8px) !important;
    transition: all 0.2s ease !important;
    cursor: pointer !important;
    width: 36px !important;
    height: 36px !important;
    align-items: center !important;
    justify-content: center !important;
}
[data-testid="stSidebarCollapsedControl"] button:hover {
    background: rgba(59, 130, 246, 0.2) !important;
    border-color: rgba(59, 130, 246, 0.5) !important;
    color: #60A5FA !important;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2) !important;
}
/* Sidebar içindeki collapse (kapat) butonu */
button[data-testid="stSidebarCollapseButton"] {
    background: transparent !important;
    border: none !important;
    color: #64748B !important;
}
button[data-testid="stSidebarCollapseButton"]:hover {
    color: #94A3B8 !important;
}

/* ─── Sidebar ─── */
section[data-testid="stSidebar"] {
    background: #111422 !important;
    border-right: 1px solid rgba(59, 130, 246, 0.08) !important;
    padding-top: 0 !important;
}
section[data-testid="stSidebar"] > div:first-child {
    padding-top: 0 !important;
}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    font-size: 0.88rem;
}

/* ─── Sidebar Logo Alanı ─── */
.sidebar-logo {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 24px 8px 20px 8px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 16px;
}
.sidebar-logo .logo-icon {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    background: linear-gradient(135deg, #3B82F6, #8B5CF6);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    flex-shrink: 0;
}
.sidebar-logo .logo-text h3 {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 700;
    color: #F1F5F9;
    letter-spacing: -0.02em;
}
.sidebar-logo .logo-text span {
    font-size: 0.65rem;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 600;
}

/* ─── Sidebar Nav Etiketleri ─── */
.nav-label {
    font-size: 0.65rem !important;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #475569 !important;
    font-weight: 600;
    margin-top: 20px;
    margin-bottom: 4px;
    padding-left: 4px;
}

/* ─── Sidebar Alt Profil ─── */
.sidebar-profile {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 16px 8px 12px 8px;
    margin-top: 20px;
    border-top: 1px solid rgba(255,255,255,0.06);
}
.sidebar-profile .profile-icon {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: #1E293B;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
}
.sidebar-profile .profile-text h4 {
    margin: 0;
    font-size: 0.85rem;
    font-weight: 600;
    color: #F1F5F9;
}
.sidebar-profile .profile-text span {
    font-size: 0.7rem;
    color: #64748B;
}

/* ─── Sidebar Yükleme Kartları ─── */
.upload-card {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(59, 130, 246, 0.1);
    border-radius: 14px;
    padding: 16px 14px;
    margin: 8px 0;
}
.upload-card .card-title {
    font-size: 0.78rem;
    color: #94A3B8;
    text-align: center;
    margin-bottom: 10px;
}
.upload-card .card-icon {
    text-align: center;
    font-size: 2rem;
    margin-bottom: 6px;
}

/* ─── New Chat Butonu ─── */
section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]:first-of-type {
    border-radius: 12px !important;
}

/* ─── Genel Buton Stili ─── */
.stButton > button {
    border-radius: 12px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    transition: all 0.2s ease !important;
    border: 1px solid rgba(59,130,246,0.15) !important;
    background: rgba(59,130,246,0.08) !important;
    color: #CBD5E1 !important;
}
.stButton > button:hover {
    background: rgba(59,130,246,0.2) !important;
    border-color: rgba(59,130,246,0.35) !important;
    color: #F1F5F9 !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(59,130,246,0.15) !important;
}

/* ─── New Chat özel (sidebar'daki ilk buton) ─── */
.new-chat-btn > button {
    background: linear-gradient(135deg, #3B82F6, #2563EB) !important;
    color: #fff !important;
    border: none !important;
    font-weight: 600 !important;
    font-size: 0.92rem !important;
    padding: 10px 0 !important;
    border-radius: 14px !important;
    letter-spacing: -0.01em;
}
.new-chat-btn > button:hover {
    background: linear-gradient(135deg, #60A5FA, #3B82F6) !important;
    color: #fff !important;
    box-shadow: 0 6px 20px rgba(59,130,246,0.35) !important;
    transform: translateY(-2px);
}

/* ─── URL Tara Butonu ─── */
.url-scan-btn > button {
    background: transparent !important;
    border: 1px solid rgba(59,130,246,0.3) !important;
    color: #60A5FA !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    font-size: 0.72rem !important;
    letter-spacing: 0.08em;
}
.url-scan-btn > button:hover {
    background: rgba(59,130,246,0.1) !important;
    border-color: #3B82F6 !important;
}

/* ─── Sisteme Öğret Butonu ─── */
.teach-btn > button {
    background: rgba(59,130,246,0.15) !important;
    border: 1px solid rgba(59,130,246,0.25) !important;
    color: #93C5FD !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
}
.teach-btn > button:hover {
    background: rgba(59,130,246,0.25) !important;
}

/* ─── Karşılama Ekranı ─── */
.welcome-container {
    text-align: center;
    padding: 40px 20px 20px 20px;
    max-width: 720px;
    margin: 0 auto;
}
.welcome-wave {
    font-size: 3.2rem;
    margin-bottom: 16px;
    display: block;
    animation: wave-anim 2.5s ease-in-out infinite;
}
@keyframes wave-anim {
    0%, 100% { transform: rotate(0deg); }
    15% { transform: rotate(14deg); }
    30% { transform: rotate(-8deg); }
    40% { transform: rotate(14deg); }
    50% { transform: rotate(-4deg); }
    60% { transform: rotate(10deg); }
    70% { transform: rotate(0deg); }
}
.welcome-title {
    font-size: 2.1rem;
    font-weight: 800;
    color: #F1F5F9;
    margin-bottom: 12px;
    letter-spacing: -0.03em;
    line-height: 1.2;
}
.welcome-subtitle {
    font-size: 0.95rem;
    color: #64748B;
    font-style: italic;
    margin-bottom: 40px;
    line-height: 1.5;
}

/* ─── Öneri Kartları (Karşılama) ─── */
.suggestion-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    max-width: 680px;
    margin: 0 auto 30px auto;
}

/* ─── Mobil Uyumluluk ─── */
@media (max-width: 768px) {
    .suggestion-grid {
        grid-template-columns: 1fr;
    }
    .welcome-title {
        font-size: 1.5rem !important;
    }
    .welcome-subtitle {
        font-size: 0.85rem !important;
    }
    .sidebar-logo {
        padding: 16px 8px 14px 8px;
    }
}

/* Streamlit butonlarını kart görünümüne dönüştür */
.card-btn > button {
    background: rgba(20, 27, 45, 0.7) !important;
    border: 1px solid rgba(59, 130, 246, 0.1) !important;
    border-radius: 16px !important;
    padding: 20px 18px !important;
    text-align: left !important;
    min-height: 90px !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: flex-start !important;
    justify-content: center !important;
    gap: 6px !important;
    font-size: 0.88rem !important;
    color: #CBD5E1 !important;
    line-height: 1.4 !important;
    transition: all 0.25s ease !important;
}
.card-btn > button:hover {
    background: rgba(30, 41, 59, 0.9) !important;
    border-color: rgba(59, 130, 246, 0.3) !important;
    transform: translateY(-3px) !important;
    box-shadow: 0 8px 25px rgba(0,0,0,0.3), 0 0 0 1px rgba(59,130,246,0.15) !important;
}

/* ─── Chat Mesaj Balonları ─── */
[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
    padding: 12px 0 !important;
}

/* Kullanıcı mesajı */
[data-testid="stChatMessage"][data-testid*="user"],
div[class*="stChatMessage"]:has(img[alt*="user"]),
div[class*="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: rgba(30, 41, 59, 0.6) !important;
    border: 1px solid rgba(59, 130, 246, 0.12) !important;
    border-radius: 16px !important;
    padding: 16px 20px !important;
    margin: 8px 0 !important;
}

/* Asistan mesajı */
div[class*="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background: transparent !important;
    border: none !important;
    border-left: 3px solid rgba(59, 130, 246, 0.3) !important;
    border-radius: 0 !important;
    padding: 12px 20px !important;
    margin: 8px 0 !important;
}

/* ─── Chat Input ─── */
[data-testid="stChatInput"] {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}
[data-testid="stChatInput"] > div {
    background: #141B2D !important;
    border: 1px solid rgba(59, 130, 246, 0.15) !important;
    border-radius: 16px !important;
    padding: 4px 8px !important;
}
[data-testid="stChatInput"] textarea {
    background: transparent !important;
    color: #E2E8F0 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.92rem !important;
}
[data-testid="stChatInput"] button {
    background: linear-gradient(135deg, #3B82F6, #2563EB) !important;
    border: none !important;
    border-radius: 12px !important;
    color: white !important;
}
[data-testid="stChatInput"] button:hover {
    background: linear-gradient(135deg, #60A5FA, #3B82F6) !important;
}

/* ─── Takip Soru Önerileri (Pill Butonlar) ─── */
.followup-section {
    margin-top: 8px;
    margin-bottom: 16px;
}
.followup-label {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #64748B;
    font-weight: 600;
    margin-bottom: 10px;
}
.pill-btn > button {
    background: rgba(30, 41, 59, 0.5) !important;
    border: 1px solid rgba(100, 116, 139, 0.25) !important;
    border-radius: 24px !important;
    color: #94A3B8 !important;
    font-size: 0.82rem !important;
    padding: 8px 18px !important;
    font-weight: 500 !important;
}
.pill-btn > button:hover {
    background: rgba(59, 130, 246, 0.15) !important;
    border-color: rgba(59, 130, 246, 0.35) !important;
    color: #93C5FD !important;
}

/* ─── Expander (Yönetmelik Listesi) ─── */
[data-testid="stExpander"] {
    background: rgba(15, 23, 42, 0.4) !important;
    border: 1px solid rgba(59, 130, 246, 0.08) !important;
    border-radius: 12px !important;
}
[data-testid="stExpander"] summary {
    font-size: 0.85rem !important;
    font-weight: 500 !important;
}

/* ─── File Uploader ─── */
[data-testid="stFileUploader"] {
    background: transparent !important;
}
[data-testid="stFileUploader"] section {
    background: rgba(15, 23, 42, 0.4) !important;
    border: 1px dashed rgba(59, 130, 246, 0.2) !important;
    border-radius: 12px !important;
}
[data-testid="stFileUploader"] section:hover {
    border-color: rgba(59, 130, 246, 0.4) !important;
}

/* ─── Text Area (URL Input) ─── */
[data-testid="stTextArea"] textarea {
    background: rgba(15, 23, 42, 0.6) !important;
    border: 1px solid rgba(59, 130, 246, 0.12) !important;
    border-radius: 12px !important;
    color: #CBD5E1 !important;
    font-family: 'Inter', monospace !important;
    font-size: 0.82rem !important;
}
[data-testid="stTextArea"] textarea:focus {
    border-color: rgba(59, 130, 246, 0.4) !important;
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1) !important;
}

/* ─── Divider ─── */
[data-testid="stHorizontalRule"], hr {
    border-color: rgba(255, 255, 255, 0.04) !important;
}

/* ─── Alert / Success / Warning / Error ─── */
[data-testid="stAlert"] {
    border-radius: 12px !important;
    font-size: 0.85rem !important;
}

/* ─── Spinner ─── */
[data-testid="stSpinner"] {
    color: #60A5FA !important;
}

/* ─── Footer ─── */
.curator-footer {
    text-align: center;
    padding: 8px 0 4px 0;
    font-size: 0.72rem;
    color: #475569;
    pointer-events: none;
    margin-top: 4px;
}

/* ─── Scrollbar ─── */
::-webkit-scrollbar {
    width: 6px;
}
::-webkit-scrollbar-track {
    background: #0B0D14;
}
::-webkit-scrollbar-thumb {
    background: #1E293B;
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: #334155;
}

/* ─── Streamlit default gizle ─── */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
/* Deploy/Share/Menu butonlarını gizle — toolbar YAPISI'na dokunma */
[data-testid="stHeaderActionElements"] { display: none !important; }
[data-testid="stAppDeployButton"],
[data-testid="stStatusWidget"],
.stDeployButton,
[data-testid="stToolbar"] a[href],
[data-testid="stHeader"] a[href*="deploy"],
[data-testid="stHeader"] a[href*="share"] { display: none !important; }
/* Toolbar'ı TAMAMEN şeffaf ve arka planda bırak ama pointer-events'e dokunma!
   pointer-events:none sidebar toggle'ı da devre dışı bırakıyordu */
[data-testid="stToolbar"] {
    background: transparent !important;
}
/* Header görünür ve şeffaf kalır */
[data-testid="stHeader"] {
    background: transparent !important;
    border-bottom: none !important;
}
/* Sidebar toggle butonları her zaman erişilebilir */
[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarCollapsedControl"] *,
button[data-testid="stBaseButton-headerNoPadding"] {
    visibility: visible !important;
    display: flex !important;
    opacity: 1 !important;
    pointer-events: auto !important;
}

/* ─── Caption ─── */
.stCaption, [data-testid="stCaptionContainer"] {
    color: #475569 !important;
    font-size: 0.75rem !important;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────── API KEY KONTROLÜ ───────────────────
if not os.environ.get("GROQ_API_KEY"):
    st.error("⚠️ GROQ_API_KEY bulunamadı! Ortam değişkenlerini kontrol edin.")
    st.stop()

# ─────────────────── HAFIZA ───────────────────
if "mesajlar" not in st.session_state:
    st.session_state.mesajlar = []
if "yeni_dokumanlar" not in st.session_state:
    st.session_state.yeni_dokumanlar = []
if "oneriler" not in st.session_state:
    st.session_state.oneriler = []
if "web_hatalari" not in st.session_state:
    st.session_state.web_hatalari = []
if "aktif_sayfa" not in st.session_state:
    st.session_state.aktif_sayfa = "chat"
if "asistan_modu" not in st.session_state:
    st.session_state.asistan_modu = "Akademik Rehber"
if "admin_loggedin" not in st.session_state:
    st.session_state.admin_loggedin = False

# ─────────────────── MOTOR ───────────────────
@st.cache_resource
def get_engine():
    return SelcukRAGEngine()


# ══════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════
with st.sidebar:
    # ─── Logo ───
    st.markdown("""
    <div class="sidebar-logo">
        <div class="logo-icon">🎓</div>
        <div class="logo-text">
            <h3>Curator AI</h3>
            <span>Academic Research Lab</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ─── + New Chat Butonu ───
    st.markdown('<div class="new-chat-btn">', unsafe_allow_html=True)
    if st.button("＋  Yeni Sohbet", use_container_width=True, key="new_chat"):
        st.session_state.mesajlar = []
        st.session_state.yeni_dokumanlar = []
        st.session_state.oneriler = []
        st.session_state.web_hatalari = []
        st.session_state.aktif_sayfa = "chat"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # ─── Mode Selection ───
    st.markdown('<p class="nav-label">ASİSTAN MODU</p>', unsafe_allow_html=True)
    st.session_state.asistan_modu = st.radio(
        "Mod Seçimi",
        ["Akademik Rehber", "Kampüs Yaşamı", "Hızlı Arama"],
        index=["Akademik Rehber", "Kampüs Yaşamı", "Hızlı Arama"].index(st.session_state.asistan_modu),
        label_visibility="collapsed"
    )

    # ─── Navigation ───
    st.markdown('<p class="nav-label">NAVİGASYON</p>', unsafe_allow_html=True)

    if st.button("💬  Sohbet Geçmişi", use_container_width=True, key="nav_history"):
        st.session_state.aktif_sayfa = "chat"
        st.rerun()

    if st.button("ℹ️  Hakkında", use_container_width=True, key="nav_about"):
        st.session_state.aktif_sayfa = "hakkinda"
        st.rerun()

    # ─── Administration ───
    st.markdown('<p class="nav-label">YÖNETİM</p>', unsafe_allow_html=True)
    
    if st.button("🔑 Yönetici Paneli", use_container_width=True, key="nav_admin"):
        st.session_state.aktif_sayfa = "admin"
        st.rerun()



    # ─── Alt Profil ───
    st.markdown("""
    <div class="sidebar-profile">
        <div class="profile-icon">🏛️</div>
        <div class="profile-text">
            <h4>Selçuk Üni.</h4>
            <span>Yönetmelik Asistanı</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  ANA İÇERİK ALANI
# ══════════════════════════════════════════════════════════

# ─── Hakkında Sayfası ───
if st.session_state.aktif_sayfa == "hakkinda":
    st.markdown("""
    <div style="max-width:600px; margin:40px auto; text-align:center;">
        <div style="font-size:3rem; margin-bottom:16px;">ℹ️</div>
        <h2 style="color:#F1F5F9; font-weight:700; margin-bottom:8px;">Hakkında</h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    Bu asistan, Selçuk Üniversitesi yönetmeliklerini yapay zeka ile sorgulayan
    bir **RAG (Retrieval-Augmented Generation)** sistemidir.

    **🤖 Model:** Llama 3.1 8B (Groq)

    **📊 Embedding:** intfloat/multilingual-e5-small

    **🔍 Arama:** ChromaDB + MMR (Maximal Marginal Relevance)

    **📄 Desteklenen Kaynaklar:**
    - PDF yönetmelik belgeleri
    - Web sayfası içerikleri (otomatik tarama)
    - Dinamik oturum bazlı doküman ekleme

    **⚙️ Özellikler:**
    - Streaming yanıt (token token cevap)
    - Takip sorusu önerileri
    - Soru yeniden yazma (bağlam koruma)
    - Kaynak belirtme
    """)

    if st.button("← Sohbete Dön", key="back_from_about"):
        st.session_state.aktif_sayfa = "chat"
        st.rerun()



# ─── Admin Sayfası ───
elif st.session_state.aktif_sayfa == "admin":
    st.markdown("""
    <div style="max-width:600px; margin:40px auto; text-align:center;">
        <div style="font-size:3rem; margin-bottom:16px;">🔑</div>
        <h2 style="color:#F1F5F9; font-weight:700; margin-bottom:8px;">Yönetici Paneli</h2>
    </div>
    """, unsafe_allow_html=True)

    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_password:
        st.warning("Yönetici paneli devre dışı. Etkinleştirmek için ADMIN_PASSWORD ortam değişkenini tanımlayın.")
    elif not st.session_state.admin_loggedin:
        pw = st.text_input("Yönetici Şifresi", type="password")
        if st.button("Giriş"):
            if pw == admin_password:
                st.session_state.admin_loggedin = True
                st.rerun()
            else:
                st.error("Hatalı şifre!")
    else:
        if st.button("Çıkış Yap"):
            st.session_state.admin_loggedin = False
            st.rerun()
            
        st.markdown("### 📊 İstatistikler")
        col1, col2 = st.columns(2)
        with col1:
            try:
                from crawler_db import get_record_count
                crawled_count = get_record_count()
                st.metric("Toplam Taranan Sayfa", crawled_count)
            except Exception:
                st.metric("Toplam Taranan Sayfa", "Bilinmiyor")
        
        with col2:
            try:
                from data_ingestion import DB_DIR
                chroma_health = check_chroma_health(DB_DIR)
                vector_count = chroma_health.get("document_count", 0)
                st.metric("Toplam Vektör Sayısı", vector_count)
            except Exception:
                st.metric("Toplam Vektör Sayısı", "Bilinmiyor")

        st.markdown("### 👎 Düşük Kaliteli Sorgular")
        try:
            from data_ingestion import DB_DIR
            chroma_health = check_chroma_health(DB_DIR)
            st.markdown("### Index Durumu")
            st.caption(f"ChromaDB path: `{chroma_health.get('db_path')}`")
            hcol1, hcol2, hcol3 = st.columns(3)
            hcol1.metric("DB var", "Evet" if chroma_health.get("db_exists") else "Hayir")
            hcol2.metric("Collection", "Okunuyor" if chroma_health.get("collection_readable") else "Okunamiyor")
            hcol3.metric("Kaynak", chroma_health.get("unique_source_count", 0))
            if not chroma_health.get("ok"):
                st.warning(chroma_health.get("reason") or chroma_health.get("error") or "ChromaDB hazir degil.")
        except Exception as exc:
            logger.warning("Index durumu gosterilemedi: %s", exc)

        if os.path.exists("low_quality_queries.log"):
            with open("low_quality_queries.log", "r", encoding="utf-8") as f:
                content = f.read()
            st.text_area("Log Kayıtları", content, height=300)
            if st.button("Logları Temizle"):
                os.remove("low_quality_queries.log")
                st.rerun()
        else:
            st.info("Henüz olumsuz geri bildirim yok.")

# ─── Sohbet Sayfası (Ana Sayfa) ───
else:
    # ─── KARŞILAMA EKRANI ───
    if len(st.session_state.mesajlar) == 0:
        st.markdown("""
        <div class="welcome-container">
            <span class="welcome-wave">👋</span>
            <div class="welcome-title">
                Selçuk Üniversitesi Yönetmelik<br>Asistanı'na hoş geldiniz.
            </div>
            <div class="welcome-subtitle">
                "Size nasıl yardımcı olabilirim? Akademik mevzuat ve yönergeler hakkında her şeyi sorabilirsiniz."
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 4 Adet Öneri Kartı
        ornek_sorular = [
            ("☑️  Staj Muafiyeti\n📋 Staj muafiyet şartları nelerdir?", "Staj muafiyet şartları nelerdir?"),
            ("🎓  Çift Ana Dal\n📘 Çift ana dal nasıl yapılır?", "Çift ana dal programına başvuru şartları nelerdir?"),
            ("💰  Burs Başvuruları\n💳 Burs başvuru koşulları nelerdir?", "Burs başvuru koşulları nelerdir?"),
            ("📑  Diploma Eki\n📄 Diploma eki nedir?", "Diploma eki nedir ve nasıl düzenlenir?"),
        ]

        col1, col2 = st.columns(2)
        col3, col4 = st.columns(2)
        cols = [col1, col2, col3, col4]

        for i, (label, soru) in enumerate(ornek_sorular):
            with cols[i]:
                st.markdown('<div class="card-btn">', unsafe_allow_html=True)
                if st.button(label, use_container_width=True, key=f"ornek_{i}"):
                    st.session_state.ornek_soru = soru
                st.markdown('</div>', unsafe_allow_html=True)

    # ─── GEÇMİŞ MESAJLAR ───
    for idx, m in enumerate(st.session_state.mesajlar):
        with st.chat_message(m["rol"], avatar="🎓" if m["rol"] == "assistant" else "👤"):
            st.markdown(m["icerik"])
            
            if m["rol"] == "assistant":
                docs = m.get("docs", [])
                if docs:
                    with st.expander("📚 Kaynaklar", expanded=False):
                        for i, doc in enumerate(docs):
                            source_info = SelcukRAGEngine.build_source_metadata(doc)
                            source_url = source_info["url"]

                            st.markdown(f"**[{i+1}] {source_info['label']}**")
                            if source_info["article_label"]:
                                st.caption(source_info["article_label"])
                            if source_info["page"]:
                                st.caption(f"Sayfa: {source_info['page']}")
                            st.caption(doc.page_content[:200].replace("\n", " ") + "...")
                            if source_url:
                                st.markdown(f"[Kaynağa Git]({source_url})")
                            st.divider()

                # Feedback ve İndirme butonları
                col1, col2, col3, col4 = st.columns([1, 1, 3, 5])
                with col1:
                    if st.button("👍", key=f"up_{idx}", help="Beğen"):
                        st.toast("Geri bildiriminiz için teşekkürler!")
                with col2:
                    if st.button("👎", key=f"down_{idx}", help="Beğenme"):
                        with open("low_quality_queries.log", "a", encoding="utf-8") as f:
                            f.write(f"Soru: {m.get('soru', 'Bilinmiyor')}\nCevap: {m['icerik']}\nMode: {st.session_state.asistan_modu}\n---\n")
                        st.toast("Geri bildiriminiz kaydedildi.")
                with col3:
                    st.download_button(
                        label="📥 İndir (.md)",
                        data=f"# Soru: {m.get('soru', '')}\n\n## Cevap:\n{m['icerik']}",
                        file_name=f"Cevap_{idx}.md",
                        mime="text/markdown",
                        key=f"export_{idx}"
                    )

    # ─── TAKİP SORU ÖNERİLERİ ───
    if st.session_state.oneriler and len(st.session_state.mesajlar) > 0:
        st.markdown("""
        <div class="followup-section">
            <div class="followup-label">🔎 Bunları da sorabilirsiniz:</div>
        </div>
        """, unsafe_allow_html=True)

        oneri_cols = st.columns(len(st.session_state.oneriler))
        for i, oneri in enumerate(st.session_state.oneriler):
            with oneri_cols[i]:
                st.markdown('<div class="pill-btn">', unsafe_allow_html=True)
                if st.button(oneri, key=f"oneri_{i}", use_container_width=True):
                    st.session_state.ornek_soru = oneri
                    st.session_state.oneriler = []
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    # ─── KULLANICI GİRDİSİ ───
    kullanici_sorusu = st.chat_input("Selçuk Üniversitesi yönetmeliği hakkında bir soru sorun...")
    if "ornek_soru" in st.session_state:
        kullanici_sorusu = st.session_state.ornek_soru
        del st.session_state.ornek_soru

    if kullanici_sorusu:
        # Kullanıcı mesajını ekle
        st.session_state.mesajlar.append({"rol": "user", "icerik": kullanici_sorusu})
        with st.chat_message("user", avatar="👤"):
            st.markdown(kullanici_sorusu)

        with st.chat_message("assistant", avatar="🎓"):
            try:
                # 1. Sohbet geçmişi
                if SelcukRAGEngine.is_source_inventory_question(kullanici_sorusu):
                    cevap = SelcukRAGEngine.build_source_inventory_answer_from_db()
                    st.markdown(cevap)
                    st.session_state.mesajlar.append({
                        "rol": "assistant",
                        "icerik": cevap,
                        "soru": kullanici_sorusu,
                        "docs": []
                    })
                    st.session_state.oneriler = []
                    st.rerun()

                motor = get_engine()
                history = build_prompt_chat_history(st.session_state.mesajlar[:-1])

                # 2. Soru yeniden yazma (takip soruları için)
                with st.spinner("Soru analiz ediliyor..."):
                    yeniden_soru = motor.rewrite_query(kullanici_sorusu, history)

                # 3. Doküman getirme
                with st.spinner("Dökümanlar taranıyor..."):
                    docs = motor.retrieve(yeniden_soru, dynamic_docs=st.session_state.yeni_dokumanlar)
                    context = motor.format_context(docs)

                # 4. Streaming yanıt
                def token_generator():
                    for chunk in motor.stream_answer(yeniden_soru, context, history, mode=st.session_state.asistan_modu):
                        if hasattr(chunk, 'content'):
                            yield chunk.content
                        else:
                            yield str(chunk)

                cevap = st.write_stream(token_generator())

                st.session_state.mesajlar.append({
                    "rol": "assistant", 
                    "icerik": cevap,
                    "soru": kullanici_sorusu,
                    "docs": docs
                })

                # 5. Takip sorusu önerileri (arka planda)
                oneriler = motor.suggest_followups(kullanici_sorusu, cevap)
                st.session_state.oneriler = oneriler

                st.rerun()

            except Exception as e:
                error_msg = str(e).lower()
                safe_detail = str(e)
                groq_key = os.environ.get("GROQ_API_KEY", "")
                if groq_key:
                    safe_detail = safe_detail.replace(groq_key, "[GROQ_API_KEY]")

                if isinstance(e, KnowledgeBaseUnavailableError) or is_chroma_collection_error(e):
                    logger.error("ChromaDB/index hatasi: %s", e)
                    hata_mesaji = LIVE_INDEX_UNAVAILABLE_MESSAGE
                elif "rate_limit" in error_msg or "429" in error_msg or "rate limit" in error_msg:
                    logger.warning(f"Groq rate limit aşıldı: {e}")
                    hata_mesaji = "⏳ API istek limiti aşıldı. Lütfen **30 saniye** bekleyip tekrar deneyin."
                elif "authentication" in error_msg or "invalid_api_key" in error_msg or "unauthorized" in error_msg or "api_key" in error_msg or "401" in error_msg:
                    logger.error(f"API key hatası: {e}")
                    hata_mesaji = "🔑 API anahtarı geçersiz veya eksik. Lütfen `.env` dosyasındaki **GROQ_API_KEY** değerini kontrol edin."
                elif "connection" in error_msg or "timeout" in error_msg or "unreachable" in error_msg:
                    logger.error(f"Bağlantı hatası: {e}")
                    hata_mesaji = "🌐 Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edip tekrar deneyin."
                elif "groq" in error_msg or "chatgroq" in error_msg or "model" in error_msg:
                    logger.error(f"Groq/model hatasÄ±: {e}")
                    hata_mesaji = "⚠️ Yapay zeka modeli çağrılırken hata oluştu. Streamlit Secrets içindeki **GROQ_API_KEY** değerini ve Groq hesabı erişimini kontrol edin."
                else:
                    logger.error(f"RAG zinciri hatası: {e}")
                    hata_mesaji = "⚠️ Bir hata oluştu. Lütfen tekrar deneyin."

                st.error(hata_mesaji)
                with st.expander("Teknik hata ayrıntısı", expanded=False):
                    st.code(safe_detail[:2000])
                st.session_state.mesajlar.append({"rol": "assistant", "icerik": hata_mesaji})

# ─────────────────── FOOTER ───────────────────
st.markdown(
    '<div class="curator-footer">Yönetmelik Asistanı hata yapabilir. Önemli bilgileri her zaman resmi gazeteden kontrol edin.</div>',
    unsafe_allow_html=True
)
