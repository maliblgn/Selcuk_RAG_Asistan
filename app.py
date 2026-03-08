import streamlit as st
import pickle
import os
import tempfile
import time
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.retrievers import BM25Retriever

# 1. STREAMLIT SAYFA AYARLARI
st.set_page_config(page_title="Selçuk RAG Asistanı", page_icon="🎓")
st.title("🎓 Selçuk Üni. Yönetmelik Asistanı")
st.markdown("Selçuk Üniversitesi yönetmelikleri hakkında bana sorular sorabilirsiniz. Sizin için okur ve özetlerim.")

if not os.environ.get("GROQ_API_KEY"):
    st.error("⚠️ Groq API anahtarı (GROQ_API_KEY) bulunamadı. Lütfen ortam değişkenlerini kontrol edin (örn. Streamlit Cloud'da Secrets bölümü).")
    st.stop()

# Dinamik PDF'ler için Session State hafızası
if "yeni_dokumanlar" not in st.session_state:
    st.session_state.yeni_dokumanlar = []

# --- YAN MENÜ (SIDEBAR) AŞAĞIYA TAŞINDI ---

# 2. SİSTEMİ YÜKLEME
# Cache hash bypass: session_state içerisindeki döküman sayısı değiştiğinde yeniden tetikletmek için parametre ekledik.
@st.cache_resource
def sistemi_yukle(yeni_doc_count):
    try:
        # 1. Semantik Arama (Chroma DB - Önceden oluşturulmuş)
        embedding_model = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
        db_yolu = os.path.abspath("./chroma_db")
        vektordb = Chroma(persist_directory=db_yolu, embedding_function=embedding_model)
        chroma_retriever = vektordb.as_retriever(search_kwargs={"k": 3})
        
        # 2. BM25 DB (Anahtar Kelime Araması - Diske kaydedilmiş pkl'den yükleniyor)
        with open("bm25_index.pkl", "rb") as f:
            bm25_retriever = pickle.load(f)
            
        # Eğer çalışma zamanında yeni doküman yüklenmişse, statik BM25'i baştan dinamik olarak yaratıyoruz.
        if hasattr(bm25_retriever, 'docs') and len(st.session_state.yeni_dokumanlar) > 0:
            tum_docs = bm25_retriever.docs + st.session_state.yeni_dokumanlar
            bm25_retriever = BM25Retriever.from_documents(tum_docs)
            
        bm25_retriever.k = 2
            
        # 3. Ensemble Retriever (Hibrit Arama)
        ensemble_retriever = EnsembleRetriever(
            retrievers=[chroma_retriever, bm25_retriever],
            weights=[0.6, 0.4]
        )
        
        llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)
        
        sistem_istemi = (
            "Sen Selçuk Üniversitesi Döküman Uzmanısın. Görevin sadece dökümanlardaki gerçekleri söylemektir.\n\n"
            "KURAL 1: Eğer cevap bağlamda (context) yoksa, asla genel bilgini kullanma, uydurma. 'Bu bilgi dökümanlarda yer almıyor' de.\n"
            "KURAL 2: Mezuniyet ortalaması, kredi sayısı, tarihler gibi rakamsal verilerde dökümandaki değerlere %100 sadık kal.\n"
            "KURAL 3: Sadece döküman odaklı çalış, dış sitelere veya API'lere bağlanma.\n\n"
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
        return {"durum": "basarili", "zincir": rag_zinciri, "vektordb": vektordb}
        
    except FileNotFoundError:
        return {"durum": "hata", "mesaj": "⚠️ BM25 İndeksi (`bm25_index.pkl`) veya Chroma DB bulunamadı. Lütfen önce `python veritabani_olustur.py` komutunu çalıştırın."}
    except Exception as e:
        return {"durum": "hata", "mesaj": f"⚠️ Sistem yüklenirken bir hata oluştu: {str(e)}"}

# Sistemi Yükle
sistem = sistemi_yukle(len(st.session_state.get("yeni_dokumanlar", [])))

# Eğer veritabanları yoksa uyarı göster ve durdur
if sistem["durum"] == "hata":
    st.error(sistem["mesaj"])
    st.stop()
else:
    zincir = sistem["zincir"]
    vektordb = sistem["vektordb"]

# --- YAN MENÜ (SIDEBAR) (Dinamik Yükleme) ---
with st.sidebar:
    st.header("⚙️ Ayarlar")
    
    st.divider()
    st.header("📄 PDF Yükle ve Öğret")
    yuklenen_pdf = st.file_uploader("Öğretmek için PDF seçin", type=["pdf"])
    if st.button("Sisteme Öğret"):
        if yuklenen_pdf:
            with st.spinner("İşleniyor, lütfen bekleyin..."):
                tmp_dosya_yolu = ""
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        tmp.write(yuklenen_pdf.getvalue())
                        tmp_dosya_yolu = tmp.name
                    
                    loader = PyPDFLoader(tmp_dosya_yolu)
                    docs = loader.load()
                    for d in docs: 
                        d.metadata["source"] = yuklenen_pdf.name
                    
                    splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)
                    parcalar = splitter.split_documents(docs)
                    
                    # Mevcut vektordb nesnesi üzerinden ekleme yaparak dosya kilidini aşıyoruz
                    vektordb.add_documents(parcalar)
                    
                    # Cache bağlantısını tazele
                    st.cache_resource.clear()
                    
                    # BM25 için session hafızasına ekle
                    st.session_state.yeni_dokumanlar.extend(parcalar)
                    
                    st.success(f"✅ '{yuklenen_pdf.name}' başarıyla eklendi ve sistem tarafından öğrenildi!")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    # Yazma işlemini try-except bloğunda kilide karşı koruma
                    st.error(f"Sistem şu an meşgul, lütfen tekrar deneyin.\n(Detay: {str(e)})")
                finally:
                    if tmp_dosya_yolu and os.path.exists(tmp_dosya_yolu):
                        try:
                            os.remove(tmp_dosya_yolu)
                        except Exception:
                            pass

    st.divider()
    if st.button("🗑️ Sohbeti Temizle"):
        st.session_state.mesajlar = []
        st.success("Sohbet geçmişi temizlendi!")

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
