"""Generate deterministic coverage QA prompts from the current Chroma inventory."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from audit_chroma_coverage import TOPIC_TERMS, build_coverage_report
except ImportError:  # Imported as tools.generate_chroma_coverage_questions in tests.
    from tools.audit_chroma_coverage import TOPIC_TERMS, build_coverage_report


QUESTION_TEMPLATES = {
    "akts": ["AKTS nedir?", "AKTS hangi sistemin kısaltmasıdır?"],
    "ales": ["ALES nedir?", "Lisansüstü başvurularda ALES neyi ifade eder?"],
    "agno_gano": ["Ön lisans ve lisans AGNO şartı nedir?", "GANO ile AGNO aynı şey mi?"],
    "cift_anadal": ["Çift anadal şartları nelerdir?", "Çift anadal ile ilgili yönerge var mı?"],
    "lisansustu": ["Lisansüstü başvuru şartları nelerdir?", "Doktora yeterlik sınavı nasıl yapılır?"],
    "staj": ["Staj yönergesi var mı?", "Stajla ilgili kaynaklar nelerdir?"],
    "teknoloji_fakultesi": ["Teknoloji Fakültesi staj kaynakları nelerdir?", "Teknoloji Fakültesi ile alakalı kaynak var mı?"],
    "yemekhane": ["Bugün yemekte ne var?", "Yemekhane ile ilgili kaynaklar nelerdir?"],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def generate_questions(chroma_dir: str = "chroma_db") -> dict:
    coverage = build_coverage_report(chroma_dir)
    questions = []
    for topic in TOPIC_TERMS:
        covered = coverage.get("topic_coverage", {}).get(topic, {}).get("covered", False)
        for index, query in enumerate(QUESTION_TEMPLATES.get(topic, []), start=1):
            questions.append({
                "id": f"generated_{topic}_{index}",
                "query": query,
                "topic": topic,
                "covered_in_inventory": covered,
                "expected_mode": "dynamic_dining_menu" if query.lower().startswith("bugün") else "rag_or_source_discovery",
            })
    return {
        "generated_at": _now(),
        "chroma_dir": chroma_dir,
        "generated_question_count": len(questions),
        "questions": questions,
    }


def write_markdown(report: dict, path: str | Path) -> None:
    lines = [
        "# Generated Chroma Coverage Questions",
        "",
        f"- Chroma dir: {report['chroma_dir']}",
        f"- Generated questions: {report['generated_question_count']}",
        "",
    ]
    for item in report["questions"]:
        lines.append(f"- `{item['id']}` ({item['topic']}): {item['query']}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate local vector coverage questions.")
    parser.add_argument("--chroma-dir", default="chroma_db")
    parser.add_argument("--out", required=True)
    parser.add_argument("--markdown-out", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = generate_questions(args.chroma_dir)
    Path(args.out).write_text(json.dumps(report["questions"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(report, args.markdown_out)
    print(json.dumps({
        "generated_question_count": report["generated_question_count"],
        "chroma_dir": report["chroma_dir"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
