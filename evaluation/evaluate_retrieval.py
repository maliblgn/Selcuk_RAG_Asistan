import argparse
import json
import math
import os
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from urllib.parse import unquote

try:
    from evaluation.retrieval_rerank import detect_query_intent, rerank_results
except ImportError:
    from retrieval_rerank import detect_query_intent, rerank_results


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, "chroma_db", "chroma.sqlite3")
DEFAULT_QUESTIONS = os.path.join(BASE_DIR, "evaluation", "golden_questions.json")
DEFAULT_JSON_OUT = os.path.join(BASE_DIR, "retrieval_baseline_report.json")
DEFAULT_MARKDOWN_OUT = os.path.join(BASE_DIR, "docs", "FAZ3A_RETRIEVAL_BASELINE_RAPORU.md")
ARTICLE_RE = re.compile(r"(?im)(?:^|\n)\s*MADDE\s+(\d+)\s*[-–]?\s*")


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
    return value.casefold()


def tokenize(value):
    return re.findall(r"[a-z0-9]{2,}", normalize_text(value))


def metadata_value(row):
    _id, key, string_value, int_value, float_value, bool_value = row
    if string_value is not None:
        return string_value
    if int_value is not None:
        return int_value
    if float_value is not None:
        return float_value
    if bool_value is not None:
        return bool(bool_value)
    return None


def resolve_db_path(db_path=DEFAULT_DB):
    if os.path.isdir(db_path):
        return os.path.join(db_path, "chroma.sqlite3")
    return db_path


