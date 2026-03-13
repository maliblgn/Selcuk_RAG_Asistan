"""
Selçuk RAG Asistanı – Birim Testleri
Gerçek LLM / embedding çağrısı yapmadan saf Python mantığını test eder.
"""
import os
import sys
import types
import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub harici bağımlılıkları: LLM ve embedding çağrısı olmadan test et
# ---------------------------------------------------------------------------

def _make_stub_modules():
    """langchain ve chromadb stub'larını oluştur."""
    # langchain_huggingface
    lc_hf = types.ModuleType("langchain_huggingface")
    lc_hf.HuggingFaceEmbeddings = MagicMock()
    sys.modules.setdefault("langchain_huggingface", lc_hf)

    # langchain_chroma
    lc_chroma = types.ModuleType("langchain_chroma")
    lc_chroma.Chroma = MagicMock()
    sys.modules.setdefault("langchain_chroma", lc_chroma)

    # langchain_groq
    lc_groq = types.ModuleType("langchain_groq")
    lc_groq.ChatGroq = MagicMock()
    sys.modules.setdefault("langchain_groq", lc_groq)

    # langchain_core.prompts
    lc_core_prompts = types.ModuleType("langchain_core.prompts")
    class FakePromptTemplate:
        @staticmethod
        def from_template(template):
            obj = MagicMock()
            obj._template = template
            return obj
    lc_core_prompts.ChatPromptTemplate = FakePromptTemplate
    sys.modules.setdefault("langchain_core", types.ModuleType("langchain_core"))
    sys.modules.setdefault("langchain_core.prompts", lc_core_prompts)

    # langchain_core.output_parsers
    lc_core_parsers = types.ModuleType("langchain_core.output_parsers")
    lc_core_parsers.StrOutputParser = MagicMock()
    sys.modules.setdefault("langchain_core.output_parsers", lc_core_parsers)


_make_stub_modules()

# Proje kökünü sys.path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import rag_engine  # noqa: E402  (stub'lar hazır olduktan sonra import)
from rag_engine import MAX_CONTEXT_CHARS  # noqa: E402


# ---------------------------------------------------------------------------
# Yardımcı: sahte Document nesnesi
# ---------------------------------------------------------------------------

class FakeDoc:
    def __init__(self, content, source="test.pdf"):
        self.page_content = content
        self.metadata = {"source": source}


# ---------------------------------------------------------------------------
# format_context testleri
# ---------------------------------------------------------------------------

class TestFormatContext:
    """format_context metodunu test eder."""

    def _get_engine(self):
        """Gerçek __init__ çalıştırmadan motor nesnesini oluşturur."""
        engine = rag_engine.SelcukRAGEngine.__new__(rag_engine.SelcukRAGEngine)
        return engine

    def test_kaynak_etiketi_eklenir(self):
        """Her parça [Kaynak: ...] etiketi içermeli."""
        engine = self._get_engine()
        docs = [FakeDoc("Burslara başvuru şartları...", "Burs Yönergesi.pdf")]
        ctx = engine.format_context(docs)
        assert "[Kaynak: Burs Yönergesi]" in ctx
        assert "Burslara başvuru şartları..." in ctx

    def test_birden_fazla_kaynak(self):
        """Birden fazla belgeden gelen parçaların hepsi etiketlenmeli."""
        engine = self._get_engine()
        docs = [
            FakeDoc("Staj içeriği...", "Staj Yönergesi.pdf"),
            FakeDoc("Diploma içeriği...", "Diploma Yönerge.pdf"),
        ]
        ctx = engine.format_context(docs)
        assert "[Kaynak: Staj Yönergesi]" in ctx
        assert "[Kaynak: Diploma Yönerge]" in ctx

    def test_bos_liste_bos_string_dondurur(self):
        engine = self._get_engine()
        assert engine.format_context([]) == ""

    def test_max_context_uzunluk_siniri(self):
        """Uzun bağlam MAX_CONTEXT_CHARS karakterde kesilmeli."""
        LABEL_TOLERANCE = 50  # [Kaynak: ...] etiketi ve ek satırlar için tolerans
        engine = self._get_engine()
        uzun_icerik = "a" * (MAX_CONTEXT_CHARS + 5000)
        docs = [FakeDoc(uzun_icerik, "uzun_belge.pdf")]
        ctx = engine.format_context(docs)
        assert len(ctx) <= MAX_CONTEXT_CHARS + LABEL_TOLERANCE
        assert "kısaltıldı" in ctx

    def test_kaynak_metadata_yokken_varsayilan_deger(self):
        """metadata'da 'source' anahtarı yoksa 'Bilinmeyen Belge' kullanılmalı."""
        engine = self._get_engine()
        doc = FakeDoc("içerik")
        doc.metadata = {}  # source anahtarı yok
        ctx = engine.format_context([doc])
        assert "Bilinmeyen Belge" in ctx

    def test_pdf_uzantisi_kaynak_etiketinden_cikarilir(self):
        engine = self._get_engine()
        docs = [FakeDoc("metin", "/klasor/Burs Yönergesi.pdf")]
        ctx = engine.format_context(docs)
        assert ".pdf" not in ctx.split("\n")[0]


