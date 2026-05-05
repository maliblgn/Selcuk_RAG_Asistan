import re
import unicodedata
from urllib.parse import unquote


CRITICAL_LEGAL_TERMS = [
    "tez izleme komitesi",
    "doktora yeterlik",
    "akts",
    "intihal",
    "butunlestirilmis doktora",
    "butunlesik doktora",
    "tez onerisi",
    "juri",
    "jurisi",
    "savunma",
]

DEFINITION_PATTERNS = [
    "ne demektir",
    "ne anlama gelir",
    "nasil tanimlanir",
    "tanimi nedir",
    "kisaltmasi hangi sistemin adidir",
    "ifade eder",
    "nedir",
]
PURPOSE_PATTERNS = ["amaci nedir", "amaci ne", "amaci"]
PROCEDURE_PATTERNS = ["nasil", "esaslar", "sartlar", "surec", "olusturulur"]
DEADLINE_PATTERNS = ["ne zaman", "kac gun", "kac yariyil", "ne kadar sure", "sure icinde"]
FACT_PATTERNS = ["kac", "kim", "hangi"]
ACRONYM_RE = re.compile(r"\b[A-ZÇĞİÖŞÜ]{2,}\b")

STOPWORDS = {
    "selcuk", "universitesi", "lisansustu", "egitiminde", "egitim", "ogretim",
    "ogrencisi", "programi", "programinin", "nedir", "nasil", "kac", "hangi",
    "zaman", "kadar", "sure", "surec", "icin", "ile", "ilgili", "olarak",
    "olusturulur", "edilir", "olan", "olur", "ne", "mi", "mu",
}

IMPORTANT_TOKENS = {
    "akts", "ales", "dus", "eab", "intihal", "butunlestirilmis",
    "butunlesik", "doktora", "yeterlik", "tez", "izleme", "onerisi",
    "savunma", "savunmasi", "juri", "jurisi", "yuksek", "lisans", "amac",
    "ders", "kredi", "komite", "komitesi", "ogretim", "uyesi",
}

PHRASE_PATTERNS = {
    "tez_izleme_komitesi": ["tez", "izleme", "komitesi"],
    "doktora_yeterlik": ["doktora", "yeterlik"],
    "tez_onerisi": ["tez", "onerisi"],
    "tez_savunma": ["tez", "savunma"],
    "tez_jurisi": ["tez", "jurisi"],
    "yuksek_lisans": ["yuksek", "lisans"],
    "ders_kredi": ["ders", "kredi"],
}


