import streamlit as st
import os
import tempfile
import time
import logging
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rag_engine import SelcukRAGEngine

# .env dosyasından ortam değişkenlerini yükle (lokal geliştirme için)
load_dotenv()

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# 1. STREAMLIT SAYFA AYARLARI
st.set_page_config(page_title="Selçuk RAG Asistanı", page_icon="🎓")
st.title("🎓 Selçuk Üni. Yönetmelik Asistanı")

if not os.environ.get("GROQ_API_KEY"):
    st.error("⚠️ GROQ_API_KEY bulunamadı! Ortam değişkenlerini kontrol edin.")
    st.stop()

# 2. HAFIZA YÖNETİMİ (Session State)
if "mesajlar" not in st.session_state:
    st.session_state.mesajlar = []
if "yeni_dokumanlar" not in st.session_state:
    st.session_state.yeni_dokumanlar = [] # Dinamik yüklenen PDF'ler sadece RAM'de kalır!

# 3. MOTORU ÇALIŞTIR (Sadece bir kere yüklenir, kilitleme yapmaz)
@st.cache_resource
def get_engine():
    return SelcukRAGEngine()

motor = get_engine()

# 4. YAN MENÜ: DİNAMİK PDF YÜKLEME
with st.sidebar:
    st.header("📄 PDF Yükle ve Öğret")
    st.info("Buradan yüklediğiniz PDF'ler veritabanını bozmaz, sadece bu oturum için asistanın hafızasına eklenir.")
    yuklenen_pdf = st.file_uploader("CV veya Belge Seçin", type=["pdf"])
    
    if st.button("Sisteme Öğret"):
        if yuklenen_pdf:
            with st.spinner("İşleniyor..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(yuklenen_pdf.getvalue())
                    tmp_dosya_yolu = tmp.name
                
                loader = PyPDFLoader(tmp_dosya_yolu)
                docs = loader.load()
                for d in docs: 
                    d.metadata["source"] = yuklenen_pdf.name
                
                # Daha küçük parçalar CV okumayı kolaylaştırır
                splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)
                parcalar = splitter.split_documents(docs)
                
                # RAM'de tutmak için session_state'e ekliyoruz (Diske YAZMIYORUZ = Sıfır Kilitlenme!)
                st.session_state.yeni_dokumanlar.extend(parcalar)
                os.remove(tmp_dosya_yolu)
                
                st.success(f"✅ '{yuklenen_pdf.name}' geçici hafızaya eklendi!")
                time.sleep(1)
                st.rerun()

    st.divider()
    if st.button("🗑️ Sohbeti ve Hafızayı Temizle"):
        st.session_state.mesajlar = []
        st.session_state.yeni_dokumanlar = []
        st.rerun()

# 5. SOHBET ARAYÜZÜ VE ÖRNEK SORULAR
if len(st.session_state.mesajlar) == 0:
    st.info("👋 Merhaba! Ben Selçuk Üniversitesi Yönetmelik Asistanı.")
    col1, col2 = st.columns(2)
    if col1.button("Staj muafiyet şartları nelerdir?"):
        st.session_state.ornek_soru = "Staj muafiyet şartları nelerdir?"
    if col2.button("Çift ana dal nasıl yapılır?"):
        st.session_state.ornek_soru = "Çift ana dal nasıl yapılır?"

# Geçmiş mesajları yazdır
for m in st.session_state.mesajlar:
    with st.chat_message(m["rol"], avatar="🎓" if m["rol"] == "assistant" else "👤"):
        st.markdown(m["icerik"])

# Kullanıcı girdisi al
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
        with st.spinner("Dökümanlar taranıyor..."):
            try:
                # Son 3 mesajı geçmiş olarak ver (Gereksiz token tüketimini engeller)
                history = "\n".join([f"{m['rol']}: {m['icerik']}" for m in st.session_state.mesajlar[-3:]])
                
                # Motorumuzdan dinamik dökümanları da hesaba katan RAG zincirini iste
                rag_zinciri = motor.get_chain(dynamic_docs=st.session_state.yeni_dokumanlar)
                
                # Cevabı üret
                sonuc = rag_zinciri.invoke({"input": kullanici_sorusu, "chat_history": history})
                cevap = sonuc["answer"]
                st.markdown(cevap)
                
                st.session_state.mesajlar.append({"rol": "assistant", "icerik": cevap})
            
            except Exception as e:
                logging.getLogger(__name__).error(f"RAG zinciri hatası: {e}")
                hata_mesaji = "⚠️ Bir hata oluştu. Lütfen tekrar deneyin. Sorun devam ederse yönetici ile iletişime geçin."
                st.error(hata_mesaji)
                st.session_state.mesajlar.append({"rol": "assistant", "icerik": hata_mesaji, "kaynaklar": ""})