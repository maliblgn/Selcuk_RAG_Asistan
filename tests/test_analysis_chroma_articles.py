from analysis_chroma_articles import aggregate_source, text_flags, unique_article_numbers


def test_article_regex_captures_standard_dash():
    numbers = unique_article_numbers("MADDE 43 - Doktora yeterlik sınavı düzenlenir.")
    assert numbers == ["43"]


def test_article_regex_captures_en_dash():
    numbers = unique_article_numbers("Başlık\nMADDE 1 – Amaç\nMADDE 2 – Kapsam")
    assert numbers == ["1", "2"]


def test_keyword_flags_detect_akts_tanimlar_yeterlik():
    flags = text_flags("Tanımlar bölümünde AKTS ve doktora yeterlik sınav şartları vardır.")
    assert flags["has_tanimlar"] is True
    assert flags["has_akts"] is True
    assert flags["has_yeterlik"] is True


def test_source_aggregation_deduplicates_article_numbers():
    source = "https://example.edu.tr/yonetmelik.pdf"
    items = [
        {
            "document": "MADDE 1 - Amaç\nMADDE 2 - Kapsam",
            "metadata": {
                "source": source,
                "title": "Test Yönetmelik",
                "source_type": "web_pdf",
                "doc_type": "yönetmelik",
            },
        },
        {
            "document": "MADDE 2 - Kapsam devamı\nMADDE 3 - Tanımlar",
            "metadata": {
                "source": source,
                "title": "Test Yönetmelik",
                "source_type": "web_pdf",
                "doc_type": "yönetmelik",
            },
        },
    ]

    aggregated = aggregate_source(source, items)

    assert aggregated["chunk_count"] == 2
    assert aggregated["has_madde"] is True
    assert aggregated["estimated_article_count"] == 3
    assert aggregated["first_article_numbers"] == ["1", "2", "3"]
    assert aggregated["has_tanimlar"] is True