# ---------------------------------------------------------------------------
# rewrite_query testleri
# ---------------------------------------------------------------------------

class TestRewriteQuery:
    def _get_engine(self):
        engine = rag_engine.SelcukRAGEngine.__new__(rag_engine.SelcukRAGEngine)
        return engine

    def test_gecmis_yoksa_orijinal_soru_doner(self):
        """Sohbet geçmişi boşsa LLM çağrılmadan orijinal soru dönmeli."""
        engine = self._get_engine()
        soru = "Staj muafiyet şartları nelerdir?"
        assert engine.rewrite_query(soru, "") == soru
        assert engine.rewrite_query(soru, "   ") == soru

    def test_gecmis_none_ise_orijinal_soru_doner(self):
        engine = self._get_engine()
        soru = "Burs başvurusu nasıl yapılır?"
        assert engine.rewrite_query(soru, None) == soru


# ---------------------------------------------------------------------------
# suggest_followups testleri
# ---------------------------------------------------------------------------

class TestSuggestFollowups:
    def _get_engine(self):
        engine = rag_engine.SelcukRAGEngine.__new__(rag_engine.SelcukRAGEngine)
        return engine

    def test_hata_durumunda_bos_liste_doner(self):
        """LLM çağrısı başarısız olursa boş liste dönmeli."""
        engine = self._get_engine()
        # followup_prompt zinciri hata fırlatacak şekilde ayarla
        broken_chain = MagicMock()
        broken_chain.invoke.side_effect = Exception("API hatası")
        engine.followup_prompt = MagicMock()
        engine.llm = MagicMock()
        # __or__ zincirini simüle et
        engine.followup_prompt.__or__ = MagicMock(return_value=broken_chain)
        result = engine.suggest_followups("soru", "cevap")
        assert result == []

    def test_en_fazla_3_oneri_doner(self):
        """Sonuç listesi her zaman en fazla 3 eleman içermeli."""
        engine = self._get_engine()
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = "Soru 1\nSoru 2\nSoru 3\nSoru 4\nSoru 5"
        engine.followup_prompt = MagicMock()
        engine.llm = MagicMock()
        parser = MagicMock()
        engine.followup_prompt.__or__ = MagicMock(return_value=parser)
        parser.__or__ = MagicMock(return_value=mock_chain)
        result = engine.suggest_followups("soru", "cevap")
        assert len(result) <= 3


# ---------------------------------------------------------------------------
# MAX_CONTEXT_CHARS sabit testi
# ---------------------------------------------------------------------------

def test_max_context_chars_pozitif_tamsayi():
    assert isinstance(MAX_CONTEXT_CHARS, int)
    assert MAX_CONTEXT_CHARS > 0
