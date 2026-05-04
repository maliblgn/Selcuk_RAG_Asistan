import re
from urllib.parse import unquote


DEFINITION_PATTERNS = [
    "ne demektir",
    "ne anlama gelir",
    "nasıl tanımlanır",
    "tanımı nedir",
    "kısaltması hangi sistemin adıdır",
    "ifade eder",
    "nedir",
]
PURPOSE_PATTERNS = ["amacı nedir", "amacı ne", "amacı"]
PROCEDURE_PATTERNS = ["nasıl", "esaslar", "şartlar", "süreç", "oluşturulur"]
DEADLINE_PATTERNS = ["ne zaman", "kaç gün", "kaç yarıyıl", "ne kadar süre", "süre içinde"]
FACT_PATTERNS = ["kaç", "kim", "hangi"]
ACRONYM_RE = re.compile(r"\b[A-ZÇĞİÖŞÜ]{2,}\b")

STOPWORDS = {
    "selcuk",
    "universitesi",
    "lisansustu",
    "egitiminde",
    "egitim",
    "ogretim",
    "ogrencisi",
    "programi",
    "programinin",
    "nedir",
    "nasil",
    "kac",
    "hangi",
    "zaman",
    "kadar",
    "sure",
    "surec",
    "icin",
    "ile",
    "ilgili",
    "olarak",
    "olusturulur",
    "edilir",
    "olan",
    "olur",
    "ne",
    "mi",
    "mu",
}

IMPORTANT_TOKENS = {
    "akts",
    "ales",
    "dus",
    "eab",
    "intihal",
    "butunlestirilmis",
    "doktora",
    "yeterlik",
    "tez",
    "onerisi",
    "savunma",
    "savunmasi",
    "juri",
    "jurisi",
    "yuksek",
    "lisans",
    "amac",
    "ders",
    "kredi",
    "komite",
}

PHRASE_PATTERNS = {
    "tez_onerisi": ["tez", "onerisi"],
    "tez_savunma": ["tez", "savunma"],
    "tez_jurisi": ["tez", "jurisi"],
    "doktora_yeterlik": ["doktora", "yeterlik"],
    "tez_izleme_komitesi": ["tez", "izleme", "komitesi"],
    "yuksek_lisans": ["yuksek", "lisans"],
    "ders_kredi": ["ders", "kredi"],
}


def normalize_text(value):
    value = unquote(str(value or ""))
    replacements = {
        "İ": "i",
        "I": "i",
        "ı": "i",
        "Ğ": "g",
        "ğ": "g",
        "Ü": "u",
        "ü": "u",
        "Ş": "s",
        "ş": "s",
        "Ö": "o",
        "ö": "o",
        "Ç": "c",
        "ç": "c",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = value.casefold()
    value = value.replace("jürisi", "jurisi").replace("jüri", "juri")
    return value


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
    content = _result_content(result)
    return title, content


def _contains_all_tokens(text_norm, tokens):
    return all(token in text_norm for token in tokens)


def _phrase_boosts(question, title_norm, content_norm, intent):
    question_tokens = query_tokens(question)
    boosts = []
    for phrase_name, tokens in PHRASE_PATTERNS.items():
        if not set(tokens).issubset(question_tokens):
            continue
        if _contains_all_tokens(title_norm, tokens):
            amount = 7.0 if intent in {"procedure", "deadline", "purpose", "fact"} else 4.0
            boosts.append((amount, f"title_query_phrase_overlap_{phrase_name}"))
        elif _contains_all_tokens(content_norm, tokens):
            amount = 4.0 if intent in {"procedure", "deadline", "purpose", "fact"} else 2.0
            boosts.append((amount, f"content_query_phrase_overlap_{phrase_name}"))
    return boosts


def score_result_with_metadata(question, result, base_score=None):
    intent = detect_query_intent(question)
    metadata = _metadata(result)
    title, content = _field_text(result)
    content_norm = normalize_text(content)
    title_norm = normalize_text(title)
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

    overlap = query_tokens(question) & query_tokens(title)
    if overlap:
        amount = min(5.0, 1.2 * len(overlap))
        if intent["intent"] in {"procedure", "deadline", "purpose", "fact"}:
            amount = min(8.0, 1.8 * len(overlap))
        score = _add(score, explanation, amount, "article_title_query_token_overlap")

    for amount, reason in _phrase_boosts(question, title_norm, content_norm, intent["intent"]):
        score = _add(score, explanation, amount, reason)

    if "jurisi" in query_tokens(question) or "juri" in query_tokens(question):
        if "tez jurisi" in content_norm or "tez jurisi" in title_norm:
            score = _add(score, explanation, 7.0, "content_query_phrase_overlap_tez_jurisi")

    for acronym in intent["acronym_terms"]:
        acronym_norm = normalize_text(acronym)
        if re.search(rf"(?i)\b{re.escape(acronym)}\s*:", content):
            score = _add(score, explanation, 10.0, f"acronym_colon_{acronym}")
        elif acronym_norm in content_norm:
            score = _add(score, explanation, 2.0, f"acronym_present_{acronym}")
        if acronym_norm in content_norm and "ifade eder" in content_norm:
            score = _add(score, explanation, 3.0, f"acronym_near_definition_phrase_{acronym}")

    return {
        "rerank_score": score,
        "intent": intent["intent"],
        "acronym_terms": intent["acronym_terms"],
        "rerank_explanation": explanation,
    }


def rerank_results(question, results):
    reranked = []
    for result in results:
        scored = dict(result)
        rerank = score_result_with_metadata(question, scored, base_score=scored.get("score"))
        scored.update(rerank)
        reranked.append(scored)
    reranked.sort(key=lambda item: item.get("rerank_score", item.get("score", 0)), reverse=True)
    return reranked
