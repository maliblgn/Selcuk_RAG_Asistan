import streamlit as st
import os
import tempfile
import time
import logging
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rag_engine import SelcukRAGEngine

# .env dosyasından ortam değişkenlerini yükle
load_dotenv()

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ─────────────────── SAYFA AYARLARI ───────────────────
st.set_page_config(page_title="Selçuk RAG Asistanı", page_icon="🎓", layout="centered")

# Özel CSS
st.markdown("""
<style>
    /* Footer */
    .footer {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        text-align: center;
        padding: 8px 0;
        font-size: 0.78rem;
        color: #888;
        background: linear-gradient(transparent, #0E1117 40%);
        z-index: 999;
    }
    /* Öneri butonları */
    .stButton > button {
        border-radius: 20px;
        font-size: 0.85rem;
    }
    /* Başlık altı çizgisi */
    .header-divider {
        height: 3px;
        background: linear-gradient(90deg, #1E88E5, transparent);
        border: none;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────── BAŞLIK ───────────────────
st.markdown("# 🎓 Selçuk Üni. Yönetmelik Asistanı")
st.markdown('<div class="header-divider"></div>', unsafe_allow_html=True)

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

# ─────────────────── MOTOR ───────────────────
@st.cache_resource
def get_engine():
    return SelcukRAGEngine()

motor = get_engine()

# ─────────────────── DATA KLASÖRÜNDEKİ PDF LİSTESİ ───────────────────
def get_data_pdfs():
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    if os.path.exists(data_dir):
        return [f for f in os.listdir(data_dir) if f.lower().endswith(".pdf")]
    return []

# ─────────────────── YAN MENÜ ───────────────────
with st.sidebar:
    st.markdown("### 📚 Bilgi Tabanı")
    
    # Mevcut yönetmelik listesi
    pdfs = get_data_pdfs()
    if pdfs:
        with st.expander(f"📂 Yüklü Yönetmelikler ({len(pdfs)})", expanded=False):
            for pdf in pdfs:
                st.markdown(f"• {pdf.replace('.pdf', '')}")
    
    if st.session_state.yeni_dokumanlar:
        st.success(f"📎 {len(st.session_state.yeni_dokumanlar)} geçici parça hafızada")
    
    st.divider()
    
    # Dinamik PDF yükleme
    st.markdown("### 📄 PDF Yükle ve Öğret")
    st.caption("Yüklenen PDF'ler sadece bu oturum için geçerlidir.")
    yuklenen_pdf = st.file_uploader("Belge Seçin", type=["pdf"], label_visibility="collapsed")
    
    if st.button("📤 Sisteme Öğret", use_container_width=True):
        if yuklenen_pdf:
            with st.spinner("İşleniyor..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(yuklenen_pdf.getvalue())
                    tmp_dosya_yolu = tmp.name
                
                loader = PyPDFLoader(tmp_dosya_yolu)
                docs = loader.load()
                for d in docs: 
                    d.metadata["source"] = yuklenen_pdf.name
                
                splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
                parcalar = splitter.split_documents(docs)
                
                st.session_state.yeni_dokumanlar.extend(parcalar)
                os.remove(tmp_dosya_yolu)
                
                st.success(f"✅ '{yuklenen_pdf.name}' eklendi!")
                time.sleep(1)
                st.rerun()
    
    st.divider()
    if st.button("🗑️ Sohbeti Temizle", use_container_width=True):
        st.session_state.mesajlar = []
        st.session_state.yeni_dokumanlar = []
        st.session_state.oneriler = []
        st.rerun()
    
    # Hakkında bölümü
    st.divider()
    st.markdown("### ℹ️ Hakkında")
    st.caption(
        "Bu asistan, Selçuk Üniversitesi yönetmeliklerini "
        "yapay zeka ile sorgulayan bir RAG (Retrieval-Augmented Generation) sistemidir.\n\n"
        "**Model:** Llama 3.1 8B (Groq)\n\n"
        "**Embedding:** multilingual-e5-small"
    )

# ─────────────────── KARŞILAMA EKRANI ───────────────────
if len(st.session_state.mesajlar) == 0:
    st.markdown("""
    > 👋 **Merhaba!** Selçuk Üniversitesi yönetmelikleri hakkında sorularınızı yanıtlamak için buradayım.
    > Aşağıdaki örnek sorulardan birine tıklayabilir veya kendi sorunuzu yazabilirsiniz.
    """)
    
    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)
    
    ornek_sorular = [
        ("📋 Staj muafiyet şartları nelerdir?", "Staj muafiyet şartları nelerdir?"),
        ("📘 Çift ana dal nasıl yapılır?", "Çift ana dal programına başvuru şartları nelerdir?"),
        ("💰 Burs başvuru koşulları nelerdir?", "Burs başvuru koşulları nelerdir?"),
        ("📄 Diploma eki nedir?", "Diploma eki nedir ve nasıl düzenlenir?"),
    ]
    
    cols = [col1, col2, col3, col4]
    for i, (label, soru) in enumerate(ornek_sorular):
        if cols[i].button(label, use_container_width=True):
            st.session_state.ornek_soru = soru

# ─────────────────── GEÇMİŞ MESAJLAR ───────────────────
for m in st.session_state.mesajlar:
    with st.chat_message(m["rol"], avatar="🎓" if m["rol"] == "assistant" else "👤"):
        st.markdown(m["icerik"])

# ─────────────────── TAKİP SORU ÖNERİLERİ ───────────────────
if st.session_state.oneriler and len(st.session_state.mesajlar) > 0:
    st.markdown("**🔎 Bunları da sorabilirsiniz:**")
    oneri_cols = st.columns(len(st.session_state.oneriler))
    for i, oneri in enumerate(st.session_state.oneriler):
        if oneri_cols[i].button(oneri, key=f"oneri_{i}", use_container_width=True):
            st.session_state.ornek_soru = oneri
            st.session_state.oneriler = []
            st.rerun()

# ─────────────────── KULLANICI GİRDİSİ ───────────────────
kullanici_sorusu = st.chat_input("Sorunuzu yazın...")
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
            history = "\n".join([f"{m['rol']}: {m['icerik']}" for m in st.session_state.mesajlar[-4:]])
            
            # 2. Soru yeniden yazma (takip soruları için)
            with st.spinner("Soru analiz ediliyor..."):
                yeniden_soru = motor.rewrite_query(kullanici_sorusu, history)
            
            # 3. Doküman getirme
            with st.spinner("Dökümanlar taranıyor..."):
                docs = motor.retrieve(yeniden_soru, dynamic_docs=st.session_state.yeni_dokumanlar)
                context = motor.format_context(docs)
            
            # 4. Streaming yanıt
            def token_generator():
                for chunk in motor.stream_answer(kullanici_sorusu, context, history):
                    if hasattr(chunk, 'content'):
                        yield chunk.content
                    else:
                        yield str(chunk)
            
            cevap = st.write_stream(token_generator())
            
            st.session_state.mesajlar.append({"rol": "assistant", "icerik": cevap})
            
            # 5. Takip sorusu önerileri (arka planda)
            oneriler = motor.suggest_followups(kullanici_sorusu, cevap)
            st.session_state.oneriler = oneriler
            
            st.rerun()
        
        except Exception as e:
            error_msg = str(e).lower()
            
            if "rate_limit" in error_msg or "429" in error_msg or "rate limit" in error_msg:
                logger.warning(f"Groq rate limit aşıldı: {e}")
                hata_mesaji = "⏳ API istek limiti aşıldı. Lütfen **30 saniye** bekleyip tekrar deneyin."
            else:
                logger.error(f"RAG zinciri hatası: {e}")
                hata_mesaji = "⚠️ Bir hata oluştu. Lütfen tekrar deneyin."
            
            st.error(hata_mesaji)
            st.session_state.mesajlar.append({"rol": "assistant", "icerik": hata_mesaji})

# ─────────────────── FOOTER ───────────────────
st.markdown(
    '<div class="footer">Selçuk Üniversitesi RAG Asistanı © 2026 | Yapay Zeka Destekli Yönetmelik Sorgulama</div>',
    unsafe_allow_html=True
)