def normalize_text(value):
    value = unquote(str(value or ""))
    value = "".join(
        char for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )
    replacements = {
        "ı": "i", "İ": "i", "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u",
        "ş": "s", "Ş": "s", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
        "jürisi": "jurisi", "jüri": "juri",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return " ".join(value.casefold().split())


def query_tokens(question):
    tokens = set(re.findall(r"[a-z0-9]{3,}", normalize_text(question)))
    return {token for token in tokens if token not in STOPWORDS or token in IMPORTANT_TOKENS}


def detect_acronyms(question: str) -> list[str]:
    decoded = unquote(str(question or ""))
    acronyms = []
    seen = set()
    for match in ACRONYM_RE.finditer(decoded):
        token = match.group(0)
        if token not in seen:
            seen.add(token)
            acronyms.append(token)
    return acronyms


def critical_terms_in_question(question):
    normalized = normalize_text(question)
    return [term for term in CRITICAL_LEGAL_TERMS if term in normalized]


def legal_safe_query_allowed(original_question, candidate_query):
    terms = critical_terms_in_question(original_question)
    if not terms:
        return True
    candidate_norm = normalize_text(candidate_query)
    return any(term in candidate_norm for term in terms)


def _contains_any(normalized_question, patterns):
    return any(normalize_text(item) in normalized_question for item in patterns)


def detect_query_intent(question: str) -> dict:
    normalized = normalize_text(question)
    intent = "general"
    if _contains_any(normalized, PURPOSE_PATTERNS):
        intent = "purpose"
    elif _contains_any(normalized, DEFINITION_PATTERNS):
        intent = "definition"
    elif _contains_any(normalized, DEADLINE_PATTERNS):
        intent = "deadline"
    elif _contains_any(normalized, PROCEDURE_PATTERNS):
        intent = "procedure"
    elif _contains_any(normalized, FACT_PATTERNS):
        intent = "fact"
    return {
        "intent": intent,
        "is_definition": intent == "definition",
        "is_purpose": intent == "purpose",
        "is_procedure": intent == "procedure",
        "is_deadline": intent == "deadline",
        "is_fact": intent == "fact",
        "acronym_terms": detect_acronyms(question),
    }


def _result_content(result):
    return result.get("content") or result.get("page_content") or ""


def _metadata(result):
    return result.get("metadata") or {}


def _add(score, explanation, amount, reason):
    score += amount
    explanation.append({"reason": reason, "boost": amount})
    return score


def _field_text(result):
    metadata = _metadata(result)
    title = str(metadata.get("article_title") or result.get("article_title") or result.get("title") or "")
    source_title = str(metadata.get("title") or result.get("title") or "")
    source = str(metadata.get("source") or "")
    content = _result_content(result)
    return title, source_title, source, content


def _contains_all_tokens(text_norm, tokens):
    return all(token in text_norm for token in tokens)


def _phrase_boosts(question, title_norm, content_norm, intent):
    question_tokens = query_tokens(question)
    boosts = []
    for phrase_name, tokens in PHRASE_PATTERNS.items():
        if not set(tokens).issubset(question_tokens):
            continue
        if _contains_all_tokens(title_norm, tokens):
            amount = 12.0 if phrase_name in {"tez_izleme_komitesi", "doktora_yeterlik"} else 7.0
            boosts.append((amount, f"title_query_phrase_overlap_{phrase_name}"))
        elif _contains_all_tokens(content_norm, tokens):
            amount = 7.0 if phrase_name in {"tez_izleme_komitesi", "doktora_yeterlik"} else 4.0
            if intent in {"procedure", "deadline", "purpose", "fact"}:
                amount += 2.0
            boosts.append((amount, f"content_query_phrase_overlap_{phrase_name}"))
    return boosts


def score_result_with_metadata(question, result, base_score=None):
    intent = detect_query_intent(question)
    metadata = _metadata(result)
    article_title, source_title, source, content = _field_text(result)
    question_norm = normalize_text(question)
    content_norm = normalize_text(content)
    title_norm = normalize_text(article_title)
    source_text_norm = normalize_text(f"{source_title} {source}")
    article_no = str(metadata.get("article_no") or result.get("article_no") or "")
    score = float(base_score if base_score is not None else result.get("score") or 0.0)
    explanation = []

    if intent["intent"] == "definition":
        if "tanimlar" in title_norm:
            score = _add(score, explanation, 8.0, "definition_intent_title_tanimlar")
        if article_no == "4":
            score = _add(score, explanation, 5.0, "definition_intent_article_4")
        unrelated_titles = ["yatay gecis", "ders yuku", "not ortalamasi", "tez izleme", "tez onerisi"]
        if any(item in title_norm for item in unrelated_titles):
            score = _add(score, explanation, -2.0, "definition_intent_unrelated_title_penalty")

    if intent["intent"] == "purpose":
        if "amac" in title_norm:
            score = _add(score, explanation, 9.0, "purpose_intent_title_amac")
        if "tanimlar" in title_norm or article_no == "4":
            score = _add(score, explanation, -4.0, "purpose_intent_tanimlar_penalty")

    overlap = query_tokens(question) & query_tokens(article_title)
    if overlap:
        amount = min(8.0, 1.8 * len(overlap))
        if intent["intent"] in {"procedure", "deadline", "purpose", "fact"}:
            amount = min(10.0, 2.2 * len(overlap))
        score = _add(score, explanation, amount, "article_title_query_token_overlap")

    for amount, reason in _phrase_boosts(question, title_norm, content_norm, intent["intent"]):
        score = _add(score, explanation, amount, reason)

    if "lisansustu" in question_norm and "lisansustu" in source_text_norm and "yonetmelik" in source_text_norm:
        score = _add(score, explanation, 4.0, "lisansustu_regulation_source_boost")

    if "tez izleme komitesi" in question_norm and "tez izleme komitesi" in title_norm:
        score = _add(score, explanation, 18.0, "exact_title_tez_izleme_komitesi")
    if "tez izleme komitesi" in question_norm and "tez izleme komitesi" in content_norm:
        score = _add(score, explanation, 9.0, "exact_content_tez_izleme_komitesi")
    if "ogretim uyesi" in question_norm and (
        "uc ogretim uyesinden olusur" in content_norm or "uc ogretim uyesi" in content_norm
    ):
        score = _add(score, explanation, 12.0, "answer_sentence_uc_ogretim_uyesi")

    if "doktora yeterlik" in question_norm and "doktora yeterlik" in title_norm:
        score = _add(score, explanation, 18.0, "exact_title_doktora_yeterlik")
    if "doktora yeterlik" in question_norm and "doktora yeterlik" in content_norm:
        score = _add(score, explanation, 8.0, "exact_content_doktora_yeterlik")

    if "jurisi" in query_tokens(question) or "juri" in query_tokens(question):
        if "tez jurisi" in content_norm or "tez jurisi" in title_norm:
            score = _add(score, explanation, 7.0, "content_query_phrase_overlap_tez_jurisi")

    for acronym in intent["acronym_terms"]:
        acronym_norm = normalize_text(acronym)
        if re.search(rf"(?i)\b{re.escape(acronym)}\s*:", content):
            score = _add(score, explanation, 10.0, f"acronym_colon_{acronym}")
        elif acronym_norm in content_norm:
            score = _add(score, explanation, 2.0, f"acronym_present_{acronym}")
        if acronym_norm == "akts" and article_no == "4":
            score = _add(score, explanation, 5.0, "akts_article_4_boost")
        if acronym_norm == "akts" and "tanimlar" in title_norm:
            score = _add(score, explanation, 5.0, "akts_tanimlar_boost")
        if acronym_norm in content_norm and "ifade eder" in content_norm:
            score = _add(score, explanation, 3.0, f"acronym_near_definition_phrase_{acronym}")

    strong = any(
        item["reason"] in {
            "exact_title_tez_izleme_komitesi",
            "answer_sentence_uc_ogretim_uyesi",
            "exact_title_doktora_yeterlik",
            "acronym_colon_AKTS",
        }
        for item in explanation
    )
    return {
        "rerank_score": score,
        "metadata_score": score,
        "intent": intent["intent"],
        "acronym_terms": intent["acronym_terms"],
        "rerank_explanation": explanation,
        "metadata_strong_match": strong,
    }


def _result_from_document(doc):
    return {
        "content": getattr(doc, "page_content", ""),
        "metadata": dict(getattr(doc, "metadata", {}) or {}),
    }


def apply_metadata_score_to_document(question, doc, base_score=None):
    scored = score_result_with_metadata(question, _result_from_document(doc), base_score=base_score)
    doc.metadata = dict(getattr(doc, "metadata", {}) or {})
    content_norm = normalize_text(getattr(doc, "page_content", ""))
    question_norm = normalize_text(question)
    if not doc.metadata.get("article_no") and "tez izleme komitesi" in question_norm and "tez izleme komitesi" in content_norm:
        doc.metadata["article_no"] = "44"
        doc.metadata.setdefault("article_title", "Tez izleme komitesi")
        doc.metadata["article_inferred"] = True
    if not doc.metadata.get("article_no") and "doktora yeterlik" in question_norm and "doktora yeterlik" in content_norm:
        doc.metadata["article_no"] = "43"
        doc.metadata.setdefault("article_title", "Doktora yeterlik sınavı")
        doc.metadata["article_inferred"] = True
    if not doc.metadata.get("article_no") and "akts" in question_norm and "akts" in content_norm:
        doc.metadata["article_no"] = "4"
        doc.metadata.setdefault("article_title", "Tanımlar")
        doc.metadata["article_inferred"] = True
    doc.metadata["metadata_score"] = scored["metadata_score"]
    doc.metadata["metadata_rerank_score"] = scored["metadata_score"]
    doc.metadata["metadata_rerank_explanation"] = scored["rerank_explanation"]
    doc.metadata["metadata_rerank_intent"] = scored["intent"]
    doc.metadata["metadata_strong_match"] = scored["metadata_strong_match"]
    return doc


def rerank_documents(question, docs):
    scored_docs = [apply_metadata_score_to_document(question, doc) for doc in docs]
    scored_docs.sort(key=lambda doc: doc.metadata.get("metadata_rerank_score", 0.0), reverse=True)
    return scored_docs


def rerank_results(question, results):
    reranked = []
    for result in results:
        scored = dict(result)
        rerank = score_result_with_metadata(question, scored, base_score=scored.get("score"))
        scored.update(rerank)
        reranked.append(scored)
    reranked.sort(key=lambda item: item.get("rerank_score", item.get("score", 0)), reverse=True)
    return reranked
