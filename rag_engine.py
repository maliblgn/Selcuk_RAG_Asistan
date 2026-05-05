import os
import logging
import re
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
from check_chroma_health import check_chroma_health
from retrieval_rerank import legal_safe_query_allowed, rerank_documents

logger = logging.getLogger(__name__)

# Gonderilecek prompt parcasi limitleri (Groq 6000 TPM limitini asmayacak sekilde)
MAX_CHAT_HISTORY_CHARS = 2_500
MAX_REWRITE_HISTORY_CHARS = 1_200
MAX_ANSWER_CONTEXT_CHARS = 5_000
MAX_RETRY_CONTEXT_CHARS = 2_500
MAX_RETRY_HISTORY_CHARS = 800

# Geriye uyumluluk: format_context bu sabiti kullanir.
MAX_CONTEXT_CHARS = MAX_ANSWER_CONTEXT_CHARS

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


LIVE_INDEX_UNAVAILABLE_MESSAGE = (
    "Bilgi tabani canli ortamda hazir degil. "
    "Lutfen yonetici panelinden veri indeksleme islemini calistirin "
    "veya ChromaDB kalici depolamasini kontrol edin."
)

PROMPT_SOURCE_RULE = (
    "Cevabın sonunda Kaynak veya Kaynaklar başlığı açma. "
    "URL yazma. Kaynak listesini uygulama gösterecek."
)

INVENTORY_HISTORY_PLACEHOLDER = (
    "[Onceki mesajda veritabani kaynak envanteri listelendi; "
    "detaylar prompttan cikarildi.]"
)

FOLLOWUP_REFERENCE_TERMS = (
    "bu",
    "bunu",
    "bunun",
    "onda",
    "onu",
    "onun",
    "peki",
    "az once",
    "az önce",
    "yukaridaki",
    "yukarıdaki",
    "onceki",
    "önceki",
    "devam",
    "detaylandir",
    "detaylandır",
)


def trim_text_for_prompt(text: str, max_chars: int) -> str:
    """Prompt parcasini max_chars sinirinda tutup son kismi koru."""
    text = str(text or "")
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    marker = "[gecmis kisaltildi]\n"
    keep = max(0, max_chars - len(marker))
    return marker + text[-keep:]


def is_long_inventory_answer(text: str) -> bool:
    """Kaynak envanteri cevabinin chat_history'yi sisirmesini yakala."""
    text = str(text or "")
    normalized = SelcukRAGEngine._normalize_question_text(text)
    if "su an acik olan veritabaninda indekslenmis kaynaklar" in normalized:
        return True
    if re.search(r"toplam:\s*\d+\s+benzersiz kaynak", normalized):
        return True
    return len(re.findall(r"\b\d+\.\s+.*?\bparca\b", normalized)) >= 8


def sanitize_chat_history(chat_history: str, max_chars: int = MAX_CHAT_HISTORY_CHARS) -> str:
    """Uzun envanter cevaplarini at ve history'yi prompt butcesine sigdir."""
    text = str(chat_history or "").strip()
    if not text:
        return ""
    if is_long_inventory_answer(text):
        return INVENTORY_HISTORY_PLACEHOLDER

    lines = []
    inventory_block_seen = False
    for line in text.splitlines():
        if is_long_inventory_answer(line):
            if not inventory_block_seen:
                lines.append(INVENTORY_HISTORY_PLACEHOLDER)
                inventory_block_seen = True
            continue
        lines.append(line)
    return trim_text_for_prompt("\n".join(lines).strip(), max_chars)


def is_question_independent(question: str) -> bool:
    """Soru yeterince aciksa rewrite LLM cagrisini atla."""
    normalized = SelcukRAGEngine._normalize_question_text(question)
    tokens = set(normalized.split())
    if len(tokens) < 5:
        return False
    for term in FOLLOWUP_REFERENCE_TERMS:
        if " " in term:
            if term in normalized:
                return False
        elif term in tokens:
            return False
    return True


