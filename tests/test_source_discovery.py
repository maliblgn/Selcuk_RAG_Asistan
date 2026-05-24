from source_discovery import (
    discover_sources,
    extract_source_discovery_topic,
    is_source_discovery_query,
)


def test_source_discovery_intent_positive_examples():
    assert is_source_discovery_query("stajla ilgili kaynaklar nelerdir")
    assert is_source_discovery_query("kütüphane hakkında hangi belgeler var")
    assert is_source_discovery_query("çift anadal ile ilgili yönerge var mı")


def test_source_discovery_intent_negative_examples():
    assert not is_source_discovery_query("AKTS nedir?")
    assert not is_source_discovery_query("Ders kredisi nasıl hesaplanır?")
    assert not is_source_discovery_query("Staj nedir?")


def test_extract_source_discovery_topic_general_patterns():
    assert extract_source_discovery_topic("teknoloji fakültesi ile alakalı bir kaynak var mı") == "teknoloji fakultesi"
    assert extract_source_discovery_topic("kütüphane hakkında hangi belgeler var") == "kutuphane"
    assert extract_source_discovery_topic("stajla ilgili kaynaklar nelerdir") == "staj"


def test_discover_sources_deduplicates_sources_with_sample_inventory():
    inventory = [
        {
            "source": "https://example.edu/staj.pdf",
            "title": "Teknoloji Fakultesi Staj Uygulama Yonergesi",
            "source_type": "web_pdf",
            "content": "Staj uygulama esaslari ve mesleki egitim sureci.",
        },
        {
            "source": "https://example.edu/staj.pdf",
            "title": "Teknoloji Fakultesi Staj Uygulama Yonergesi",
            "source_type": "web_pdf",
            "content": "Staj defteri ve staj komisyonu.",
        },
    ]
    result = discover_sources("stajla ilgili kaynaklar nelerdir", inventory_items=inventory)
    assert result["status"] == "ok"
    assert result["total_matches"] == 1
    assert len(result["sources"]) == 1
    assert result["sources"][0]["title"] == "Teknoloji Fakultesi Staj Uygulama Yonergesi"


def test_discover_sources_low_score_returns_no_match():
    inventory = [
        {
            "source": "https://example.edu/burs.pdf",
            "title": "Burs Yonergesi",
            "source_type": "web_pdf",
            "content": "Basvuru sartlari ve burs komisyonu.",
        }
    ]
    result = discover_sources("kutuphane hakkinda hangi belgeler var", inventory_items=inventory)
    assert result["status"] == "no_match"
    assert result["sources"] == []


def test_multi_token_topic_does_not_match_only_one_generic_token():
    inventory = [
        {
            "source": "https://example.edu/teknoloji-gelistirme.pdf",
            "title": "Teknoloji Gelistirme Yonergesi",
            "source_type": "web_pdf",
            "content": "Teknoloji gelistirme bolgesi uygulama esaslari.",
        }
    ]
    result = discover_sources("teknoloji fakultesi ile alakali bir kaynak var mi", inventory_items=inventory)
    assert result["status"] == "no_match"


def test_multi_token_topic_prefers_specific_terms_over_generic_faculty_terms():
    inventory = [
        {
            "source": "https://example.edu/other-staj.pdf",
            "title": "Baska Fakultesi Staj Yonergesi",
            "source_type": "web_pdf",
            "content": "Staj yonergesi ve uygulama esaslari.",
        },
        {
            "source": "https://example.edu/technology-staj.pdf",
            "title": "Teknoloji Fakultesi Staj Uygulama Yonergesi",
            "source_type": "web_pdf",
            "content": "Teknoloji Fakultesi ogrencileri icin staj uygulama esaslari.",
        },
    ]

    result = discover_sources("teknoloji fakultesi staj yonergesi var mi", inventory_items=inventory)

    assert result["status"] == "ok"
    assert result["sources"][0]["source"] == "https://example.edu/technology-staj.pdf"


def test_source_discovery_uses_general_patterns_not_single_question_patch():
    query = "yeni bir konu hakkinda hangi dokumanlar var"
    assert is_source_discovery_query(query)
    constants = " ".join(str(value) for value in is_source_discovery_query.__code__.co_consts)
    assert "teknoloji fakultesi" not in constants
    assert "stajla ilgili kaynaklar nelerdir" not in constants
