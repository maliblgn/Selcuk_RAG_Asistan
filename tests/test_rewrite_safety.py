from rag_engine import is_unsafe_rewrite, multi_query_variation_allowed


def test_rewrite_rejects_fallback_answer_for_double_major_query():
    original = "Çift anadal şartları nelerdir?"
    rewritten = "Bu konuda bilgi dokümanlarda yer almıyor, bu nedenle cevap veremem."

    assert is_unsafe_rewrite(original, rewritten)


def test_rewrite_preserves_core_term_family():
    assert is_unsafe_rewrite("Çift anadal şartları nelerdir?", "Başvuru şartları nelerdir?")
    assert not is_unsafe_rewrite("Çift anadal şartları nelerdir?", "Çift ana dal başvuru şartları nelerdir?")


def test_rewrite_rejects_grade_average_semantic_drift():
    assert is_unsafe_rewrite("AGNO nedir?", "Not sistemi hakkında genel bilgi verir misin?")


def test_multi_query_rejects_unrelated_science_drift():
    assert not multi_query_variation_allowed("AGNO şartı nedir?", "AGNO molekül yapısı nedir?")
    assert multi_query_variation_allowed("AGNO şartı nedir?", "GANO not ortalaması şartı nedir?")