def is_prompt_size_error(error) -> bool:
    text = str(error or "").lower()
    return (
        "413" in text
        or "payload too large" in text
        or "request too large" in text
        or ("requested" in text and "tokens" in text and "limit" in text)
        or "rate_limit" in text
        or "rate limit" in text
        or "tpm" in text
    )

def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def normalize_user_question_for_retrieval(question):
    """Arama akisi icin liste numarasi ve gereksiz isaretleri temizle."""
    text = str(question or "").strip()
    for _ in range(3):
        text = text.strip().strip("\"'“”‘’`")
        text = re.sub(r"^\s*(?:[-*+]\s+)+", "", text)
        text = re.sub(r"^\s*\d+\s*[\.)]\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def strip_model_generated_sources(answer: str) -> str:
    """Modelin sonda urettigi kaynak bloklarini kaldir, inline [1] atiflari koru."""
    text = str(answer or "").strip()
    if not text:
        return text

    source_heading_re = re.compile(r"(?im)^\s*(?:#+\s*)?Kaynak(?:lar)?\s*:\s*.*$")
    match = source_heading_re.search(text)
    if match:
        text = text[:match.start()].rstrip()

    lines = []
    skipping_url_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^(?:[-*]\s*)?https?://\S+", stripped):
            skipping_url_block = True
            continue
        if skipping_url_block and not stripped:
            skipping_url_block = False
            continue
        if skipping_url_block:
            continue
        lines.append(line)

    return "\n".join(lines).strip()


class KnowledgeBaseUnavailableError(RuntimeError):
    """ChromaDB index is missing, empty, or unreadable."""

    def __init__(self, message=LIVE_INDEX_UNAVAILABLE_MESSAGE, health=None):
        self.health = health or {}
        detail = self.health.get("error") or self.health.get("reason") or ""
        super().__init__(f"{message} Teknik durum: {detail}".strip())

    @property
    def user_message(self):
        return LIVE_INDEX_UNAVAILABLE_MESSAGE


def is_chroma_collection_error(error):
    text = str(error or "").lower()
    return (
        "collection" in text
        and ("does not exist" in text or "error getting collection" in text)
    )


class SelcukRAGEngine:
    def __init__(self, enable_llm=True):
        logger.info("SelcukRAGEngine başlatılıyor...")
        # 1. Embedding Modelini Yükle
        self.db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
        self.db_health = check_chroma_health(self.db_dir)
        if not self.db_health.get("ok"):
            logger.error("ChromaDB hazir degil: %s", self.db_health)
            raise KnowledgeBaseUnavailableError(health=self.db_health)

        self.embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
        
        # 2. Statik Veritabanını Bağla
        try:
            self.static_db = Chroma(persist_directory=self.db_dir, embedding_function=self.embeddings)
        except Exception as exc:
            logger.exception("ChromaDB collection baglantisi kurulamadi: %s", exc)
            health = check_chroma_health(self.db_dir)
            health["error"] = str(exc)
            raise KnowledgeBaseUnavailableError(health=health) from exc
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
        self.llm = None
        if enable_llm:
            self.llm = ChatGroq(model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"), temperature=0)
        
        # 4. Modlara Özel Promptlar (Multi-Agent UI)
        common_rules = (
            "KESİN KURALLAR:\n"
            "1. Eğer cevap bağlamda (context) yoksa ASLA uydurma. 'Bu bilgi dökümanlarda yer almıyor' de.\n"
            "2. Bağlamdaki rakamlara %100 sadık kal.\n"
            "3. Sadece Türkçe konuş.\n"
            "4. Cevabındaki bilgilerin sonuna mutlaka bağlamdaki kaynak numarasını [1], [2] şeklinde ekle (Inline Citation).\n"
            "5. Cevap içinde sadece [1], [2] inline citation kullan.\n"
            f"6. {PROMPT_SOURCE_RULE}\n\n"
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
        try:
            self.reranker = FlashrankRerank(top_n=5)
        except Exception as e:
            logger.warning("FlashRank yuklenemedi, reranking devre disi: %s", e)
            self.reranker = None
        
        logger.info("SelcukRAGEngine hazır.")

    def rewrite_query(self, question, chat_history):
        """Takip sorularını bağımsız sorulara çevir."""
        question = normalize_user_question_for_retrieval(question)
        if not chat_history or len(chat_history.strip()) == 0:
            return question
        if is_question_independent(question):
            logger.info("Soru bagimsiz gorunuyor; rewrite LLM cagrisi atlandi.")
            return question

        safe_history = sanitize_chat_history(
            chat_history,
            max_chars=MAX_REWRITE_HISTORY_CHARS,
        )
        if not safe_history:
            return question
        
        try:
            chain = self.rewrite_prompt | self.llm | StrOutputParser()
            rewritten = chain.invoke({"question": question, "chat_history": safe_history})
            logger.info(f"Soru yeniden yazıldı: '{question}' → '{rewritten.strip()}'")
            return normalize_user_question_for_retrieval(rewritten)
        except Exception as e:
            logger.warning(f"Soru yeniden yazılamadı, orijinal kullanılıyor: {e}")
            return question

    def _generate_multi_queries(self, question):
        """Kullanicinin sorgusunu guvenli alternatif sorgulara cevirir."""
        question = normalize_user_question_for_retrieval(question)
        if not env_bool("MULTI_QUERY_ENABLED", True):
            return [question]

        try:
            chain = self.multi_query_prompt | self.llm | StrOutputParser()
            result = chain.invoke({"question": question})
            queries = [q.strip() for q in result.strip().split("\n") if q.strip()]
            clean_queries = []
            for query in queries:
                clean_query = normalize_user_question_for_retrieval(query)
                if not clean_query or clean_query == question:
                    continue
                if env_bool("MULTI_QUERY_LEGAL_SAFE_MODE", True) and not legal_safe_query_allowed(question, clean_query):
                    logger.info("Legal safe mode multi-query varyasyonunu eledi: %s", clean_query)
                    continue
                clean_queries.append(clean_query)
            return [question] + clean_queries[:3]
        except Exception as e:
            if is_prompt_size_error(e):
                logger.warning("Multi-query token/rate limit nedeniyle atlandi: %s", e)
            else:
                logger.warning(f"Multi-query üretilemedi: {e}")
            return [question]

    def _akts_definition_fallback_docs(self, question, limit=3):
        """AKTS tanim sorularinda lisansustu Madde 4 adayini hybrid havuzuna ekle."""
        normalized = self._normalize_question_text(question)
        if "akts" not in normalized:
            return []

        source_specific_terms = (
            "staj",
            "fen fakultesi",
            "fen",
            "cift ana dal",
            "cift anadal",
            "cap",
            "yandal",
            "diploma",
            "yaz okulu",
            "pedagojik formasyon",
        )
        if any(term in normalized for term in source_specific_terms):
            return []

        try:
            data = self.static_db.get(include=["documents", "metadatas"])
        except Exception as exc:
            logger.debug("AKTS fallback adaylari okunamadi: %s", exc)
            return []

        docs = []
        for content, metadata in zip(data.get("documents") or [], data.get("metadatas") or []):
            metadata = dict(metadata or {})
            content_text = str(content or "")
            content_norm = self._normalize_question_text(content_text)
            source_text = self._normalize_question_text(
                f"{unquote(str(metadata.get('title') or ''))} "
                f"{unquote(str(metadata.get('source') or ''))}"
            )
            article_title = self._normalize_question_text(metadata.get("article_title") or "")
            if not (
                "akts" in content_norm
                and str(metadata.get("article_no") or "") == "4"
                and "tanimlar" in article_title
                and "lisansustu" in source_text
                and "yonetmel" in source_text
            ):
                continue
            metadata["metadata_fallback"] = "akts_lisansustu_article_4"
            docs.append(Document(page_content=content_text, metadata=metadata))
            if len(docs) >= limit:
                break
        return docs

    def retrieve(self, question, dynamic_docs=None, top_k=5):
        """Soruya en uygun doküman parçalarını getir."""
        question = normalize_user_question_for_retrieval(question)
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
        all_docs.extend(self._akts_definition_fallback_docs(question))
                
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
            
        metadata_ranked_docs = unique_docs
        if env_bool("METADATA_RERANK_ENABLED", True):
            metadata_ranked_docs = rerank_documents(question, unique_docs)
            candidate_k = max(top_k, env_int("METADATA_RERANK_CANDIDATE_K", 40))
            metadata_ranked_docs = metadata_ranked_docs[:candidate_k]
            logger.info(
                "Metadata-aware rerank aktif: %d aday siralandi, en iyi skor %.2f",
                len(metadata_ranked_docs),
                metadata_ranked_docs[0].metadata.get("metadata_rerank_score", 0.0) if metadata_ranked_docs else 0.0,
            )

        strong_metadata_docs = [
            doc for doc in metadata_ranked_docs
            if doc.metadata.get("metadata_strong_match")
            or doc.metadata.get("metadata_rerank_score", 0.0) >= 16.0
        ]

        # 4. Cross-Encoder Re-ranking
        if self.reranker is None:
            logger.info("Reranker devre disi, metadata sirali ilk dokumanlar donduruluyor.")
            return metadata_ranked_docs[:top_k]

        try:
            reranked_docs = self.reranker.compress_documents(metadata_ranked_docs, question)
            logger.info(f"Reranking sonrası {len(reranked_docs)} doküman seçildi.")

            merged_docs = []
            seen_after_rerank = set()

            def add_doc(doc):
                content_hash = hash(doc.page_content)
                if content_hash in seen_after_rerank:
                    return
                seen_after_rerank.add(content_hash)
                merged_docs.append(doc)

            for doc in strong_metadata_docs[:top_k]:
                add_doc(doc)
            for doc in reranked_docs:
                add_doc(doc)
            for doc in metadata_ranked_docs:
                add_doc(doc)

            final_docs = merged_docs[:top_k]

            # 5. Threshold kontrolu. Metadata guclu eslesme varsa sistem uyari dokumani uretme.
            if final_docs:
                top_score = final_docs[0].metadata.get("relevance_score", 1.0)
                logger.info(f"En iyi doküman skoru: {top_score}")
                if top_score < 0.6 and not strong_metadata_docs:
                    logger.warning("Bulunan sonuçlar eşik değerinin altında (Güvensiz bilgi).")
                    return [Document(
                        page_content="[SISTEM UYARISI] Bu konuda veritabanında net ve yeterli bir bilgi bulunamadı. Lütfen kullanıcıya 'Üzgünüm, belgelerde bu konuda kesin bir bilgi bulamadım. Lütfen sorunuzu farklı kelimelerle veya daha detaylı sormayı deneyin.' şeklinde yanıt ver.",
                        metadata={"source": "Sistem"}
                    )]

            return final_docs
        except Exception as e:
            logger.warning(f"Reranker hatası: {e}. Metadata sıralı sonuçlar dönülüyor.")
            return metadata_ranked_docs[:top_k]

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
    def _format_page_range(metadata):
        page_start = metadata.get("page_start") or metadata.get("page")
        page_end = metadata.get("page_end") or metadata.get("page")
        if not page_start and not page_end:
            return ""
        if page_start and page_end and str(page_start) != str(page_end):
            return f"{page_start}-{page_end}"
        return str(page_start or page_end)

    @classmethod
    def build_source_metadata(cls, doc):
        """UI ve LLM context icin ayni kaynak/madde etiketini uret."""
        metadata = dict(getattr(doc, "metadata", {}) or {})
        source = metadata.get("source") or ""
        title = metadata.get("title") or ""
        label = cls._source_display_name(source, title)
        article_no = metadata.get("article_no")
        article_title = metadata.get("article_title") or ""
        page = cls._format_page_range(metadata)
        article_label = ""
        if article_no and article_title:
            article_label = f"Madde {article_no} - {article_title}"
        elif article_no:
            article_label = f"Madde {article_no}"
        elif article_title:
            article_label = str(article_title)
        return {
            "label": label,
            "source": source,
            "article_no": article_no,
            "article_title": article_title,
            "article_label": article_label,
            "page": page,
            "url": source if str(source).startswith(("http://", "https://")) else "",
        }

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
    def _clean_source_name(name):
        name = unquote(str(name or "").strip())
        if name.lower().endswith(".pdf"):
            name = name[:-4]
        return re.sub(r"_[0-9]{10,}$", "", name)

    @staticmethod
    def _source_display_name(source, title=""):
        title = SelcukRAGEngine._clean_source_name(title)
        if title:
            return title

        source = str(source or "").strip()
        if not source:
            return "Bilinmeyen Belge"

        parsed = urlparse(source)
        path = parsed.path if parsed.scheme else source
        normalized_path = unquote(path).replace("\\", "/").rstrip("/")
        filename = normalized_path.rsplit("/", 1)[-1]
        if filename:
            return SelcukRAGEngine._clean_source_name(filename)
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

    @classmethod
    def build_source_inventory_answer_from_db(cls, db_dir=None, max_sources=30):
        """RAG motorunu baslatmadan ChromaDB kaynak envanteri cevabi uret."""
        db_dir = db_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
        health = check_chroma_health(db_dir)
        if not health.get("ok"):
            logger.warning("Kaynak envanteri icin ChromaDB hazir degil: %s", health)
            return LIVE_INDEX_UNAVAILABLE_MESSAGE
        try:
            db = Chroma(persist_directory=db_dir)
            engine = cls.__new__(cls)
            engine.static_db = db
            return engine.build_source_inventory_answer(max_sources=max_sources)
        except Exception as exc:
            logger.warning("Kaynak envanteri hafif modda alinamadi: %s", exc)
            return (
                "Su an veritabanindaki kaynak listesini okuyamadim. "
                "Canli ortamda ChromaDB dosyalari veya veritabani baglantisi kontrol edilmeli."
            )

    def build_source_inventory_answer(self, max_sources=30):
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
            source_info = self.build_source_metadata(doc)
            header = [f"[{i+1}] Kaynak: {source_info['label']}"]
            if source_info["article_label"]:
                header.append(f"Madde: {source_info['article_label'].replace('Madde ', '', 1)}")
            if source_info["page"]:
                header.append(f"Sayfa: {source_info['page']}")
            if source_info["url"]:
                header.append(f"URL: {source_info['url']}")
            header.append("İçerik:")
            chunks.append("\n".join(header) + f"\n{doc.page_content}")
        context = "\n\n".join(chunks)
        # Token taşmasını önlemek için maksimum karakter sayısını uygula
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS] + "\n...[bağlam kısaltıldı]"
        return context

    def stream_answer(self, question, context, chat_history="", mode="Akademik Rehber"):
        """Cevabı token token stream eder (generator)."""
        question = normalize_user_question_for_retrieval(question)
        prompt_template = self.prompts.get(mode, self.prompts["Akademik Rehber"])
        safe_context = trim_text_for_prompt(context, MAX_ANSWER_CONTEXT_CHARS)
        safe_history = sanitize_chat_history(chat_history, max_chars=MAX_CHAT_HISTORY_CHARS)

        def _stream_once(context_text, history_text):
            prompt_value = prompt_template.invoke({
                "context": context_text,
                "chat_history": history_text,
                "input": question
            })
            yield from self.llm.stream(prompt_value)

        def _safe_stream():
            try:
                yield from _stream_once(safe_context, safe_history)
            except Exception as exc:
                if not is_prompt_size_error(exc):
                    raise
                logger.warning("Groq prompt/token limiti asildi, kisa baglamla tekrar deneniyor: %s", exc)
                yield "Yanıt oluştururken bağlam çok uzun geldi. Daha kısa bağlamla tekrar deniyorum.\n\n"
                retry_context = trim_text_for_prompt(safe_context, MAX_RETRY_CONTEXT_CHARS)
                retry_history = sanitize_chat_history(safe_history, max_chars=MAX_RETRY_HISTORY_CHARS)
                try:
                    yield from _stream_once(retry_context, retry_history)
                except Exception as retry_exc:
                    logger.warning("Kisa baglam retry denemesi basarisiz: %s", retry_exc)
                    yield (
                        "Yanıt oluştururken modelin token/istek limitine takıldım. "
                        "Lütfen soruyu biraz daha daraltarak tekrar deneyin."
                    )

        return _safe_stream()

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