def read_chroma_documents(db_path=DEFAULT_DB):
    db_path = resolve_db_path(db_path)
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT id, key, string_value, int_value, float_value, bool_value
            FROM embedding_metadata
            """
        ).fetchall()
    finally:
        conn.close()

    metadata_by_id = defaultdict(dict)
    documents_by_id = {}
    for row in rows:
        item_id, key = row[0], row[1]
        value = metadata_value(row)
        if key == "chroma:document":
            documents_by_id[item_id] = value or ""
        else:
            metadata_by_id[item_id][key] = value

    docs = []
    for item_id in sorted(set(metadata_by_id) | set(documents_by_id)):
        metadata = metadata_by_id.get(item_id, {})
        content = documents_by_id.get(item_id, "")
        docs.append({
            "id": item_id,
            "content": content,
            "metadata": metadata,
            "source": metadata.get("source") or "",
            "title": metadata.get("title") or "",
            "page": metadata.get("page"),
        })
    return docs


def article_numbers_from_content(content):
    numbers = []
    seen = set()
    for match in ARTICLE_RE.finditer(content or ""):
        number = match.group(1)
        if number not in seen:
            seen.add(number)
            numbers.append(number)
    return numbers


def result_article_numbers(result):
    metadata = result.get("metadata") or {}
    article_no = metadata.get("article_no")
    if article_no:
        return [str(article_no)]
    return article_numbers_from_content(result.get("content") or "")


def expected_document_matches(result, expected_values):
    haystack = normalize_text(f"{result.get('source', '')} {result.get('title', '')}")
    return any(normalize_text(value) in haystack for value in (expected_values or []))


def expected_terms_match(results, expected_terms):
    haystack = normalize_text(" ".join(result.get("content", "") for result in results))
    return all(normalize_text(term) in haystack for term in (expected_terms or []))


def article_matches(result, expected_article_no):
    if not expected_article_no:
        return False
    return str(expected_article_no) in result_article_numbers(result)


def build_bm25_index(docs):
    doc_tokens = [tokenize(f"{doc.get('title', '')} {doc.get('content', '')}") for doc in docs]
    doc_freq = Counter()
    for tokens in doc_tokens:
        doc_freq.update(set(tokens))
    avg_len = sum(len(tokens) for tokens in doc_tokens) / max(len(doc_tokens), 1)
    return {
        "docs": docs,
        "doc_tokens": doc_tokens,
        "doc_freq": doc_freq,
        "avg_len": avg_len or 1,
        "doc_count": len(docs),
    }


def retrieve(index, query, top_k=5):
    query_terms = tokenize(query)
    if not query_terms:
        return []
    query_counts = Counter(query_terms)
    k1 = 1.5
    b = 0.75
    scored = []
    for doc, tokens in zip(index["docs"], index["doc_tokens"]):
        if not tokens:
            continue
        token_counts = Counter(tokens)
        score = 0.0
        for term, query_weight in query_counts.items():
            tf = token_counts.get(term, 0)
            if tf == 0:
                continue
            df = index["doc_freq"].get(term, 0)
            idf = math.log(1 + (index["doc_count"] - df + 0.5) / (df + 0.5))
            denom = tf + k1 * (1 - b + b * len(tokens) / index["avg_len"])
            score += query_weight * idf * ((tf * (k1 + 1)) / denom)
        if score > 0:
            ranked = dict(doc)
            ranked["score"] = score
            scored.append(ranked)
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def hit_at(results, predicate, k):
    return any(predicate(result) for result in results[:k])


def serialize_top_results(results):
    serialized = []
    for rank, result in enumerate(results, start=1):
        article_numbers = result_article_numbers(result)
        metadata = result.get("metadata") or {}
        serialized.append({
            "rank": rank,
            "source": result.get("source", ""),
            "title": result.get("title", ""),
            "page": result.get("page"),
            "article_no": metadata.get("article_no") or (article_numbers[0] if article_numbers else None),
            "article_title": metadata.get("article_title"),
            "score": result.get("score"),
            "rerank_score": result.get("rerank_score"),
            "rerank_explanation": result.get("rerank_explanation", []),
            "content_preview": " ".join((result.get("content") or "").split())[:500],
        })
    return serialized


def evaluate_question(index, question, top_k=5, candidate_k=None, metadata_rerank=False):
    candidate_k = candidate_k or top_k
    results = retrieve(index, question["question"], top_k=candidate_k)
    intent = detect_query_intent(question["question"])
    if metadata_rerank:
        results = rerank_results(question["question"], results)
    results = results[:top_k]
    expected_doc = question.get("expected_document_contains", [])
    expected_article_no = question.get("expected_article_no")
    expected_terms = question.get("expected_answer_terms", [])

    output = {
        "id": question["id"],
        "question": question["question"],
        "expected_article_no": expected_article_no,
        "intent": intent["intent"],
        "acronym_terms": intent["acronym_terms"],
        "top_results": serialize_top_results(results),
        "document_hit_at_1": hit_at(results, lambda result: expected_document_matches(result, expected_doc), 1),
        "document_hit_at_3": hit_at(results, lambda result: expected_document_matches(result, expected_doc), 3),
        "document_hit_at_5": hit_at(results, lambda result: expected_document_matches(result, expected_doc), min(5, top_k)),
        "article_hit_at_1": hit_at(results, lambda result: article_matches(result, expected_article_no), 1),
        "article_hit_at_3": hit_at(results, lambda result: article_matches(result, expected_article_no), 3),
        "article_hit_at_5": hit_at(results, lambda result: article_matches(result, expected_article_no), min(5, top_k)),
        "expected_terms_hit_at_5": expected_terms_match(results[: min(5, top_k)], expected_terms),
    }
    return output


def metric_ratio(results, key):
    if not results:
        return 0.0
    return sum(1 for result in results if result.get(key)) / len(results)


def compute_metrics(results):
    return {
        "document_hit_at_1": metric_ratio(results, "document_hit_at_1"),
        "document_hit_at_3": metric_ratio(results, "document_hit_at_3"),
        "document_hit_at_5": metric_ratio(results, "document_hit_at_5"),
        "article_hit_at_1": metric_ratio(results, "article_hit_at_1"),
        "article_hit_at_3": metric_ratio(results, "article_hit_at_3"),
        "article_hit_at_5": metric_ratio(results, "article_hit_at_5"),
        "expected_terms_hit_at_5": metric_ratio(results, "expected_terms_hit_at_5"),
    }


def evaluate(
    questions,
    docs,
    top_k=5,
    mode="retrieval_baseline_current_index",
    db_path=None,
    baseline=None,
    metadata_rerank=False,
    candidate_k=None,
):
    index = build_bm25_index(docs)
    candidate_k = candidate_k or top_k
    results = [
        evaluate_question(
            index,
            question,
            top_k=top_k,
            candidate_k=candidate_k,
            metadata_rerank=metadata_rerank,
        )
        for question in questions
    ]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "retrieval_method": "read_only_sqlite_bm25",
        "db_path": db_path,
        "question_count": len(questions),
        "top_k": top_k,
        "candidate_k": candidate_k,
        "metadata_rerank": metadata_rerank,
        "document_count": len(docs),
        "metrics": compute_metrics(results),
        "results": results,
    }
    if baseline:
        report["baseline"] = baseline
    return report


def markdown_escape(value):
    return str(value or "").replace("|", "\\|")


def write_markdown_report(report, path, command):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    metrics = report.get("metrics", {})
    baseline = report.get("baseline") or {}
    baseline_metrics = baseline.get("metrics", {})
    results = report.get("results", [])
    akts = next((item for item in results if item.get("id") == "lisansustu_akts_tanim"), None)
    baseline_akts = next(
        (item for item in baseline.get("results", []) if item.get("id") == "lisansustu_akts_tanim"),
        None,
    )
    basename = os.path.basename(path).upper()
    is_tuning = "3D" in basename
    is_rerank = "3C" in basename or is_tuning or report.get("metadata_rerank")
    is_legal_test = (
        "3B" in os.path.basename(path).upper()
        or report.get("mode") == "retrieval_legal_test_index"
        or is_rerank
    )
    if is_tuning:
        title = "Faz 3D Rerank Tuning Raporu"
    elif is_rerank:
        title = "Faz 3C Metadata-Aware Rerank Raporu"
    elif is_legal_test:
        title = "Faz 3B Legal Test Index Retrieval Raporu"
    else:
        title = "Faz 3A Retrieval Baseline Raporu"
    lines = [
        f"# {title}",
        "",
        f"Rapor tarihi: {report.get('generated_at')}",
        "",
        "## 1. Amaç",
        "",
        "Ana ChromaDB'yi bozmadan retrieval başarısını ölçmek. Bu rapor LLM/Groq çağrısı yapmadan, ChromaDB SQLite snapshot'ını okuyarak üretilmiştir.",
        "",
        "## 2. Yapılan Tuningler" if is_tuning else ("## 2. Rerank Kuralları" if is_rerank else ("## 2. Test Index Oluşturma" if is_legal_test else "## 2. Golden Question Set")),
        "",
    ]
    if is_rerank:
        lines.extend([
            "- Purpose intent: `amacı nedir` soruları Tanımlar yerine `Amaç` başlıklı maddeye yönelmeye çalışır.",
            "- Definition intent sınırlandırıldı; Tanımlar boost'u purpose/deadline/procedure sorularına uygulanmaz.",
            "- Definition intent: `nedir`, `ne demektir`, `nasıl tanımlanır`, `kısaltması hangi sistemin adıdır` gibi kalıplarla yakalanır.",
            "- Acronym detect: AKTS, ALES, DUS, EAB gibi büyük harfli tokenlar çıkarılır.",
            "- `Tanımlar` article_title, `article_no=4`, `{ACRONYM}:` pattern ve title/query token örtüşmesi boost alır.",
            "- Title/query phrase overlap ve content/query phrase overlap özellikle tez önerisi, tez jürisi, doktora yeterlik gibi ifadelerde boost üretir.",
            "- Stopword listesi genişletildi; alan terimleri korunur.",
            "",
            "## 3. Genel Metrikler",
            "",
        ])
    else:
        lines.extend([
        f"- Soru sayısı: {report.get('question_count', 0)}",
        f"- Değerlendirilen doküman/chunk sayısı: {report.get('document_count', 0)}",
        "- Kapsam: Madde 4, 24, 26, 29, 43, 44 ve 45 odaklı Lisansüstü Eğitim ve Öğretim Yönetmeliği soruları.",
        "",
        "## 3. Genel Metrikler",
        "",
        ])
    metric_keys = [
        "document_hit_at_1",
        "document_hit_at_3",
        "document_hit_at_5",
        "article_hit_at_1",
        "article_hit_at_3",
        "article_hit_at_5",
        "expected_terms_hit_at_5",
    ]
    if is_legal_test and baseline_metrics:
        lines.extend([
            "| metric | baseline_current_index | legal_test_index | delta |",
            "|---|---:|---:|---:|",
        ])
        for key in metric_keys:
            base_value = baseline_metrics.get(key, 0)
            legal_value = metrics.get(key, 0)
            lines.append(f"| {key} | {base_value:.3f} | {legal_value:.3f} | {legal_value - base_value:+.3f} |")
    else:
        lines.extend([
            "| metrik | değer |",
            "|---|---:|",
        ])
        for key in metric_keys:
            lines.append(f"| {key} | {metrics.get(key, 0):.3f} |")

    lines.extend([
        "",
        "## 4. AKTS Özel Karşılaştırma" if is_legal_test else "## 4. Soru Bazlı Sonuçlar",
        "",
    ])
    if is_legal_test:
        def _rank1_label(item):
            rank1 = item.get("top_results", [{}])[0] if item and item.get("top_results") else {}
            article = rank1.get("article_no") or ""
            title = rank1.get("article_title") or rank1.get("title") or rank1.get("source") or ""
            return f"{article} {title}".strip()

        lines.extend([
            "| alan | baseline | legal_test |",
            "|---|---|---|",
            f"| Madde 4 yakalandı mı | {baseline_akts.get('article_hit_at_5') if baseline_akts else ''} | {akts.get('article_hit_at_5') if akts else ''} |",
            f"| Avrupa Kredi Transfer Sistemi yakalandı mı | {baseline_akts.get('expected_terms_hit_at_5') if baseline_akts else ''} | {akts.get('expected_terms_hit_at_5') if akts else ''} |",
            f"| rank1 | {markdown_escape(_rank1_label(baseline_akts))} | {markdown_escape(_rank1_label(akts))} |",
            f"| detected intent | {baseline_akts.get('intent') if baseline_akts else ''} | {akts.get('intent') if akts else ''} |",
            f"| acronym_terms | {', '.join(baseline_akts.get('acronym_terms', [])) if baseline_akts else ''} | {', '.join(akts.get('acronym_terms', [])) if akts else ''} |",
            f"| rerank explanation |  | {markdown_escape((akts.get('top_results', [{}])[0] if akts and akts.get('top_results') else {}).get('rerank_explanation', []))} |",
            "",
            "## 5. Sorunlu Soruların Kontrolü" if is_tuning else ("## 5. Diğer Tanım Soruları" if is_rerank else "## 5. Soru Bazlı Sonuçlar"),
        ])
        if is_rerank:
            if is_tuning:
                lines.extend([
                    "| id | Faz 3C rank1 | Faz 3D rank1 | expected_article_no | article_hit@1 düzeldi mi |",
                    "|---|---|---|---:|---:|",
                ])
                for qid in [
                    "lisansustu_tez_onerisi_savunma_sure",
                    "lisansustu_tezli_yuksek_lisans_amac",
                    "lisansustu_yuksek_lisans_tez_savunma_jurisi",
                ]:
                    current = next((item for item in results if item.get("id") == qid), None)
                    previous = next((item for item in baseline.get("results", []) if item.get("id") == qid), None)
                    if not current:
                        continue
                    prev_rank = (previous.get("top_results", [{}])[0] if previous and previous.get("top_results") else {})
                    curr_rank = current.get("top_results", [{}])[0] if current.get("top_results") else {}
                    prev_label = f"{prev_rank.get('article_no')} {prev_rank.get('article_title') or prev_rank.get('title') or ''}"
                    curr_label = f"{curr_rank.get('article_no')} {curr_rank.get('article_title') or curr_rank.get('title') or ''}"
                    fixed = curr_rank.get("article_no") == current.get("expected_article_no")
                    lines.append(
                        f"| {qid} | {markdown_escape(prev_label)} | {markdown_escape(curr_label)} | "
                        f"{current.get('expected_article_no')} | {fixed} |"
                    )
            else:
                for definition_id in ["lisansustu_intihal_tanim", "lisansustu_butunlesik_doktora_tanim"]:
                    current = next((item for item in results if item.get("id") == definition_id), None)
                    previous = next((item for item in baseline.get("results", []) if item.get("id") == definition_id), None)
                    if current:
                        lines.append(
                            f"- {definition_id}: article_hit@5 {previous.get('article_hit_at_5') if previous else ''} -> "
                            f"{current.get('article_hit_at_5')}, expected_terms@5 "
                            f"{previous.get('expected_terms_hit_at_5') if previous else ''} -> "
                            f"{current.get('expected_terms_hit_at_5')}"
                        )
            lines.append("")
            lines.append("## 6. Soru Bazlı Sonuçlar")
    lines.extend([
        "",
        "| id | expected_article_no | article_hit@5 | expected_terms_hit@5 | rank1 article_no | rank1 title |",
        "|---|---:|---:|---:|---:|---|",
    ])
    for item in results:
        rank1 = item.get("top_results", [{}])[0] if item.get("top_results") else {}
        lines.append(
            f"| {markdown_escape(item.get('id'))} | {markdown_escape(item.get('expected_article_no'))} | "
            f"{item.get('article_hit_at_5')} | {item.get('expected_terms_hit_at_5')} | "
            f"{markdown_escape(rank1.get('article_no'))} | "
            f"{markdown_escape(rank1.get('article_title') or rank1.get('title') or rank1.get('source'))} |"
        )

    if not is_legal_test:
        lines.extend([
            "",
            "## 5. AKTS Özel Kontrol",
            "",
        ])
        if akts:
            rank1 = akts.get("top_results", [{}])[0] if akts.get("top_results") else {}
            lines.extend([
                f"- Top1 kaynak/title: {rank1.get('title') or rank1.get('source') or ''}",
                f"- Madde 4 yakalandı mı: {akts.get('article_hit_at_5')}",
                f"- `Avrupa Kredi Transfer Sistemi` top-k içinde var mı: {akts.get('expected_terms_hit_at_5')}",
            ])
        else:
            lines.append("- AKTS sorusu bulunamadı.")

    lines.extend([
        "",
        "## 6. Sonuç" if is_tuning else ("## 7. Sonraki Adım" if is_rerank else "## 6. Sonuç"),
        "",
        "Metadata-aware rerank başarılıysa sonraki adım bu scoring katmanını rag_engine.py içine opsiyonel ve kontrollü şekilde taşımaktır. Rule-based boostlar fazla agresif olabileceği için production entegrasyonunda feature flag ve ek regression seti kullanılmalıdır.",
        "",
        "## Çalıştırılan Komut",
        "",
        "```powershell",
        command,
        "```",
    ])
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def load_questions(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_args():
    parser = argparse.ArgumentParser(description="Golden sorularla mevcut ChromaDB retrieval baseline olcer.")
    parser.add_argument("--questions", default=DEFAULT_QUESTIONS, help="Golden questions JSON yolu")
    parser.add_argument("--db", default=DEFAULT_DB, help="Chroma sqlite3 yolu")
    parser.add_argument("--db-path", dest="db_path", default=None, help="Chroma persist directory veya sqlite3 yolu")
    parser.add_argument("--out", default=DEFAULT_JSON_OUT, help="JSON rapor yolu")
    parser.add_argument("--markdown-out", default=DEFAULT_MARKDOWN_OUT, help="Markdown rapor yolu")
    parser.add_argument("--top-k", type=int, default=5, help="Her soru icin top-k sonuc")
    parser.add_argument("--candidate-k", type=int, default=None, help="Rerank oncesi aday sayisi")
    parser.add_argument("--metadata-rerank", action="store_true", help="Metadata-aware rerank uygula")
    parser.add_argument("--baseline", default=None, help="Karsilastirma icin baseline JSON raporu")
    return parser.parse_args()


def main():
    args = parse_args()
    questions = load_questions(args.questions)
    db_path = args.db_path or args.db
    docs = read_chroma_documents(db_path)
    baseline = None
    if args.baseline:
        with open(args.baseline, "r", encoding="utf-8") as f:
            baseline = json.load(f)
    mode = "retrieval_legal_test_index" if args.db_path else "retrieval_baseline_current_index"
    if args.metadata_rerank:
        mode = "retrieval_metadata_rerank"
    report = evaluate(
        questions,
        docs,
        top_k=args.top_k,
        mode=mode,
        db_path=db_path,
        baseline=baseline,
        metadata_rerank=args.metadata_rerank,
        candidate_k=args.candidate_k,
    )
    command = (
        ".\\venv\\Scripts\\python.exe evaluation\\evaluate_retrieval.py "
        f"--questions {args.questions} "
        f"{'--db-path ' + args.db_path + ' ' if args.db_path else ''}"
        f"--out {args.out} --markdown-out {args.markdown_out} --top-k {args.top_k}"
        f"{' --candidate-k ' + str(args.candidate_k) if args.candidate_k else ''}"
        f"{' --metadata-rerank' if args.metadata_rerank else ''}"
        f"{' --baseline ' + args.baseline if args.baseline else ''}"
    )
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    if args.markdown_out:
        write_markdown_report(report, args.markdown_out, command)
    print(json.dumps({
        "question_count": report["question_count"],
        "top_k": report["top_k"],
        "metrics": report["metrics"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
