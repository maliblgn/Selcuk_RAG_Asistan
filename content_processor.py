"""
Semantik veri isleme modulu — Selcuk Universitesi RAG Asistani.

Uc temel bileseni icerir:
1. ContentExtractor: trafilatura ile boilerplate temizleme + Markdown cikti
2. SmartChunker: Header-aware + SemanticChunker pipeline
3. MetadataEnricher: URL/baslik'tan birim, dokuman tipi, tarih, ozet cikarma
"""

import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


# =====================================================================
#  ContentExtractor — Boilerplate Removal & Markdown Extraction
# =====================================================================

class ContentExtractor:
    """trafilatura tabanli icerik cikarma motoru.

    Fallback zinciri:
    1. trafilatura (favor_precision, include_tables, markdown)
    2. Mevcut BeautifulSoup yontemi (web_scraper.ContentCleaner)
    """

    @staticmethod
    def extract_main_content(html: str, url: str = "") -> Optional[str]:
        """HTML'den ana icerigi Markdown olarak cikar.

        Args:
            html: Ham HTML icerik.
            url: Sayfa URL'si (trafilatura'ya ipucu).

        Returns:
            Temiz Markdown metin veya None.
        """
        if not html or not html.strip():
            return None

        # 1. trafilatura ile cikarma
        try:
            import trafilatura

            content = trafilatura.extract(
                html,
                output_format="markdown",
                include_tables=True,
                include_formatting=True,
                include_links=False,
                favor_precision=True,
                url=url or None,
            )
            if content and len(content.strip()) > 0:
                cleaned = ContentExtractor.clean_markdown(content)
                if not ContentExtractor.is_junk(cleaned):
                    return cleaned
                logger.debug("trafilatura sonucu junk: %s (%d char)", url, len(cleaned))
        except Exception as exc:
            logger.warning("trafilatura hatasi, fallback'e geciliyor: %s", exc)

        # 2. Fallback: BeautifulSoup
        try:
            from web_scraper import ContentCleaner
            fallback_text = ContentCleaner.clean_page_text(html)
            if fallback_text and not ContentExtractor.is_junk(fallback_text):
                return fallback_text
        except Exception as exc:
            logger.warning("BS4 fallback hatasi: %s", exc)

        return None

    @staticmethod
    def is_junk(text: str, min_chars: int = 200) -> bool:
        """Temizlenmis metin anlamli mi yoksa junk mi?

        Args:
            text: Kontrol edilecek metin.
            min_chars: Minimum karakter esigi.

        Returns:
            True ise icerik junk (yetersiz).
        """
        if not text:
            return True
        stripped = text.strip()
        if len(stripped) < min_chars:
            return True

        # Cok fazla tekrar eden kisa satir varsa (menu kalintisi)
        lines = [l.strip() for l in stripped.splitlines() if l.strip()]
        if lines:
            avg_line_len = len(stripped) / len(lines)
            if avg_line_len < 15 and len(lines) > 5:
                return True

        return False

    @staticmethod
    def clean_markdown(text: str) -> str:
        """Markdown metnini son kez temizle.

        - Ardisik bos satirlari tek satira indir
        - Unicode normalize et
        - Navigasyon kalintisi pattern'larini sil
        """
        if not text:
            return ""

        # Unicode normalizasyon
        cleaned = unicodedata.normalize("NFKC", text)

        # Ardisik bos satirlari ikiye indir
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        # Navigasyon kalintilari (| ile ayrilmis kisa linkler)
        cleaned = re.sub(
            r"^([ \t]*[\w ]{1,30}[ \t]*\|)+[ \t]*[\w ]{1,30}[ \t]*$",
            "",
            cleaned,
            flags=re.MULTILINE,
        )

        # Bas/son bosluk
        cleaned = cleaned.strip()

        return cleaned


# =====================================================================
#  SmartChunker — Semantic Chunking Pipeline
# =====================================================================

