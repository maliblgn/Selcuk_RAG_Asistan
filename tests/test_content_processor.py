import pytest
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document
from content_processor import ContentExtractor, SmartChunker, MetadataEnricher

# =====================================================================
# ContentExtractor Tests
# =====================================================================

@pytest.mark.skip(reason="Hangs in pytest environment")
def test_extract_main_content_trafilatura():
    html_content = "<html><body><header>Menu</header><main>This is the main content of the page.</main><footer>Footer content</footer></body></html>"
    # trafilatura should extract the main content and ignore header/footer.
    # It converts it to markdown.
    long_text = "This is the main content of the page. " * 10
    with patch("trafilatura.extract", return_value=long_text) as mock_extract:
        result = ContentExtractor.extract_main_content(html_content, url="https://example.com")
        assert result is not None
        assert "This is the main content of the page." in result
        mock_extract.assert_called_once()

@pytest.mark.skip(reason="Hangs in pytest environment")
def test_extract_fallback_to_bs4():
    # If trafilatura fails or returns empty, it falls back to BS4.
    html_content = "<html><body><div class='icerik'>Main article text here.</div></body></html>"
    with patch("trafilatura.extract", return_value=None):
        result = ContentExtractor.extract_main_content(html_content, url="https://example.com")
        assert result is not None
        assert "Main article text here." in result

def test_is_junk_short_content():
    assert ContentExtractor.is_junk("Too short") is True

def test_is_junk_valid_content():
    valid_text = "This is a sufficiently long text that should pass the junk filter. " * 10
    assert ContentExtractor.is_junk(valid_text) is False

def test_clean_markdown_removes_noise():
    dirty_markdown = "Link 1 | Link 2 | Link 3\n\n\n\nValid text\n\n\nMore valid text"
    cleaned = ContentExtractor.clean_markdown(dirty_markdown)
    assert "Link 1 | Link 2" not in cleaned
    assert "Valid text\n\nMore valid text" in cleaned

# =====================================================================
# MetadataEnricher Tests
# =====================================================================

def test_detect_unit_from_subdomain():
    assert MetadataEnricher.detect_unit("https://muhendislik.selcuk.edu.tr/page") == "Mühendislik Fakültesi"

def test_detect_unit_from_path():
    assert MetadataEnricher.detect_unit("https://selcuk.edu.tr/sks/duyuru") == "Sağlık Kültür ve Spor Daire Başkanlığı"

def test_detect_doc_type_yonerge():
    assert MetadataEnricher.detect_doc_type("https://selcuk.edu.tr/yonerge") == "yönerge"

def test_detect_doc_type_haber():
    assert MetadataEnricher.detect_doc_type("https://selcuk.edu.tr/haberler/123") == "haber"

def test_generate_summary():
    summary = MetadataEnricher.generate_summary(
        title="Duyuru Başlığı",
        unit="Mühendislik Fakültesi",
        doc_type="duyuru",
        header_1="Staj Bilgileri"
    )
    assert "Bağlam:" in summary
    assert "Mühendislik Fakültesi" in summary
    assert "Duyuru Başlığı" in summary
    assert "Staj Bilgileri" in summary
    assert "Duyuru" in summary

def test_enrich_document_full():
    doc = Document(page_content="Staj yönergesi maddeleri...", metadata={"source": "https://muhendislik.selcuk.edu.tr/staj-yonergesi", "title": "Staj İşlemleri"})
    enriched = MetadataEnricher.enrich_document(doc)
    
    assert enriched.metadata["unit"] == "Mühendislik Fakültesi"
    assert enriched.metadata["doc_type"] == "yönerge"
    assert "summary" in enriched.metadata
    assert "Bağlam: Mühendislik Fakültesi" in enriched.page_content
    assert "Staj yönergesi maddeleri..." in enriched.page_content

# =====================================================================
# SmartChunker Tests
# =====================================================================

def test_smart_chunker_header_split():
    doc = Document(
        page_content="# Baslik 1\nIcerik 1\n## Alt Baslik 1\nIcerik 2\n# Baslik 2\nIcerik 3",
        metadata={"source": "test"}
    )
    chunker = SmartChunker()
    # Mock embeddings to prevent downloading models during simple tests
    chunker._embeddings = MagicMock()
    
    chunks = chunker._split_by_headers(doc)
    assert len(chunks) == 3
    assert chunks[0].metadata.get("header_1") == "Baslik 1"
    assert chunks[1].metadata.get("header_2") == "Alt Baslik 1"
    assert chunks[2].metadata.get("header_1") == "Baslik 2"

def test_smart_chunker_preserves_metadata():
    doc = Document(
        page_content="# Baslik\nIcerik... " * 10,
        metadata={"source": "test_url", "title": "Test Title"}
    )
    chunker = SmartChunker()
    chunker._embeddings = MagicMock()
    
    chunks = chunker.chunk_documents([doc])
    assert len(chunks) > 0
    assert chunks[0].metadata["source"] == "test_url"
    assert chunks[0].metadata["title"] == "Test Title"
    assert chunks[0].metadata.get("header_1") == "Baslik"
