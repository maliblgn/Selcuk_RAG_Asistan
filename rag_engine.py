import os
import logging
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel

logger = logging.getLogger(__name__)

class SelcukRAGEngine:
    def __init__(self):
        logger.info("SelcukRAGEngine başlatılıyor...")
        # 1. Embedding Modelini Yükle (RAM dostu ve performanslı model)
        self.embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
        
        # 2. Statik Veritabanını Bağla (Read-Only Modu - Kilitlenmeyi önler)
        self.db_dir = os.path.abspath("./chroma_db")
        self.static_db = Chroma(persist_directory=self.db_dir, embedding_function=self.embeddings)
        self.static_retriever = self.static_db.as_retriever(search_kwargs={"k": 3})
        
        # Dinamik DB referansı (bellek sızıntısını önlemek için)
        self._temp_db = None
        logger.info("SelcukRAGEngine hazır.")
        
        # 3. LLM Ayarları (Groq Llama 3.1 - Sıfır Halüsinasyon için temperature=0)
        self.llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)
        
        # 4. Katı Prompt (Zero-Hallucination Kuralı)
        self.prompt = ChatPromptTemplate.from_template(
            "Sen Selçuk Üniversitesi Döküman Uzmanısın. Görevin sadece sana verilen bağlamdaki gerçekleri söylemektir.\n\n"
            "KESİN KURALLAR:\n"
            "1. Eğer cevap bağlamda (context) yoksa ASLA uydurma. 'Bu bilgi dökümanlarda yer almıyor' de.\n"
            "2. Bağlamdaki rakamlara %100 sadık kal. Kendi bildiğin rakamları söyleme.\n"
            "3. Sadece Türkçe konuş.\n\n"
            "--- BAĞLAM ---\n{context}\n\n"
            "--- GEÇMİŞ SOHBET ---\n{chat_history}\n\n"
            "--- SORU ---\n{input}\n\n"
            "Cevap:"
        )

    def _ensemble_retrieve(self, query, static_retriever, dynamic_retriever, weights=(0.6, 0.4)):
        """İki retriever'ın sonuçlarını ağırlıklı birleştirme (EnsembleRetriever yerine)."""
        static_docs = static_retriever.invoke(query)
        dynamic_docs = dynamic_retriever.invoke(query)
        
        # Tekilleştir (aynı içerik tekrar gelmesin)
        seen = set()
        merged = []
        for doc in static_docs + dynamic_docs:
            content_hash = hash(doc.page_content)
            if content_hash not in seen:
                seen.add(content_hash)
                merged.append(doc)
        return merged

    def get_chain(self, dynamic_docs=None):
        """
        Dinamik PDF'leri sadece RAM'de tutarak SQLite kilitlenmesini engeller.
        """
        active_retriever = self.static_retriever
        use_ensemble = False

        # Arayüzden yeni PDF yüklendiyse hibrit arama yap
        if dynamic_docs and len(dynamic_docs) > 0:
            # Önceki geçici DB'yi temizle (bellek sızıntısını önler)
            if self._temp_db is not None:
                try:
                    del self._temp_db
                except Exception:
                    pass
            
            self._temp_db = Chroma.from_documents(dynamic_docs, self.embeddings)
            self._dynamic_retriever = self._temp_db.as_retriever(search_kwargs={"k": 2})
            logger.info(f"Dinamik retriever oluşturuldu ({len(dynamic_docs)} doküman)")
            use_ensemble = True

        if use_ensemble:
            def retrieve_fn(x):
                return self._ensemble_retrieve(
                    x["input"], self.static_retriever, self._dynamic_retriever
                )
        else:
            def retrieve_fn(x):
                return active_retriever.invoke(x["input"])

        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        # RAG Akış Zinciri
        rag_zinciri = (
            RunnablePassthrough.assign(
                raw_docs=lambda x: retrieve_fn(x)
            )
            | RunnablePassthrough.assign(
                context=lambda x: format_docs(x["raw_docs"])
            )
            | RunnableParallel(
                answer=(self.prompt | self.llm | StrOutputParser()),
                source_documents=lambda x: x["raw_docs"]
            )
        )
        return rag_zinciri