class SmartChunker:
    """Iki asamali semantik parcalama pipeline'i.

    Pipeline:
    1. MarkdownHeaderTextSplitter → baslik bazli bolme
    2. SemanticChunker → konu degisim noktalarinda bolme (sadece uzun sectionlar)
    3. Fallback: RecursiveCharacterTextSplitter (SemanticChunker basarisiz olursa)
    """

    # SemanticChunker sadece bu esigi asan sectionlara uygulanir
    SEMANTIC_THRESHOLD_CHARS = 3000

    # Fallback chunker ayarlari
    FALLBACK_CHUNK_SIZE = 1000
    FALLBACK_CHUNK_OVERLAP = 200

    def __init__(self, embeddings=None):
        """SmartChunker olustur.

        Args:
            embeddings: Embedding modeli (None ise varsayilan yuklenir).
        """
        self._embeddings = embeddings
        self._semantic_chunker = None

    @property
    def embeddings(self):
        """Lazy-load embedding modeli."""
        if self._embeddings is None:
            from langchain_huggingface import HuggingFaceEmbeddings
            self._embeddings = HuggingFaceEmbeddings(
                model_name="intfloat/multilingual-e5-small"
            )
        return self._embeddings

    def chunk_documents(self, docs: List[Document]) -> List[Document]:
        """Ana chunking pipeline.

        Args:
            docs: LangChain Document listesi (page_content Markdown olmali).

        Returns:
            Parcalanmis Document listesi (metadata korunur + header metadata eklenir).
        """
        all_chunks: List[Document] = []

        for doc in docs:
            try:
                chunks = self._process_single_document(doc)
                all_chunks.extend(chunks)
            except Exception as exc:
                logger.warning(
                    "SmartChunker hatasi, fallback kullaniliyor: %s", exc
                )
                chunks = self._split_recursive_fallback(doc)
                all_chunks.extend(chunks)

        logger.info(
            "SmartChunker: %d dokumandan %d parca olusturuldu.",
            len(docs),
            len(all_chunks),
        )
        return all_chunks

    def _process_single_document(self, doc: Document) -> List[Document]:
        """Tek bir dokumani isle: header split → semantic split."""
        # 1. Header-based splitting
        header_sections = self._split_by_headers(doc)

        # 2. Her section icin: uzunsa semantic split, kisaysa olduğu gibi
        final_chunks: List[Document] = []

        for section in header_sections:
            content_len = len(section.page_content)

            if content_len > self.SEMANTIC_THRESHOLD_CHARS:
                # Uzun section → SemanticChunker dene
                try:
                    semantic_chunks = self._split_semantically(section)
                    final_chunks.extend(semantic_chunks)
                except Exception as exc:
                    logger.debug(
                        "SemanticChunker basarisiz, fallback: %s", exc
                    )
                    fallback_chunks = self._split_recursive_fallback(section)
                    final_chunks.extend(fallback_chunks)
            elif content_len > self.FALLBACK_CHUNK_SIZE:
                # Orta uzunlukta → RecursiveCharacterTextSplitter
                fallback_chunks = self._split_recursive_fallback(section)
                final_chunks.extend(fallback_chunks)
            else:
                # Kisa section → olduğu gibi birak
                if content_len > 50:  # Cok kisa parcalari atla
                    final_chunks.append(section)

        return final_chunks

    def _split_by_headers(self, doc: Document) -> List[Document]:
        """Markdown basliklarini sınır olarak kullan.

        Returns:
            Her section'ın metadata'sinda header bilgisi olan Document listesi.
        """
        from langchain_text_splitters import MarkdownHeaderTextSplitter

        headers_to_split_on = [
            ("#", "header_1"),
            ("##", "header_2"),
            ("###", "header_3"),
        ]

        splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=False,  # Baslik metnini icerige dahil et
        )

        try:
            sections = splitter.split_text(doc.page_content)
        except Exception as exc:
            logger.debug("MarkdownHeaderSplitter hatasi: %s", exc)
            # Baslik bulunamazsa tum dokumani tek section olarak dondur
            return [doc]

        if not sections:
            return [doc]

        # Orijinal metadata'yi her section'a aktar
        result: List[Document] = []
        for section in sections:
            merged_meta = {**doc.metadata, **section.metadata}
            result.append(
                Document(page_content=section.page_content, metadata=merged_meta)
            )

        return result

    def _split_semantically(self, doc: Document) -> List[Document]:
        """SemanticChunker ile konu butunlugune gore bol."""
        from langchain_experimental.text_splitter import SemanticChunker

        chunker = SemanticChunker(
            self.embeddings,
            breakpoint_threshold_type="percentile",
        )

        chunks = chunker.create_documents([doc.page_content])

        # Metadata'yi aktar
        result: List[Document] = []
        for chunk in chunks:
            merged_meta = {**doc.metadata, **chunk.metadata}
            result.append(
                Document(page_content=chunk.page_content, metadata=merged_meta)
            )

        return result

    def _split_recursive_fallback(self, doc: Document) -> List[Document]:
        """Guvenli RecursiveCharacterTextSplitter fallback."""
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.FALLBACK_CHUNK_SIZE,
            chunk_overlap=self.FALLBACK_CHUNK_OVERLAP,
            separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " "],
        )

        chunks = splitter.split_documents([doc])
        return chunks


