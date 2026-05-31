"""CI-safe smoke evaluation for session-only PDF/URL RAG."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from session_sources.chunker import chunk_text
from session_sources.models import SessionSource, utc_now
from session_sources.session_rag import answer_from_session_source
from session_sources.text_loader import build_text_session_source
from session_sources.vector_store import build_session_vector_store


FIXTURES = {
    "pdf": """
    İletişim
    E-posta: aday@example.com
    Telefon: +90 555 111 22 33

    Özet
    Aday, bilgisayar mühendisliği öğrencisidir. Yapay zeka, veri analizi ve web uygulamaları üzerinde çalışır.

    Eğitim
    Selçuk Üniversitesi Bilgisayar Mühendisliği. GPA: 3.42

    Projeler
    - Kaynak Analiz Sistemi
    - Akademik Takvim Uygulaması
    - Makine Öğrenmesi Portfolyosu

    Beceriler
    Python: ileri
    Veri analizi: orta

    Diller
    İngilizce: B2

    Başvuru Şartları
    a) Transkript teslim edilir.
    b) Başvuru formu doldurulur.
    """,
    "url": """
    Sayfa Başlığı
    Bu web sayfası akademik duyuru başlıklarını ve başvuru sürecini açıklar.

    Başlıklar
    - Duyuru takvimi
    - Başvuru belgeleri
    - İletişim
    """,
    "pasted_text": """
    Geçici Metin Notları
    Bu metin PDF yükleme çalışmadığında kullanıcı tarafından yapıştırılan içerik gibi değerlendirilir.

    Projeler
    - Kaynak Analiz Sistemi
    - Oturum Kaynak Cevaplama Denemesi

    Not
    Bu kaynak ana ChromaDB veritabanına eklenmez; yalnızca geçici oturum kapsamında kullanılır.
    """,
    "pdf_url": """
    PDF Link İçeriği
    Bu bağlantı üzerinden okunan PDF aday başvuru sürecini açıklar.

    Başvuru Şartları
    a) Transkript teslim edilir.
    b) Başvuru formu doldurulur.
    c) Belgeler ilgili birime iletilir.
    """,
}

SOURCE_TYPE_ALIASES = {
    "pdf_upload_fixture": "pdf",
    "pdf": "pdf",
    "url_fixture": "url",
    "url": "url",
    "pasted_text_fixture": "pasted_text",
    "pasted_text": "pasted_text",
    "pdf_url_fixture": "pdf_url",
    "pdf_url": "pdf_url",
}


def _canonical_source_type(source_type: str) -> str:
    try:
        return SOURCE_TYPE_ALIASES[source_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported session source fixture type: {source_type}") from exc


def _source(source_type: str) -> tuple[SessionSource, list]:
    source_type = _canonical_source_type(source_type)
    if source_type == "pasted_text":
        return build_text_session_source(FIXTURES[source_type], "Fixture Pasted Text")

    source = SessionSource(
        id=f"fixture_{source_type}",
        source_type=source_type,
        title=f"Fixture {source_type.upper()}",
        original_name_or_url=f"fixture.{source_type}",
        created_at=utc_now(),
        document_count=1,
        chunk_count=0,
        source_label=f"Fixture {source_type.upper()}",
    )
    chunks = chunk_text(source.id, FIXTURES[source_type], metadata={"source_type": source_type, "title": source.title, "page_number": 1}, min_chars=10)
    source = SessionSource(**{**source.to_dict(), "chunk_count": len(chunks)})
    return source, chunks


def load_questions(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Session source smoke questions must be a list.")
    return data


def build_report(questions: list[dict]) -> dict:
    stores = {}
    for source_type in sorted({_canonical_source_type(item["source_type"]) for item in questions}):
        source, chunks = _source(source_type)
        stores[source_type] = build_session_vector_store(source, chunks)

    failures = []
    for item in questions:
        source_type = _canonical_source_type(item["source_type"])
        result = answer_from_session_source(item["query"], stores[source_type])
        reasons = []
        if result.status != item["expected_status"]:
            reasons.append(f"expected_status={item['expected_status']}, actual_status={result.status}")
        answer_norm = result.answer.casefold()
        for term in item.get("expected_terms", []):
            if term.casefold() not in answer_norm:
                reasons.append(f"missing_term={term}")
        for term in item.get("forbidden_terms", []):
            if term.casefold() in answer_norm:
                reasons.append(f"forbidden_term={term}")
        if item.get("requires_citation") and not result.citations:
            reasons.append("missing_citation")
        if item.get("forbid_raw_dump") and len(result.answer) > item.get("max_answer_chars", 900):
            reasons.append("answer_too_long_possible_raw_dump")
        if reasons:
            failures.append({"id": item["id"], "query": item["query"], "failure_reasons": reasons, "answer": result.answer})

    total = len(questions)
    return {
        "total_questions": total,
        "passed": total - len(failures),
        "failed": len(failures),
        "critical_failures": failures,
        "status": "failed" if failures else "passed",
        "main_chroma_used": False,
    }


def write_markdown(report: dict, path: str | Path) -> None:
    lines = [
        "# Session Source Smoke Summary",
        "",
        f"- Status: {report['status']}",
        f"- Total questions: {report['total_questions']}",
        f"- Passed: {report['passed']}",
        f"- Failed: {report['failed']}",
        f"- Main Chroma used: {report['main_chroma_used']}",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate session-only PDF/URL RAG smoke questions.")
    parser.add_argument("--questions", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--markdown-out", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(load_questions(args.questions))
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(report, args.markdown_out)
    print(json.dumps({"status": report["status"], "passed": report["passed"], "failed": report["failed"]}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
