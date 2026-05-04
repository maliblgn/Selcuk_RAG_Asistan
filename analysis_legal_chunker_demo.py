import argparse
import json
import os
from datetime import datetime, timezone

from legal_chunker import article_chunks_to_documents, looks_like_legal_text, split_text_by_articles


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_JSON_OUT = os.path.join(BASE_DIR, "legal_chunker_demo.json")
DEFAULT_MARKDOWN_OUT = os.path.join(BASE_DIR, "docs", "FAZ2A_LEGAL_CHUNKER_RAPORU.md")

DEMO_TEXT = """SELÇUK ÜNİVERSİTESİ ÖRNEK YÖNETMELİK

MADDE 1 - Amaç
(1) Bu Yönetmeliğin amacı örnek madde bazlı chunklama davranışını göstermektir.

MADDE 2 – Tanımlar
(1) Bu Yönetmelikte geçen AKTS, öğrenci iş yükünü ifade eder.

MADDE 43-(1) Doktora yeterlik sınavları ile ilgili esaslar şunlardır:
a) Yeterlik sınavı yılda iki kez yapılabilir.

MADDE 44 - (1) Yürürlük
Bu Yönetmelik yayımı tarihinde yürürlüğe girer.
"""


def build_demo():
    chunks = split_text_by_articles(DEMO_TEXT, source_metadata={"source": "demo"})
    docs = article_chunks_to_documents(chunks, {"source": "demo", "doc_type": "demo_yonetmelik"})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "looks_like_legal_text": looks_like_legal_text(DEMO_TEXT),
        "article_count": len(chunks),
        "articles": [
            {
                "article_no": chunk.article_no,
                "article_title": chunk.article_title,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "content_preview": chunk.content[:180],
            }
            for chunk in chunks
        ],
        "document_metadata_preview": [doc.metadata for doc in docs],
    }


def write_markdown_report(path, demo, test_result="pytest tests/ -v"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    formats = [
        "MADDE 1 -",
        "MADDE 1 –",
        "MADDE 43-",
        "Madde 4 -",
        "madde 5 -",
        "MADDE 7",
        "MADDE 8-(1)",
        "MADDE 8 - (1)",
    ]
    lines = [
        "# Faz 2A Legal Chunker Raporu",
        "",
        f"Rapor tarihi: {demo.get('generated_at')}",
        "",
        "## 1. Amaç",
        "",
        "Türkçe mevzuat metinlerinde cevapların madde düzeyinde daha doğru bağlanabilmesi için MADDE bazlı chunklama yapan bağımsız ve test edilebilir bir modül eklendi. Bu fazda ChromaDB, ingestion pipeline, web fetch veya PDF okuma akışına entegrasyon yapılmadı.",
        "",
        "## 2. Desteklenen Madde Formatları",
        "",
    ]
    lines.extend(f"- `{item}`" for item in formats)
    lines.extend([
        "",
        "## 3. Modül Fonksiyonları",
        "",
        "- `ArticleChunk`: madde numarası, başlık, içerik, karakter aralığı ve yaklaşık sayfa aralığını taşır.",
        "- `find_article_starts(text)`: satır/paragraf başındaki MADDE başlangıçlarını bulur.",
        "- `split_text_by_articles(text, source_metadata=None)`: tek metni ArticleChunk listesine böler.",
        "- `split_pages_by_articles(page_texts, source_metadata=None)`: sayfa metinlerinden ArticleChunk listesi ve yaklaşık page_start/page_end üretir.",
        "- `article_chunks_to_documents(chunks, source_metadata=None)`: ArticleChunk listesini LangChain Document listesine çevirir.",
        "- `extract_article_title(article_text, article_no)`: ilk MADDE satırından başlık benzeri kısa metni çıkarır.",
        "- `looks_like_legal_text(text)`: en az iki farklı MADDE başlangıcı varsa mevzuat benzeri metin kabul eder.",
        "",
        "## 4. Test Sonuçları",
        "",
        f"`{test_result}` komutu çalıştırıldı; sonuç final yanıtta özetlenmiştir.",
        "",
        "## 5. Demo Çıktısı",
        "",
        f"Sabit örnek metinden {demo.get('article_count', 0)} madde çıkarıldı.",
        "",
        "| madde | başlık |",
        "|---|---|",
    ])
    for article in demo.get("articles", []):
        lines.append(f"| {article.get('article_no')} | {article.get('article_title')} |")
    lines.extend([
        "",
        "## 6. Sonraki Adım",
        "",
        "Bir sonraki fazda `legal_chunker.py` mevcut ingestion pipeline'a opsiyonel olarak entegre edilebilir. Entegrasyon öncesinde gerçek yönetmelik metinlerinden örnekler seçilip madde bölünmesi, sayfa aralığı ve metadata kalitesi ayrıca doğrulanmalıdır.",
    ])
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def parse_args():
    parser = argparse.ArgumentParser(description="legal_chunker sabit demo çıktısı üretir.")
    parser.add_argument("--json", action="store_true", help="Demo çıktısını JSON olarak yazdır")
    parser.add_argument("--out", default=DEFAULT_JSON_OUT, help="JSON çıktı yolu")
    parser.add_argument("--markdown-out", default=DEFAULT_MARKDOWN_OUT, help="Markdown rapor yolu")
    return parser.parse_args()


def main():
    args = parse_args()
    demo = build_demo()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(demo, f, ensure_ascii=False, indent=2)
    if args.markdown_out:
        write_markdown_report(args.markdown_out, demo)
    if args.json:
        print(json.dumps(demo, ensure_ascii=False, indent=2))
    else:
        print(f"Article count: {demo['article_count']}")


if __name__ == "__main__":
    main()
