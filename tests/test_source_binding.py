from rag_engine import SelcukRAGEngine, strip_model_generated_sources


class FakeDoc:
    def __init__(self, content, metadata):
        self.page_content = content
        self.metadata = metadata


def test_strip_model_generated_sources_removes_single_line_source():
    answer = "AKTS, Avrupa Kredi Transfer Sistemidir [1].\nKaynak: [1] Yanlış Belge"

    assert strip_model_generated_sources(answer) == "AKTS, Avrupa Kredi Transfer Sistemidir [1]."


def test_source_panel_helper_uses_retrieved_doc_metadata():
    docs = [
        FakeDoc(
            "AKTS: Avrupa Kredi Transfer Sistemi.",
            {
                "source": "https://webadmin.selcuk.edu.tr/lisansustu.pdf",
                "title": "Lisansüstü Eğitim ve Öğretim Yönetmeliği",
                "article_no": "4",
                "article_title": "Tanımlar",
                "page_start": 3,
            },
        )
    ]

    context = SelcukRAGEngine.__new__(SelcukRAGEngine).format_context(docs)
    panel = [SelcukRAGEngine.build_source_metadata(doc) for doc in docs]

    assert "[1] Kaynak: Lisansüstü Eğitim ve Öğretim Yönetmeliği" in context
    assert panel[0]["label"] == "Lisansüstü Eğitim ve Öğretim Yönetmeliği"
    assert panel[0]["article_label"] == "Madde 4 - Tanımlar"
    assert panel[0]["page"] == "3"
