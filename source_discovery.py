"""Source discovery helpers for indexed source-listing questions."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import unquote

from langchain_chroma import Chroma
from langchain_core.documents import Document

from retrieval_normalization import (
    document_alias_score,
    expand_query_alias_text,
    load_retrieval_aliases,
    normalize_ascii_lite,
    title_similarity_score,
    tokenize_for_match,
)


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "chroma_db"
SOURCE_DISCOVERY_MIN_SCORE = 2.5

_SOURCE_TERMS = (
    "kaynak",
    "kaynaklar",
    "belge",
    "belgeler",
    "dokuman",
    "dokumanlar",
    "doküman",
    "dokümanlar",
    "yonerge",
    "yonergeler",
    "yönerge",
    "yönergeler",
    "pdf",
)
_LIST_TERMS = (
    "hangi",
    "neler",
    "nelerdir",
    "liste",
    "listesi",
    "goster",
    "göster",
    "var mi",
    "var mı",
    "mevcut mu",
    "bulunuyor mu",
)
_RELATION_TERMS = (
    "ile ilgili",
    "ilgili",
    "alakali",
    "alakalı",
    "hakkinda",
    "hakkında",
    "konusunda",
)
_TOPIC_STOPWORDS = {
    "hangi",
    "kaynak",
    "kaynaklar",
    "belge",
    "belgeler",
    "dokuman",
    "dokumanlar",
    "yonerge",
    "yonergeler",
    "pdf",
    "var",
    "mi",
    "neler",
    "nelerdir",
    "liste",
    "listesi",
    "goster",
    "mevcut",
    "bulunuyor",
    "ilgili",
    "alakali",
    "hakkinda",
    "konusunda",
    "ile",
    "bir",
    "bu",
    "bununla",
}


def is_source_discovery_query(query: str) -> bool:
    """Return True when the user is clearly asking for indexed source lists."""

    normalized = normalize_ascii_lite(query)
    if not normalized:
        return False

    has_source_term = any(term in normalized for term in [normalize_ascii_lite(t) for t in _SOURCE_TERMS])
    has_list_intent = any(term in normalized for term in [normalize_ascii_lite(t) for t in _LIST_TERMS])
    has_relation = any(term in normalized for term in [normalize_ascii_lite(t) for t in _RELATION_TERMS])

    if has_source_term and has_list_intent:
        return True
    if has_source_term and has_relation and any(term in normalized for term in ("var mi", "neler", "hangi")):
        return True
    return False


def extract_source_discovery_topic(query: str) -> str:
    """Extract the topic part from a source discovery question."""

    normalized = normalize_ascii_lite(query)
    if not normalized:
        return ""

    topic = normalized
    topic = re.sub(r"\b(bununla|bunun|bu)\b", " ", topic)
    topic = re.sub(r"\b(ile\s+ilgili|ile\s+alakali|hakkinda|konusunda)\b.*", " ", topic)
    topic = re.sub(r"\b(hangi|neler|nelerdir|liste|listesi|goster)\b.*", " ", topic)
    topic = re.sub(r"\b(kaynaklar?|belgeler?|dokumanlar?|yonergeler?|pdf)\b", " ", topic)
    topic = re.sub(r"\b(var\s+mi|mevcut\s+mu|bulunuyor\s+mu)\b", " ", topic)

    tokens = [_strip_topic_suffix(token) for token in topic.split()]
    tokens = [token for token in tokens if token not in _TOPIC_STOPWORDS and len(token) >= 2]
    if tokens:
        return " ".join(tokens)

    fallback_tokens = [_strip_topic_suffix(token) for token in normalized.split()]
    fallback_tokens = [
        token for token in fallback_tokens
        if token not in _TOPIC_STOPWORDS and len(token) >= 3
    ]
    return " ".join(fallback_tokens)


def _strip_topic_suffix(token: str) -> str:
    """Remove simple Turkish connective suffixes used before ``ilgili/alakali``."""

    if len(token) > 4 and token.endswith(("la", "le")):
        return token[:-2]
    return token


def _source_display_name(source: str, title: str = "") -> str:
    title = unquote(str(title or "").strip())
    if title:
        return title[:-4] if title.lower().endswith(".pdf") else title
    source = unquote(str(source or "").strip())
    if not source:
        return "Bilinmeyen Belge"
    filename = source.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    if filename.lower().endswith(".pdf"):
        filename = filename[:-4]
    return filename or source


def _iter_inventory_items(db=None, inventory_items: list[dict] | None = None) -> list[dict]:
    if inventory_items is not None:
        return inventory_items

    if db is None:
        db = Chroma(persist_directory=str(DEFAULT_DB_PATH))

    try:
        data = db.get(include=["documents", "metadatas"])
    except TypeError:
        data = db.get()

    documents = data.get("documents") or []
    metadatas = data.get("metadatas") or []
    items: list[dict] = []
    for index, metadata in enumerate(metadatas):
        metadata = metadata or {}
        items.append({
            "source": metadata.get("source") or "",
            "title": metadata.get("title") or "",
            "source_type": metadata.get("source_type") or "unknown",
            "article_title": metadata.get("article_title") or "",
            "article_no": metadata.get("article_no") or "",
            "content": documents[index] if index < len(documents) else "",
        })
    return items


def _score_inventory_item(topic: str, query: str, item: dict, aliases: dict) -> tuple[float, list[str], str]:
    topic_text = expand_query_alias_text(topic or query, aliases)
    topic_tokens = tokenize_for_match(topic_text)
    if not topic_tokens:
        return 0.0, [], ""

    title = item.get("title") or _source_display_name(item.get("source", ""))
    source = item.get("source") or ""
    article_title = item.get("article_title") or ""
    content = item.get("content") or ""

    title_text = " ".join([title, source, article_title])
    content_text = content[:2500]
    title_tokens = tokenize_for_match(title_text)
    content_tokens = tokenize_for_match(content_text)
    matched_title = topic_tokens & title_tokens
    matched_content = topic_tokens & content_tokens
    matched_all = matched_title | matched_content
    topic_phrase = normalize_ascii_lite(topic_text)
    title_norm = normalize_ascii_lite(title_text)
    content_norm = normalize_ascii_lite(content_text)

    if len(topic_tokens) >= 2 and len(matched_all) < 2:
        if topic_phrase not in title_norm and topic_phrase not in content_norm:
            return 0.0, sorted(matched_all), ""

    score = 0.0
    if matched_title:
        score += 2.0 + (len(matched_title) / max(len(topic_tokens), 1)) * 4.0
    if matched_content:
        score += min(2.0, len(matched_content) * 0.5)
    score += title_similarity_score(topic_text, title_text) * 0.8
    score += document_alias_score(topic_text, title_text, aliases)

    matched = sorted((matched_title | matched_content))
    if matched_title:
        reason = "baslik/metadata alaninda eslesen terimler var"
    elif matched_content:
        reason = "icerik parcasi icinde eslesen terimler var"
    else:
        reason = ""
    if len(topic_tokens) >= 2 and len(matched_all) < 2 and score < 5.0:
        score = min(score, min(SOURCE_DISCOVERY_MIN_SCORE - 0.1, 2.0))
    return min(score, 10.0), matched, reason


def discover_sources(
    query: str,
    max_sources: int = 8,
    db=None,
    inventory_items: list[dict] | None = None,
    min_score: float = SOURCE_DISCOVERY_MIN_SCORE,
) -> dict:
    """Discover indexed sources related to a source-listing query."""

    topic = extract_source_discovery_topic(query)
    aliases = load_retrieval_aliases()
    best_by_source: dict[str, dict] = {}

    for item in _iter_inventory_items(db=db, inventory_items=inventory_items):
        source = item.get("source") or item.get("url") or item.get("title") or ""
        if not source:
            continue
        score, matched_terms, reason = _score_inventory_item(topic, query, item, aliases)
        if score < min_score:
            continue
        existing = best_by_source.get(source)
        if existing and existing["score"] >= score:
            continue
        title = _source_display_name(source, item.get("title"))
        best_by_source[source] = {
            "title": title,
            "source_type": item.get("source_type") or "unknown",
            "url": source if str(source).startswith(("http://", "https://")) else "",
            "source": source,
            "matched_terms": matched_terms[:8],
            "reason": reason or "kaynak metadata/icerik eslesmesi",
            "score": round(score, 3),
            "snippet": str(item.get("content") or "")[:240].replace("\n", " ").strip(),
        }

    sources = sorted(best_by_source.values(), key=lambda item: (-item["score"], item["title"].casefold()))
    visible = sources[:max_sources]
    for rank, item in enumerate(visible, start=1):
        item["rank"] = rank

    return {
        "mode": "source_discovery",
        "query": query,
        "topic": topic,
        "total_matches": len(sources),
        "sources": visible,
        "status": "ok" if visible else "no_match",
    }


def source_discovery_sources_to_documents(sources: list[dict]) -> list[Document]:
    """Convert discovery results to lightweight documents for the source panel."""

    docs: list[Document] = []
    for item in sources:
        docs.append(Document(
            page_content=item.get("snippet") or item.get("reason") or "Kaynak eslesmesi",
            metadata={
                "source": item.get("source") or item.get("url") or "",
                "title": item.get("title") or "",
                "source_type": item.get("source_type") or "unknown",
            },
        ))
    return docs


def build_source_discovery_answer(result: dict) -> str:
    """Build a user-facing source discovery answer."""

    topic = result.get("topic") or result.get("query") or "bu konu"
    if result.get("status") != "ok" or not result.get("sources"):
        return (
            f"Indekslenmis kaynaklar icinde '{topic}' konusuyla iliskili guvenilir bir kaynak eslesmesi bulamadim. "
            "Bu sonuc mevcut ChromaDB snapshot uzerinden uretilmistir."
        )

    lines = [
        f"Indekslenmis kaynaklar icinde '{topic}' konusuyla iliskili kaynaklar sunlar:",
        "",
    ]
    for item in result.get("sources", []):
        rank = item.get("rank")
        title = item.get("title") or "Bilinmeyen Belge"
        lines.append(f"[{rank}] {title}")
        if item.get("reason"):
            lines.append(f"- Eslesme nedeni: {item['reason']}.")
        if item.get("matched_terms"):
            lines.append(f"- Eslesen terimler: {', '.join(item['matched_terms'][:6])}.")
        lines.append("")

    total = result.get("total_matches", len(result.get("sources", [])))
    if total > len(result.get("sources", [])):
        lines.append(f"Ilk {len(result.get('sources', []))} kaynak gosterildi; toplam {total} eslesme var.")
        lines.append("")
    lines.append("Bu liste, mevcut indekslenmis kaynaklar uzerinden olusturulmustur.")
    return "\n".join(lines).strip()