# =====================================================================
#  MetadataEnricher — Taxonomy & Tagging
# =====================================================================

class MetadataEnricher:
    """Chunk'lara zengin metadata ekler.

    - unit: Birim/fakulte adi (URL + baslik analizi)
    - doc_type: Dokuman tipi (yonetmelik/haber/duyuru/genel)
    - crawled_at: Tarama zamani
    - content_date: Icerikteki tarih (varsa)
    - summary: Tek cumlelik baglam bilgisi (prefix injection)
    """

    # Selcuk URL yapisindan birim cikarma haritasi
    UNIT_MAP: Dict[str, str] = {
        "muhendislik": "Mühendislik Fakültesi",
        "fen": "Fen Fakültesi",
        "edebiyat": "Edebiyat Fakültesi",
        "hukuk": "Hukuk Fakültesi",
        "tip": "Tıp Fakültesi",
        "egitim": "Eğitim Fakültesi",
        "iktisat": "İktisadi ve İdari Bilimler Fakültesi",
        "iibf": "İktisadi ve İdari Bilimler Fakültesi",
        "ilahiyat": "İlahiyat Fakültesi",
        "ziraat": "Ziraat Fakültesi",
        "iletisim": "İletişim Fakültesi",
        "saglik": "Sağlık Bilimleri Fakültesi",
        "spor": "Spor Bilimleri Fakültesi",
        "veteriner": "Veteriner Fakültesi",
        "disilekimi": "Diş Hekimliği Fakültesi",
        "dishekimligi": "Diş Hekimliği Fakültesi",
        "eczacilik": "Eczacılık Fakültesi",
        "teknoloji": "Teknoloji Fakültesi",
        "guzelsanatlar": "Güzel Sanatlar Fakültesi",
        "mimarlik": "Mimarlık Fakültesi",
        "sosyalbilimler": "Sosyal Bilimler Enstitüsü",
        "fenbilimleri": "Fen Bilimleri Enstitüsü",
        "sagliklilimleri": "Sağlık Bilimleri Enstitüsü",
        "sks": "Sağlık Kültür ve Spor Daire Başkanlığı",
        "ogrenciisleri": "Öğrenci İşleri Daire Başkanlığı",
        "ogrenci": "Öğrenci İşleri",
        "kutuphane": "Kütüphane ve Dokümantasyon",
        "rektorluk": "Rektörlük",
        "yemekhane": "Yemekhane",
        "bap": "Bilimsel Araştırma Projeleri",
        "kariyer": "Kariyer Merkezi",
        "erasmus": "Erasmus Koordinatörlüğü",
        "uzem": "Uzaktan Eğitim Merkezi",
    }

    # Dokuman tipi tespit pattern'lari
    DOC_TYPE_PATTERNS: Dict[str, str] = {
        "yonetmelik": "yönetmelik",
        "yönetmelik": "yönetmelik",
        "yonerge": "yönerge",
        "yönergesi": "yönerge",
        "yönergeler": "yönerge",
        "haber": "haber",
        "duyuru": "duyuru",
        "ilan": "duyuru",
        "genelge": "genelge",
        "karar": "karar",
        "takvim": "akademik_takvim",
        "akademik-takvim": "akademik_takvim",
        "burs": "burs",
        "staj": "staj",
        "mezuniyet": "mezuniyet",
        "kayit": "kayıt",
        "sinav": "sınav",
    }

    # Tarih regex pattern'lari (Turkce tarih formatlari)
    DATE_PATTERNS = [
        # 15.09.2024, 15/09/2024
        r"(\d{1,2})[./](\d{1,2})[./](20\d{2})",
        # 2024-09-15
        r"(20\d{2})-(\d{1,2})-(\d{1,2})",
        # "15 Eylül 2024" gibi Turkce tarih
        r"(\d{1,2})\s+(Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|"
        r"Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+(20\d{2})",
    ]

    @staticmethod
    def detect_unit(url: str, title: str = "") -> str:
        """URL ve basliktan birim/fakulte adini tespit et.

        Oncelik: subdomain → URL path → baslik icerigi.
        """
        combined = f"{url} {title}".lower()
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()

        # 1. Subdomain kontrolu (muhendislik.selcuk.edu.tr)
        if hostname and hostname != "selcuk.edu.tr" and hostname != "www.selcuk.edu.tr":
            subdomain = hostname.split(".")[0]
            for key, name in MetadataEnricher.UNIT_MAP.items():
                if key in subdomain:
                    return name

        # 2. URL path kontrolu (/muhendislik/..., /sks/...)
        path = (parsed.path or "").lower()
        path_parts = [p for p in path.split("/") if p]
        if path_parts:
            first_segment = path_parts[0]
            for key, name in MetadataEnricher.UNIT_MAP.items():
                if key in first_segment:
                    return name

        # 3. Baslik icerigi kontrolu
        for key, name in MetadataEnricher.UNIT_MAP.items():
            if key in combined:
                return name

        return "Genel"

    @staticmethod
    def detect_doc_type(url: str, title: str = "", content: str = "") -> str:
        """Dokuman tipini tespit et."""
        combined = f"{url} {title} {content[:300]}".lower()

        for pattern, doc_type in MetadataEnricher.DOC_TYPE_PATTERNS.items():
            if pattern in combined:
                return doc_type

        return "genel"

    @staticmethod
    def extract_date_from_content(text: str) -> Optional[str]:
        """Metin icindeki guncelleme tarihini regex ile bulmaya calis.

        Returns:
            ISO format tarih string'i veya None.
        """
        if not text:
            return None

        # Sadece ilk 1000 karaktere bak (performans)
        search_text = text[:1000]

        for pattern in MetadataEnricher.DATE_PATTERNS:
            match = re.search(pattern, search_text)
            if match:
                try:
                    raw = match.group(0)
                    # Basit format denemeleri
                    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
                        try:
                            dt = datetime.strptime(raw, fmt)
                            return dt.strftime("%Y-%m-%d")
                        except ValueError:
                            continue
                    # Turkce ay isimli format
                    return raw
                except Exception:
                    continue

        return None

    @staticmethod
    def generate_summary(
        title: str = "",
        unit: str = "",
        doc_type: str = "",
        header_1: str = "",
        header_2: str = "",
    ) -> str:
        """Chunk'in basina eklenecek tek cumlelik baglam bilgisi olustur.

        LLM kullanmaz — kural tabanli basit format.

        Returns:
            "[Baglam: ...]" formatlı ozet string.
        """
        parts = []

        if unit and unit != "Genel":
            parts.append(unit)

        if title:
            parts.append(title)
        if header_1 and header_1 != title:
            parts.append(header_1)

        if header_2 and header_2 != title and header_2 != header_1:
            parts.append(header_2)

        if doc_type and doc_type != "genel":
            type_label = doc_type.replace("_", " ").title()
            parts.append(type_label)

        if not parts:
            return ""

        return f"[Bağlam: {' — '.join(parts)}]"

    @classmethod
    def enrich_document(cls, doc: Document) -> Document:
        """Tek bir Document'a zengin metadata ekle.

        - unit, doc_type, crawled_at, content_date, summary
        - Summary prefix injection (page_content basina eklenir)
        """
        meta = dict(doc.metadata)
        source = meta.get("source", "")
        title = meta.get("title", "")
        content = doc.page_content

        # Birim tespiti
        unit = cls.detect_unit(source, title)
        meta["unit"] = unit

        # Dokuman tipi tespiti
        doc_type = cls.detect_doc_type(source, title, content)
        meta["doc_type"] = doc_type

        # Tarama zamani
        if "crawled_at" not in meta:
            meta["crawled_at"] = datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            )

        # Icerik tarihi
        content_date = cls.extract_date_from_content(content)
        if content_date:
            meta["content_date"] = content_date

        # Ozet olustur + prefix injection
        summary = cls.generate_summary(
            title=title,
            unit=unit,
            doc_type=doc_type,
            header_1=meta.get("header_1", ""),
            header_2=meta.get("header_2", ""),
        )
        meta["summary"] = summary

        # Prefix injection: chunk metninin basina baglam ekle
        if summary:
            enriched_content = f"{summary}\n\n{content}"
        else:
            enriched_content = content

        return Document(page_content=enriched_content, metadata=meta)

    @classmethod
    def enrich_documents(cls, docs: List[Document]) -> List[Document]:
        """Birden fazla Document'i zenginlestir."""
        enriched = []
        for doc in docs:
            try:
                enriched.append(cls.enrich_document(doc))
            except Exception as exc:
                logger.warning("Metadata enrichment hatasi: %s", exc)
                enriched.append(doc)  # Hata durumunda orijinali koru
        logger.info("%d dokumana metadata eklendi.", len(enriched))
        return enriched
