import os
import logging
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)

# Gönderilecek bağlamın maksimum karakter sayısı (token taşmasını önler)
MAX_CONTEXT_CHARS = 12_000

class SelcukRAGEngine:
    def __init__(self):
        logger.info("SelcukRAGEngine başlatılıyor...")
        # 1. Embedding Modelini Yükle
        self.embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
        
        # 2. Statik Veritabanını Bağla
        self.db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
        self.static_db = Chroma(persist_directory=self.db_dir, embedding_function=self.embeddings)
        self.static_retriever = self.static_db.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 5, "fetch_k": 10}
        )
        
        # Dinamik DB referansı (bellek sızıntısını önlemek için)
        self._temp_db = None
        
        # 3. LLM Ayarları (Groq Llama 3.1)
        self.llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
        
        # 4. Katı Prompt (Zero-Hallucination + Kaynak Alıntı Kuralı)
        self.prompt = ChatPromptTemplate.from_template(
            "Sen Selçuk Üniversitesi Döküman Uzmanısın. Görevin sadece sana verilen bağlamdaki gerçekleri söylemektir.\n\n"
            "KESİN KURALLAR:\n"
            "1. Eğer cevap bağlamda (context) yoksa ASLA uydurma. 'Bu bilgi dökümanlarda yer almıyor' de.\n"
            "2. Bağlamdaki rakamlara %100 sadık kal. Kendi bildiğin rakamları söyleme.\n"
            "3. Sadece Türkçe konuş.\n"
            "4. Cevabını madde madde ve okunaklı şekilde formatla.\n"
            "5. Cevabının sonuna '📄 Kaynak: <belge adı>' satırını ekleyerek bilginin hangi belgeden geldiğini belirt.\n\n"
            "--- BAĞLAM (kaynaklarla birlikte) ---\n{context}\n\n"
            "--- GEÇMİŞ SOHBET ---\n{chat_history}\n\n"
            "--- SORU ---\n{input}\n\n"
            "Cevap:"
        )
        
        # 5. Soru Yeniden Yazma Prompt'u
        self.rewrite_prompt = ChatPromptTemplate.from_template(
            "Aşağıdaki sohbet geçmişini ve son soruyu oku. "
            "Eğer son soru geçmişe referans veriyorsa (ör. 'bunun', 'onun', 'peki ya', 'bu konuda'), "
            "soruyu geçmişi kullanarak bağımsız bir soru olarak yeniden yaz. "
            "Eğer soru zaten bağımsızsa, olduğu gibi döndür. "
            "Sadece soruyu yaz, başka açıklama ekleme.\n\n"
            "Geçmiş:\n{chat_history}\n\n"
            "Son soru: {question}\n\n"
            "Bağımsız soru:"
        )
        
        # 6. Takip Sorusu Önerme Prompt'u
        self.followup_prompt = ChatPromptTemplate.from_template(
            "Aşağıdaki soru ve cevaba bakarak, kullanıcının ilgisini çekebilecek "
            "tam olarak 3 adet kısa takip sorusu öner. "
            "Her soru bir satırda olsun, numara kullanma, sadece soruları yaz. "
            "Sorular Selçuk Üniversitesi yönetmelikleriyle ilgili olsun.\n\n"
            "Soru: {question}\n"
            "Cevap: {answer}\n\n"
            "Önerilen sorular:"
        )
        
        logger.info("SelcukRAGEngine hazır.")

    def rewrite_query(self, question, chat_history):
        """Takip sorularını bağımsız sorulara çevir."""
        if not chat_history or len(chat_history.strip()) == 0:
            return question
        
        try:
            chain = self.rewrite_prompt | self.llm | StrOutputParser()
            rewritten = chain.invoke({"question": question, "chat_history": chat_history})
            logger.info(f"Soru yeniden yazıldı: '{question}' → '{rewritten.strip()}'")
            return rewritten.strip()
        except Exception as e:
            logger.warning(f"Soru yeniden yazılamadı, orijinal kullanılıyor: {e}")
            return question

    def retrieve(self, question, dynamic_docs=None):
        """Soruya en uygun doküman parçalarını getir."""
        active_retriever = self.static_retriever

        if dynamic_docs and len(dynamic_docs) > 0:
            if self._temp_db is not None:
                try:
                    self._temp_db.delete_collection()
                except Exception:
                    pass
                self._temp_db = None
            
            self._temp_db = Chroma.from_documents(dynamic_docs, self.embeddings)
            dynamic_retriever = self._temp_db.as_retriever(search_kwargs={"k": 3})
            logger.info(f"Dinamik retriever oluşturuldu ({len(dynamic_docs)} doküman)")
            
            # Ensemble: her iki retriever'dan sonuçları birleştir
            static_docs = self.static_retriever.invoke(question)
            dynamic_results = dynamic_retriever.invoke(question)
            
            seen = set()
            merged = []
            for doc in static_docs + dynamic_results:
                content_hash = hash(doc.page_content)
                if content_hash not in seen:
                    seen.add(content_hash)
                    merged.append(doc)
            return merged
        
        return active_retriever.invoke(question)

    def format_context(self, docs):
        """Dokümanları kaynak bilgisiyle birlikte bağlam metnine çevir."""
        chunks = []
        for doc in docs:
            source = os.path.basename(doc.metadata.get("source", "Bilinmeyen Belge"))
            source = source.replace(".pdf", "")
            chunks.append(f"[Kaynak: {source}]\n{doc.page_content}")
        context = "\n\n".join(chunks)
        # Token taşmasını önlemek için maksimum karakter sayısını uygula
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS] + "\n...[bağlam kısaltıldı]"
        return context

    def stream_answer(self, question, context, chat_history=""):
        """Cevabı token token stream eder (generator)."""
        prompt_value = self.prompt.invoke({
            "context": context,
            "chat_history": chat_history,
            "input": question
        })
        return self.llm.stream(prompt_value)

    def suggest_followups(self, question, answer):
        """Cevaba göre 3 adet takip sorusu öner."""
        try:
            chain = self.followup_prompt | self.llm | StrOutputParser()
            result = chain.invoke({"question": question, "answer": answer})
            suggestions = [s.strip() for s in result.strip().split("\n") if s.strip()]
            return suggestions[:3]
        except Exception as e:
            logger.warning(f"Takip soruları üretilemedi: {e}")
            return []