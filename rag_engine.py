import os
import logging
import unicodedata
from collections import Counter
from urllib.parse import unquote
from urllib.parse import urlparse
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.document_compressors.flashrank_rerank import FlashrankRerank
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# Gönderilecek bağlamın maksimum karakter sayısı (token taşmasını önler)
MAX_CONTEXT_CHARS = 12_000

SOURCE_INVENTORY_TERMS = (
    "veritabaninda hangi kaynak",
    "veri tabaninda hangi kaynak",
    "veritabaninda ne var",
    "veri tabaninda ne var",
    "hangi kaynaklar var",
    "hangi pdfler var",
    "hangi pdf'ler var",
    "islenen pdf",
    "indexlenen pdf",
    "kaynak listes",
    "kaynak envanter",
    "dokuman listes",
    "belge listes",
)

class SelcukRAGEngine:
    def __init__(self):
        logger.info("SelcukRAGEngine başlatılıyor...")
        # 1. Embedding Modelini Yükle
        self.embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
        
        # 2. Statik Veritabanını Bağla
        self.db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
        self.static_db = Chroma(persist_directory=self.db_dir, embedding_function=self.embeddings)
        self.vector_retriever = self.static_db.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 10, "fetch_k": 20}
        )
        
        # BM25 Retriever
        logger.info("BM25 Retriever için dokümanlar yükleniyor...")
        try:
            db_data = self.static_db.get()
            docs = []
            for i in range(len(db_data["documents"])):
                if db_data["documents"][i]:
                    docs.append(Document(page_content=db_data["documents"][i], metadata=db_data["metadatas"][i]))
            
            if docs:
                self.bm25_retriever = BM25Retriever.from_documents(docs)
                self.bm25_retriever.k = 10
                
                # Hybrid Search: EnsembleRetriever
                self.static_retriever = EnsembleRetriever(
                    retrievers=[self.bm25_retriever, self.vector_retriever],
                    weights=[0.5, 0.5]
                )
                logger.info("Hybrid Search (EnsembleRetriever) aktif.")
            else:
                self.static_retriever = self.vector_retriever
                logger.info("Veritabanı boş, sadece Vector Retriever aktif.")
        except Exception as e:
            logger.warning(f"BM25 yüklenemedi, sadece Vector Search aktif: {e}")
            self.static_retriever = self.vector_retriever
        
        # Dinamik DB referansı (bellek sızıntısını önlemek için)
        self._temp_db = None
        
        # 3. LLM Ayarları (Groq Llama 3.1)
        self.llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
        
        # 4. Modlara Özel Promptlar (Multi-Agent UI)
        common_rules = (
            "KESİN KURALLAR:\n"
            "1. Eğer cevap bağlamda (context) yoksa ASLA uydurma. 'Bu bilgi dökümanlarda yer almıyor' de.\n"
            "2. Bağlamdaki rakamlara %100 sadık kal.\n"
            "3. Sadece Türkçe konuş.\n"
            "4. Cevabındaki bilgilerin sonuna mutlaka bağlamdaki kaynak numarasını [1], [2] şeklinde ekle (Inline Citation).\n"
            "5. Cevabının en sonuna ayrıca 'Kaynak:' yazma, sadece metin içinde [1] şeklinde numaraları kullan.\n\n"
            "--- BAĞLAM (kaynaklarla birlikte) ---\n{context}\n\n"
            "--- GEÇMİŞ SOHBET ---\n{chat_history}\n\n"
            "--- SORU ---\n{input}\n\n"
            "Cevap:"
        )

        self.prompts = {
            "Akademik Rehber": ChatPromptTemplate.from_template(
                "Sen Selçuk Üniversitesi Akademik Rehberisin. Resmi, ciddi ve net bir dil kullan. "
                "Yönetmeliklere, resmi belgelere, kampüs içi hizmetlere (yemekhane vb.) ve duyurulara odaklan.\n\n" + common_rules
            ),
            "Kampüs Yaşamı": ChatPromptTemplate.from_template(
                "Sen Selçuk Üniversitesi Kampüs Yaşamı asistanısın. Samimi, enerjik ve yardımsever bir dil kullan. "
                "Öğrencilere rehberlik etmeyi amaçla.\n\n" + common_rules
            ),
            "Hızlı Arama": ChatPromptTemplate.from_template(
                "Sen Hızlı Arama asistanısın. Uzun cümleler kurma. Sadece maddeler halinde doğrudan bilgiyi ver "
                "ve kaynak numaralarını ekle.\n\n" + common_rules
            )
        }
        
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
        
        # 7. Multi-Query Prompt'u
        self.multi_query_prompt = ChatPromptTemplate.from_template(
            "Sen bir arama optimizasyonu uzmanısın. Kullanıcının sorusunu farklı açılardan ifade eden, "
            "farklı kelimeler (eş anlamlılar veya varyasyonlar) kullanan tam 3 adet alternatif soru üret. "
            "Sadece soruları aralarında yeni satır bırakarak listele. Numara veya açıklama ekleme.\n\n"
            "Orijinal Soru: {question}\n\n"
            "Alternatif Sorular:"
        )
        
        # 8. Reranker (FlashRank)
        self.reranker = FlashrankRerank(top_n=5)
        
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

    def _generate_multi_queries(self, question):
        """Kullanıcının sorgusunu alternatif 3 farklı sorguya çevirir."""
        try:
            chain = self.multi_query_prompt | self.llm | StrOutputParser()
            result = chain.invoke({"question": question})
            queries = [q.strip() for q in result.strip().split("\n") if q.strip() and not q.strip().startswith("-")]
            # Sadece LLM'in urettigi gecerli sorulari al
            clean_queries = [q.replace("1.", "").replace("2.", "").replace("3.", "").replace("-", "").strip() for q in queries]
            return [question] + clean_queries[:3]
        except Exception as e:
            logger.warning(f"Multi-query üretilemedi: {e}")
            return [question]

    def retrieve(self, question, dynamic_docs=None):
        """Soruya en uygun doküman parçalarını getir."""
        active_retriever = self.static_retriever
        
        dynamic_retriever = None
        if dynamic_docs and len(dynamic_docs) > 0:
            if self._temp_db is not None:
                try:
                    self._temp_db.delete_collection()
                except Exception:
                    pass
                self._temp_db = None
            
            self._temp_db = Chroma.from_documents(dynamic_docs, self.embeddings)
            dynamic_vector = self._temp_db.as_retriever(search_kwargs={"k": 5})
            
            # Dinamik docs icin de BM25
            dynamic_bm25 = BM25Retriever.from_documents(dynamic_docs)
            dynamic_bm25.k = 5
            
            dynamic_retriever = EnsembleRetriever(
                retrievers=[dynamic_bm25, dynamic_vector],
                weights=[0.5, 0.5]
            )
            logger.info(f"Dinamik retriever oluşturuldu ({len(dynamic_docs)} doküman)")

        # 1. Multi-Query Expansion
        queries = self._generate_multi_queries(question)
        logger.info(f"Arama yapılacak sorgular: {queries}")
        
        # 2. Paralel Arama
        all_docs = []
        for q in queries:
            all_docs.extend(active_retriever.invoke(q))
            if dynamic_retriever:
                all_docs.extend(dynamic_retriever.invoke(q))
                
        # 3. Deduplication
        seen = set()
        unique_docs = []
        for doc in all_docs:
            content_hash = hash(doc.page_content)
            if content_hash not in seen:
                seen.add(content_hash)
                unique_docs.append(doc)
                
        logger.info(f"Hybrid + MultiQuery sonrası {len(unique_docs)} eşsiz doküman bulundu.")
        if not unique_docs:
            return []
            
        # 4. Cross-Encoder Re-ranking
        try:
            reranked_docs = self.reranker.compress_documents(unique_docs, question)
            logger.info(f"Reranking sonrası {len(reranked_docs)} doküman seçildi.")
            
            # 5. Threshold (Eşik) Kontrolü
            if reranked_docs:
                top_score = reranked_docs[0].metadata.get("relevance_score", 1.0)
                logger.info(f"En iyi doküman skoru: {top_score}")
                if top_score < 0.6: # Eşik değeri
                    logger.warning("Bulunan sonuçlar eşik değerinin altında (Güvensiz bilgi).")
                    return [Document(
                        page_content="[SİSTEM UYARISI] Bu konuda veritabanında net ve yeterli bir bilgi bulunamadı. Lütfen kullanıcıya 'Üzgünüm, belgelerde bu konuda kesin bir bilgi bulamadım. Lütfen sorunuzu farklı kelimelerle veya daha detaylı sormayı deneyin.' şeklinde yanıt ver.",
                        metadata={"source": "Sistem"}
                    )]
            
            return reranked_docs
        except Exception as e:
            logger.warning(f"Reranker hatası: {e}. Orijinal sonuçlar dönülüyor.")
            return unique_docs[:5]

    @staticmethod
    def _format_source_label(source):
        """Kaynak bilgisini kisa ve okunur etikete cevir."""
        if not source:
            return "Bilinmeyen Belge"

        source = str(source).strip()
        parsed = urlparse(source)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return parsed.netloc

        filename = os.path.basename(source.replace("\\", "/"))
        label = filename or source
        if label.lower().endswith(".pdf"):
            label = label[:-4]
        return label or "Bilinmeyen Belge"

    @staticmethod
    def _normalize_question_text(text):
        text = str(text or "").casefold()
        text = "".join(
            char for char in unicodedata.normalize("NFKD", text)
            if not unicodedata.combining(char)
        )
        replacements = {
            "ı": "i",
            "ğ": "g",
            "ü": "u",
            "ş": "s",
            "ö": "o",
            "ç": "c",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return " ".join(text.split())

    @classmethod
    def is_source_inventory_question(cls, question):
        """Kullanicinin mevcut index/kaynak envanterini istedigini yakala."""
        normalized = cls._normalize_question_text(question)
        if any(term in normalized for term in SOURCE_INVENTORY_TERMS):
            return True

        has_storage_term = any(term in normalized for term in ("veritabani", "veri tabani", "index", "chroma"))
        has_source_term = any(term in normalized for term in ("kaynak", "pdf", "dokuman", "belge"))
        has_list_intent = any(term in normalized for term in ("hangi", "liste", "neler", "var", "goster"))
        return has_storage_term and has_source_term and has_list_intent

    @staticmethod
    def _source_display_name(source, title=""):
        title = str(title or "").strip()
        if title:
            return title

        source = str(source or "").strip()
        if not source:
            return "Bilinmeyen Kaynak"

        parsed = urlparse(source)
        path = parsed.path if parsed.scheme else source
        filename = os.path.basename(unquote(path).replace("\\", "/"))
        if filename:
            return filename[:-4] if filename.lower().endswith(".pdf") else filename
        return source

    def get_source_inventory(self):
        """ChromaDB icindeki benzersiz kaynaklari ve parca sayilarini dondur."""
        try:
            data = self.static_db.get(include=["metadatas"])
        except TypeError:
            data = self.static_db.get()
        except Exception as exc:
            logger.warning("Kaynak envanteri alinamadi: %s", exc)
            return {
                "ok": False,
                "error": str(exc),
                "total_chunks": 0,
                "sources": [],
                "source_type_counts": {},
            }

        metadatas = data.get("metadatas") or []
        source_items = {}
        source_type_counts = Counter()

        for metadata in metadatas:
            metadata = metadata or {}
            source = metadata.get("source") or "Bilinmeyen Kaynak"
            item = source_items.setdefault(source, {
                "source": source,
                "title": metadata.get("title") or "",
                "source_type": metadata.get("source_type") or "unknown",
                "chunks": 0,
            })
            item["chunks"] += 1
            if not item.get("title") and metadata.get("title"):
                item["title"] = metadata.get("title")
            if item.get("source_type") == "unknown" and metadata.get("source_type"):
                item["source_type"] = metadata.get("source_type")

        for item in source_items.values():
            source_type_counts[item.get("source_type") or "unknown"] += 1

        sources = sorted(
            source_items.values(),
            key=lambda item: (-item["chunks"], self._source_display_name(item["source"], item.get("title")).casefold())
        )

        return {
            "ok": True,
            "total_chunks": len(metadatas),
            "unique_sources": len(sources),
            "sources": sources,
            "source_type_counts": dict(source_type_counts),
        }

    def build_source_inventory_answer(self, max_sources=120):
        """Mevcut veritabanindaki kaynaklari kullaniciya okunur sekilde anlat."""
        inventory = self.get_source_inventory()
        if not inventory.get("ok"):
            return (
                "Su an veritabanindaki kaynak listesini okuyamadim. "
                "ChromaDB baglantisi veya yerel veritabani dosyalari kontrol edilmeli."
            )

        sources = inventory.get("sources", [])
        if not sources:
            return "Su an veritabaninda kayitli bir kaynak gorunmuyor."

        type_counts = inventory.get("source_type_counts", {})
        pdf_count = type_counts.get("web_pdf", 0)
        web_count = type_counts.get("web_page", 0)
        unknown_count = type_counts.get("unknown", 0)

        summary_parts = []
        if pdf_count:
            summary_parts.append(f"{pdf_count} PDF")
        if web_count:
            summary_parts.append(f"{web_count} web sayfasi")
        if unknown_count:
            summary_parts.append(f"{unknown_count} diger kaynak")
        summary = ", ".join(summary_parts) if summary_parts else f"{len(sources)} kaynak"

        lines = [
            "Su an acik olan veritabaninda indekslenmis kaynaklar sunlar:",
            "",
            f"Toplam: {inventory.get('unique_sources', len(sources))} benzersiz kaynak ({summary}) ve {inventory.get('total_chunks', 0)} metin parcasi.",
            "",
        ]

        visible_sources = sources[:max_sources]
        for index, item in enumerate(visible_sources, start=1):
            source = item.get("source", "")
            name = self._source_display_name(source, item.get("title"))
            chunk_text = f"{item.get('chunks', 0)} parca"
            if str(source).startswith("http"):
                lines.append(f"{index}. [{name}]({source}) - {chunk_text}")
            else:
                lines.append(f"{index}. {name} - {chunk_text}")

        remaining = len(sources) - len(visible_sources)
        if remaining > 0:
            lines.append("")
            lines.append(f"...ve {remaining} kaynak daha var. Daha kisa bir liste icin belge turu veya birim adiyla sorabilirsin.")

        return "\n".join(lines)

    def format_context(self, docs):
        """Dokümanları kaynak bilgisiyle birlikte bağlam metnine çevir."""
        chunks = []
        for i, doc in enumerate(docs):
            source = self._format_source_label(doc.metadata.get("source"))
            chunks.append(f"[{i+1}] [Kaynak: {source}]\n{doc.page_content}")
        context = "\n\n".join(chunks)
        # Token taşmasını önlemek için maksimum karakter sayısını uygula
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS] + "\n...[bağlam kısaltıldı]"
        return context

    def stream_answer(self, question, context, chat_history="", mode="Akademik Rehber"):
        """Cevabı token token stream eder (generator)."""
        prompt_template = self.prompts.get(mode, self.prompts["Akademik Rehber"])
        prompt_value = prompt_template.invoke({
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
