import streamlit as st
import pickle
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
import os
from langchain_core.output_parsers import StrOutputParser

# Yeni Eklenenler: Hibrit Arama (BM25 + Ensemble)
from langchain_classic.retrievers import EnsembleRetriever

# 1. STREAMLIT SAYFA AYARLARI
st.set_page_config(page_title="Selçuk RAG Asistanı", page_icon="🎓")
st.title("🎓 Selçuk Üni. Yönetmelik Asistanı")
st.markdown("Selçuk Üniversitesi yönetmelikleri hakkında bana sorular sorabilirsiniz. Sizin için okur ve özetlerim.")

if not os.environ.get("GROQ_API_KEY"):
    st.error("⚠️ Groq API anahtarı (GROQ_API_KEY) bulunamadı. Lütfen ortam değişkenlerini kontrol edin (örn. Streamlit Cloud'da Secrets bölümü).")
    st.stop()

# --- YAN MENÜ (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Ayarlar")
    if st.button("🗑️ Sohbeti Temizle"):
        st.session_state.mesajlar = []
        st.success("Sohbet geçmişi temizlendi!")

# 2. SİSTEMİ YÜKLEME
@st.cache_resource
def sistemi_yukle():
    try:
        # 1. Semantik Arama (Chroma DB - Önceden oluşturulmuş)
        embedding_model = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
        vektordb = Chroma(persist_directory="./chroma_db", embedding_function=embedding_model)
        chroma_retriever = vektordb.as_retriever(search_kwargs={"k": 2})
        
        # 2. BM25 DB (Anahtar Kelime Araması - Diske kaydedilmiş pkl'den yükleniyor)
        # Eğer dosya yoksa veritabani_olustur.py henüz çalıştırılmamıştır
        with open("bm25_index.pkl", "rb") as f:
            bm25_retriever = pickle.load(f)
            
        # 3. Ensemble Retriever (Hibrit Arama)
        ensemble_retriever = EnsembleRetriever(
            retrievers=[chroma_retriever, bm25_retriever],
            weights=[0.5, 0.5]
        )
        
        llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)
        
        sistem_istemi = (
            "Sen Selçuk Üniversitesi RAG Asistanısın.\n\n"
            "KESİN KURALLAR:\n"
            "1. Aşağıdaki BAĞLAMDA net bir rakam veya bilgi yoksa KESİNLİKLE UYDURMA. Doğrudan 'Yönetmeliklerde bu bilgi geçmemektedir' de.\n"
            "2. SADECE TÜRKÇE KONUŞ. İngilizce kelimeler kullanma.\n"
            "3. Sadece BAĞLAM'daki bilgileri kullanarak cevap ver.\n\n"
            "--- GEÇMİŞ SOHBET ---\n{chat_history}\n\n"
            "--- BAĞLAM (BİLGİ KAYNAĞI) ---\n{context}\n\n"
            "Cevap:"
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", sistem_istemi),
            ("human", "{input}")
        ])
        
        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)
        
        from langchain_core.runnables import RunnableParallel, RunnablePassthrough

        # RunnableParallel kullanarak hem retriever'dan dokümanları alıyoruz hem de formatlanmış context'i tutuyoruz
        rag_zinciri = (
            RunnablePassthrough.assign(
               raw_docs=lambda x: ensemble_retriever.invoke(x["input"])
            )
            | RunnablePassthrough.assign(
                context=lambda x: format_docs(x["raw_docs"])
            )
            | RunnableParallel(
                 answer=(
                      {
                         "context": lambda x: x["context"], 
                         "chat_history": lambda x: x["chat_history"],
                         "input": lambda x: x["input"]
                      }
                      | prompt
                      | llm
                      | StrOutputParser()
                 ),
                 source_documents=lambda x: x["raw_docs"]
            )
        )
        return {"durum": "basarili", "zincir": rag_zinciri}
        
    except FileNotFoundError:
        return {"durum": "hata", "mesaj": "⚠️ BM25 İndeksi (`bm25_index.pkl`) veya Chroma DB bulunamadı. Lütfen önce `python veritabani_olustur.py` komutunu çalıştırın."}
    except Exception as e:
        return {"durum": "hata", "mesaj": f"⚠️ Sistem yüklenirken bir hata oluştu: {str(e)}"}

# Sistemi Yükle
sistem = sistemi_yukle()

# Eğer veritabanları yoksa uyarı göster ve durdur
if sistem["durum"] == "hata":
    st.error(sistem["mesaj"])
    st.stop()
else:
    zincir = sistem["zincir"]

# 3. SOHBET GEÇMİŞİNİ HAFIZADA TUTMA
if "mesajlar" not in st.session_state:
    st.session_state.mesajlar = []

