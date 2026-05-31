"""In-memory retrieval for session-only chunks."""

from __future__ import annotations

import re
from collections import Counter

from langchain_core.documents import Document

from retrieval_normalization import normalize_ascii_lite

from .extractors import detect_query_intent
from .models import SessionChunk, SessionSource


STOPWORDS = {
    "nedir", "nasil", "hangi", "nelerdir", "var", "icin", "ile", "bir", "bu",
    "belgede", "pdf", "sayfada", "kaynakta", "mi", "ne", "nereye", "kac",
}

INTENT_SECTION_BOOSTS = {
    "email": {"contact": 7.0},
    "phone": {"contact": 7.0},
    "url": {"contact": 5.0},
    "language": {"languages": 7.0, "skills": 2.0},
    "gpa": {"education": 7.0},
    "projects": {"projects": 7.0},
    "skills": {"skills": 7.0},
    "requirements": {"requirements": 7.0, "article": 2.0},
    "summary": {"summary": 4.0, "general": 1.0},
}

INTENT_FLAG_BOOSTS = {
    "email": ("contains_email", 8.0),
    "phone": ("contains_phone", 8.0),
    "language": ("contains_language_level", 8.0),
    "projects": ("contains_project_terms", 5.0),
    "requirements": ("contains_requirement_terms", 5.0),
    "date": ("contains_date", 5.0),
}


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]{3,}", normalize_ascii_lite(text))
    return [token for token in tokens if token not in STOPWORDS]


class InMemorySessionVectorStore:
    """Small lexical vector-like store scoped to one Streamlit session."""

    def __init__(self, source: SessionSource, chunks: list[SessionChunk]):
        self.source = source
        self.chunks = list(chunks)
        self._chunk_tokens = [Counter(tokenize(chunk.text)) for chunk in self.chunks]

    def search(self, query: str, top_k: int = 4, min_score: float | None = None) -> list[tuple[SessionChunk, float]]:
        query_tokens = Counter(tokenize(query))
        intent = detect_query_intent(query)
        if not query_tokens and not intent.wants_summary:
            return []
        threshold = 1.0 if min_score is None else min_score
        if intent.wants_summary:
            threshold = min(threshold, 0.3)
        if intent.name in INTENT_FLAG_BOOSTS or intent.name in INTENT_SECTION_BOOSTS:
            threshold = min(threshold, 0.5)
        scored = []
        for chunk, tokens in zip(self.chunks, self._chunk_tokens):
            metadata = chunk.metadata or {}
            overlap = set(query_tokens) & set(tokens)
            score = sum(min(query_tokens[token], tokens[token]) for token in overlap)
            phrase_bonus = 0.0
            normalized_text = normalize_ascii_lite(chunk.text)
            normalized_query = normalize_ascii_lite(query)
            section_title = normalize_ascii_lite(str(metadata.get("section_title", "")))
            for token in overlap:
                if token in normalized_text:
                    phrase_bonus += 0.25
                if section_title and token in section_title:
                    phrase_bonus += 1.5
            if normalized_query and normalized_query in normalized_text:
                phrase_bonus += 3.0
            section_bonus = INTENT_SECTION_BOOSTS.get(intent.name, {}).get(str(metadata.get("section_type", "")), 0.0)
            flag_bonus = 0.0
            flag = INTENT_FLAG_BOOSTS.get(intent.name)
            if flag and metadata.get(flag[0]):
                flag_bonus += flag[1]
            summary_bonus = 0.4 if intent.wants_summary and int(metadata.get("chunk_index") or 0) <= 1 else 0.0
            total = float(score) + phrase_bonus + section_bonus + flag_bonus + summary_bonus
            if total >= threshold:
                scored.append((chunk, total))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

    def to_documents(self, scored_chunks: list[tuple[SessionChunk, float]]) -> list[Document]:
        docs = []
        for chunk, score in scored_chunks:
            metadata = dict(chunk.metadata)
            metadata["session_source_id"] = chunk.source_id
            metadata["session_score"] = score
            metadata.setdefault("title", self.source.title)
            metadata.setdefault("source_type", self.source.source_type)
            metadata.setdefault("source_label", self.source.source_label)
            if self.source.source_type in {"pdf", "pdf_url"}:
                metadata["source"] = self.source.original_name_or_url
            elif self.source.source_type == "url":
                metadata["source"] = metadata.get("url") or self.source.original_name_or_url
            elif self.source.source_type == "pasted_text":
                metadata["source"] = self.source.original_name_or_url
            docs.append(Document(page_content=chunk.text, metadata=metadata))
        return docs


def build_session_vector_store(source: SessionSource, chunks: list[SessionChunk]) -> InMemorySessionVectorStore:
    return InMemorySessionVectorStore(source, chunks)
