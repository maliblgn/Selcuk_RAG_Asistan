from rag_engine import normalize_user_question_for_retrieval


def test_numbered_question_prefix_is_removed():
    question = "2. Selçuk Üniversitesi’nde tez izleme komitesi kaç öğretim üyesinden oluşur?"

    assert normalize_user_question_for_retrieval(question) == (
        "Selçuk Üniversitesi’nde tez izleme komitesi kaç öğretim üyesinden oluşur?"
    )


def test_markdown_bullet_and_quotes_are_removed():
    question = ' - "3) AKTS nedir?" '

    assert normalize_user_question_for_retrieval(question) == "AKTS nedir?"