# --- 4. KARŞILAMA VE ÖRNEK SORULAR ---
if len(st.session_state.mesajlar) == 0:
    st.info("👋 Merhaba! Ben Selçuk Üniversitesi Yönetmelik Asistanı. Size nasıl yardımcı olabilirim?")
    st.markdown("**Örnek Sorular:**")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Staj muafiyet şartları nelerdir?"):
            st.session_state.ornek_soru = "Staj muafiyet şartları nelerdir?"
    with col2:
        if st.button("Çift ana dal nasıl yapılır?"):
             st.session_state.ornek_soru = "Çift ana dal nasıl yapılır?"

# Eski mesajları ekrana yazdırma
for mesaj in st.session_state.mesajlar:
    avatar_ikon = "👤" if mesaj["rol"] == "user" else "🎓"
    with st.chat_message(mesaj["rol"], avatar=avatar_ikon):
        st.markdown(mesaj["icerik"])
        
        # Eğer geçmiş mesajda kaynak varsa onu da göster
        if "kaynaklar" in mesaj and mesaj["kaynaklar"]:
             with st.expander("📚 Kaynakları Gör"):
                  st.markdown(mesaj["kaynaklar"])

# 5. KULLANICI ETKİLEŞİMİ (Chat Input)
kullanici_sorusu = st.chat_input("Örn: Başarı bursu alma şartları nelerdir?")


# Eğer örnek soruya tıklandıysa ve chat input boşsa, soruyu input kabul et
if "ornek_soru" in st.session_state:
    kullanici_sorusu = st.session_state.ornek_soru
    del st.session_state.ornek_soru


if kullanici_sorusu:
    
    gecmis_metin = ""
    for m in st.session_state.mesajlar:
        rol_adi = "Kullanıcı" if m["rol"] == "user" else "Asistan"
        gecmis_metin += f"{rol_adi}: {m['icerik']}\n"
        
    st.session_state.mesajlar.append({"rol": "user", "icerik": kullanici_sorusu})
    with st.chat_message("user", avatar="👤"):
        st.markdown(kullanici_sorusu)

    with st.chat_message("assistant", avatar="🎓"):
        
        cevap_alani = st.empty() 
        tam_cevap = ""
        kaynak_metni = ""
        
        zincir_girdisi = {
            "input": kullanici_sorusu,
            "chat_history": gecmis_metin
        }
        
        try:
            with st.spinner("Yönetmelikler taranıyor..."):
                # RunnableParallel kullanıldığı için artık cevabı invoke ile almalıyız ki kaynakları ayıklayabilelim.
                # Eğer hem stream hem kaynak takibi yapmak istersek langchain'de astream_events veya yield generator kullanmamız gerekir.
                # Production düzeyinde basitlik adına invoke yapıp tam cevabı yansıttıktan sonra kaynakları listeliyoruz.
                sonuc = zincir.invoke(zincir_girdisi)
                tam_cevap = sonuc["answer"]
                dokumanlar = sonuc["source_documents"]

                # Kelime kelime yazdırıyormuş hissi için ufak bir hile yapabiliriz (opsiyonel)
                # Şimdilik direkt basıyoruz
                cevap_alani.markdown(tam_cevap)
                
            # --- KAYNAKLARI (SOURCE) AYIKLAMA ---
            kaynak_listesi = []
            for i, doc in enumerate(dokumanlar):
                dosya_adi = doc.metadata.get("source", "Bilinmeyen Dosya")
                # Yol içeriyorsa sadece dosya adını alalım:
                if dosya_adi and "/" in dosya_adi:
                    dosya_adi = dosya_adi.split("/")[-1]
                elif dosya_adi and "\\" in dosya_adi:
                     dosya_adi = dosya_adi.split("\\")[-1]
                     
                sayfa_no = doc.metadata.get("page", "Belirtilmemiş")
                kaynak_listesi.append(f"- **Belge:** {dosya_adi} *(Sayfa: {sayfa_no})*")
            
            # Kaynaklar varsa expander'a koy
            if kaynak_listesi:
                # Benzersiz olanları set ile alıp tekrar listeye çevirelim ki aynı sayfayı 3 kere göstermesin
                kaynak_listesi = list(set(kaynak_listesi))
                kaynak_metni = "\n".join(kaynak_listesi)
                with st.expander("📚 Kaynakları Gör"):
                    st.markdown(kaynak_metni)

            st.session_state.mesajlar.append({
                "rol": "assistant", 
                "icerik": tam_cevap,
                "kaynaklar": kaynak_metni
            })
            
        except Exception as e:
            hata_mesaji = "⚠️ Üzgünüm, asistan şu anda yanıt veremiyor. Lütfen Groq API bağlantınızı ve limitlerinizi kontrol edin."
            cevap_alani.error(f"{hata_mesaji}\n\n(Hata Detayı: {str(e)})")
