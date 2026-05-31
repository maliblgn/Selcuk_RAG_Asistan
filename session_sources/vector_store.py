"""In-memory retrieval for session-only chunks."""

from __future__ import annotations

import re
from collections import Counter

from langchain_core.documents import Document

from retrieval_normalization import normalize_ascii_lite

from .models import SessionChunk, SessionSource


STOPWORDS = {
    "nedir", "nasil", "hangi", "nelerdir", "var", "icin", "ile", "bir", "bu",
    "belgede", "pdf", "sayfada", "kaynakta", "mi", "ne", "nereye",
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

    def search(self, query: str, top_k: int = 4, min_score: float = 1.0) -> list[tuple[SessionChunk, float]]:
        query_tokens = Counter(tokenize(query))
        if not query_tokens:
            return []
        scored = []
        for chunk, tokens in zip(self.chunks, self._chunk_tokens):
            overlap = set(query_tokens) & set(tokens)
            score = sum(min(query_tokens[token], tokens[token]) for token in overlap)
            phrase_bonus = 0.0
            normalized_text = normalize_ascii_lite(chunk.text)
            normalized_query = normalize_ascii_lite(query)
            for token in overlap:
                if token in normalized_text:
                    phrase_bonus += 0.25
            if normalized_query and normalized_query in normalized_text:
                phrase_bonus += 3.0
            total = float(score) + phrase_bonus
            if total >= min_score:
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
            if self.source.source_type == "pdf":
                metadata["source"] = self.source.original_name_or_url
            elif self.source.source_type == "url":
                metadata["source"] = metadata.get("url") or self.source.original_name_or_url
            docs.append(Document(page_content=chunk.text, metadata=metadata))
        return docs


def build_session_vector_store(source: SessionSource, chunks: list[SessionChunk]) -> InMemorySessionVectorStore:
    return InMemorySessionVectorStore(source, chunks)

