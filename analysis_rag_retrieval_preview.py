import argparse
import json
import os

from rag_engine import SelcukRAGEngine, normalize_user_question_for_retrieval


def _content_preview(text, limit=500):
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _json_safe(value):
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


def _doc_to_row(rank, doc):
    metadata = dict(getattr(doc, "metadata", {}) or {})
    source_info = SelcukRAGEngine.build_source_metadata(doc)
    return {
        "rank": rank,
        "source": metadata.get("source", ""),
        "title": metadata.get("title", ""),
        "label": source_info["label"],
        "article_no": metadata.get("article_no"),
        "article_title": metadata.get("article_title", ""),
        "page": source_info["page"],
        "flashrank_score": _json_safe(metadata.get("relevance_score")),
        "metadata_score": _json_safe(metadata.get("metadata_rerank_score") or metadata.get("metadata_score")),
        "metadata_strong_match": metadata.get("metadata_strong_match"),
        "explanation": _json_safe(metadata.get("metadata_rerank_explanation", [])),
        "content_preview": _content_preview(getattr(doc, "page_content", "")),
    }


def build_preview(question, top_k=10):
    os.environ["MULTI_QUERY_ENABLED"] = "false"
    os.environ.setdefault("METADATA_RERANK_ENABLED", "true")
    os.environ.setdefault("METADATA_RERANK_CANDIDATE_K", "40")

    normalized_question = normalize_user_question_for_retrieval(question)
    engine = SelcukRAGEngine(enable_llm=False)
    docs = engine.retrieve(normalized_question, top_k=top_k)
    return {
        "question": question,
        "normalized_question": normalized_question,
        "top_k": top_k,
        "results": [_doc_to_row(index, doc) for index, doc in enumerate(docs, start=1)],
    }


def main():
    parser = argparse.ArgumentParser(description="LLM cagrisi yapmadan RAG retrieval preview uretir.")
    parser.add_argument("--question", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    preview = build_preview(args.question, top_k=args.top_k)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(preview, f, ensure_ascii=False, indent=2)

    top = preview["results"][0] if preview["results"] else {}
    print(json.dumps({
        "out": args.out,
        "top_article_no": top.get("article_no"),
        "top_article_title": top.get("article_title"),
        "top_metadata_score": top.get("metadata_score"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
