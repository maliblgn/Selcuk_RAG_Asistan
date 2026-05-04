import re
from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document


ARTICLE_START_RE = re.compile(
    r"(?im)(?:^|\n)[ \t]*(MADDE)\s+(\d+)\s*(?:[-\u2013]\s*)?(?=\(?\d*|\s|$)"
)
CONTEXT_PREFIX_RE = re.compile(
    r"(?im)^\s*(?:\[Bağlam:.*?\]|\[Madde\s+\d+.*?\]|\.\.\.\[bağlam kısaltıldı\])\s*$"
)
SECTION_HEADING_RE = re.compile(
    r"(?i)^\s*(?:BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|ALTINCI|YEDİNCİ|SEKİZİNCİ|DOKUZUNCU|ONUNCU|"
    r"BIRINCI|IKINCI|UCUNCU|DORDUNCU|BESINCI|ALTINCI|YEDINCI|SEKIZINCI|DOKUZUNCU|ONUNCU)\s+BÖLÜM\s*$"
)


@dataclass
class ArticleChunk:
    article_no: str
    article_title: str
    content: str
    start_char: int
    end_char: int
    page_start: int | None = None
    page_end: int | None = None
    title_source: str = ""
    duplicate_source_count: int = 1
    duplicate_warning: str = ""
    clean_context_prefix_applied: bool = False


def find_article_starts(text: str) -> list[re.Match]:
    """Metindeki satir/paragraf basi MADDE baslangiclarini bul."""
    return list(ARTICLE_START_RE.finditer(text or ""))


def clean_legal_text(text: str) -> tuple[str, bool]:
    """Onceki chunk/document prefix'lerinden gelen guvenli kalintilari temizle."""
    original = text or ""
    cleaned_lines = []
    removed_prefix = False
    for line in original.splitlines():
        if CONTEXT_PREFIX_RE.match(line):
            removed_prefix = True
            continue
        cleaned_lines.append(line.rstrip())
    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, removed_prefix


def normalize_article_title(title: str) -> str:
    title = re.sub(r"\s+", " ", (title or "").strip())
    title = title.strip(" :-\u2013.;")
    return title


def _meaningful_lines_before(text: str, start_char: int, limit: int = 4) -> list[str]:
    prefix = (text or "")[:start_char]
    lines = []
    for raw_line in reversed(prefix.splitlines()):
        line = normalize_article_title(raw_line)
        if not line:
            continue
        if CONTEXT_PREFIX_RE.match(line):
            continue
        lines.append(line)
        if len(lines) >= limit:
            break
    return list(reversed(lines))


def _looks_like_section_heading(line: str) -> bool:
    return bool(SECTION_HEADING_RE.match(line or ""))


def _looks_like_preceding_article_heading(line: str) -> bool:
    line = normalize_article_title(line)
    if not line:
        return False
    if _looks_like_section_heading(line):
        return False
    if len(line) > 90:
        return False
    if line.endswith((".", ";", ":")):
        return False
    if re.search(r"\b(MADDE|RG-|Resm[iî] Gazete)\b", line, re.IGNORECASE):
        return False
    if len(line.split()) > 5:
        return False
    return True


def extract_preceding_article_heading(text: str, start_char: int) -> str:
    """Madde baslangicindan onceki kisa mevzuat basligini bulmaya calis."""
    lines = _meaningful_lines_before(text, start_char, limit=4)
    for line in reversed(lines):
        if "." in line:
            tail = normalize_article_title(line.rsplit(".", 1)[-1])
            if _looks_like_preceding_article_heading(tail):
                return tail
            continue
        if _looks_like_preceding_article_heading(line):
            return line
    return ""


def extract_article_title(article_text: str, article_no: str) -> str:
    """Ilk MADDE satirindan kisa baslik/cumle girisini cikar."""
    if not article_text:
        return ""

    first_line = next((line.strip() for line in article_text.splitlines() if line.strip()), "")
    if not first_line:
        return ""

    pattern = re.compile(
        rf"(?i)^MADDE\s+{re.escape(str(article_no))}\s*(?:[-\u2013]\s*)?(?:\(\d+\)\s*)?(.*)$"
    )
    match = pattern.match(first_line)
    if not match:
        return ""

    candidate = normalize_article_title(match.group(1))
    if not candidate:
        return ""

    # Mevzuat maddelerinde ilk cumle genellikle baslik islevi gorur.
    sentence_match = re.match(r"(.+?)(?:[:.]|$)", candidate)
    if sentence_match:
        candidate = sentence_match.group(1)
    return normalize_article_title(candidate)


def split_text_by_articles(text: str, source_metadata: dict | None = None) -> list[ArticleChunk]:
    """Tek metni MADDE baslangiclarina gore ArticleChunk listesine bol."""
    del source_metadata  # Gelecekteki API uyumu icin tutulur.
    text, cleaned_prefix = clean_legal_text(text or "")
    starts = find_article_starts(text)
    chunks: list[ArticleChunk] = []

    for index, match in enumerate(starts):
        start = match.start()
        if start < len(text) and text[start] == "\n":
            start += 1
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        content = text[start:end].strip()
        article_no = match.group(2)
        if not content:
            continue
        preceding_heading = extract_preceding_article_heading(text, start)
        inline_title = extract_article_title(content, article_no)
        chunks.append(
            ArticleChunk(
                article_no=article_no,
                article_title=preceding_heading or inline_title,
                content=content,
                start_char=start,
                end_char=end,
                title_source="preceding_heading" if preceding_heading else "inline_fallback",
                clean_context_prefix_applied=cleaned_prefix,
            )
        )

    return chunks


def _content_score(chunk: ArticleChunk) -> tuple[int, int]:
    content = " ".join((chunk.content or "").split())
    return (len(content), len(set(content.casefold().split())))


def _is_mostly_contained(shorter: ArticleChunk, longer: ArticleChunk) -> bool:
    short_text = " ".join((shorter.content or "").casefold().split())
    long_text = " ".join((longer.content or "").casefold().split())
    if not short_text or not long_text:
        return False
    if short_text in long_text:
        return True
    short_words = set(short_text.split())
    long_words = set(long_text.split())
    if not short_words:
        return False
    return len(short_words & long_words) / len(short_words) >= 0.85


def _merge_duplicate_page_bounds(target: ArticleChunk, duplicates: list[ArticleChunk]) -> None:
    page_starts = [chunk.page_start for chunk in duplicates if chunk.page_start is not None]
    page_ends = [chunk.page_end for chunk in duplicates if chunk.page_end is not None]
    if page_starts:
        target.page_start = min(page_starts)
    if page_ends:
        target.page_end = max(page_ends)


def deduplicate_articles(chunks: list[ArticleChunk]) -> list[ArticleChunk]:
    """Ayni madde no tekrarlarinda daha uzun/temsilci chunk'i koru."""
    grouped: dict[str, list[ArticleChunk]] = {}
    order: list[str] = []
    for chunk in chunks:
        if chunk.article_no not in grouped:
            grouped[chunk.article_no] = []
            order.append(chunk.article_no)
        grouped[chunk.article_no].append(chunk)

    result: list[ArticleChunk] = []
    for article_no in order:
        duplicates = grouped[article_no]
        if len(duplicates) == 1:
            result.append(duplicates[0])
            continue

        sorted_duplicates = sorted(duplicates, key=_content_score, reverse=True)
        best = sorted_duplicates[0]
        rest = sorted_duplicates[1:]
        if all(_is_mostly_contained(other, best) for other in rest):
            best.duplicate_source_count = len(duplicates)
            best.duplicate_warning = "deduplicated_contained_articles"
            _merge_duplicate_page_bounds(best, duplicates)
            result.append(best)
            continue

        for duplicate in duplicates:
            duplicate.duplicate_source_count = len(duplicates)
            duplicate.duplicate_warning = "duplicate_articles_kept_distinct"
            result.append(duplicate)

    return result


def _page_offsets(page_texts: list[str]) -> tuple[str, list[tuple[int, int, int]]]:
    combined_parts = []
    offsets: list[tuple[int, int, int]] = []
    cursor = 0
    for page_index, page_text in enumerate(page_texts, start=1):
        if combined_parts:
            combined_parts.append("\n")
            cursor += 1
        page_text = page_text or ""
        start = cursor
        combined_parts.append(page_text)
        cursor += len(page_text)
        offsets.append((page_index, start, cursor))
    return "".join(combined_parts), offsets


def _page_for_offset(offsets: list[tuple[int, int, int]], char_offset: int) -> int | None:
    if not offsets:
        return None
    for page_index, start, end in offsets:
        if start <= char_offset < end:
            return page_index
    if char_offset >= offsets[-1][2]:
        return offsets[-1][0]
    return offsets[0][0]


def split_pages_by_articles(
    page_texts: list[str],
    source_metadata: dict | None = None,
    deduplicate: bool = True,
) -> list[ArticleChunk]:
    """PDF sayfa metinlerini birlestirip MADDE chunk'lari ve sayfa araliklari uret."""
    cleaned_pages = []
    any_cleaned = False
    for page_text in page_texts:
        cleaned_page, cleaned = clean_legal_text(page_text or "")
        cleaned_pages.append(cleaned_page)
        any_cleaned = any_cleaned or cleaned
    combined, offsets = _page_offsets(cleaned_pages)
    chunks = split_text_by_articles(combined, source_metadata=source_metadata)
    for chunk in chunks:
        chunk.page_start = _page_for_offset(offsets, chunk.start_char)
        chunk.page_end = _page_for_offset(offsets, max(chunk.end_char - 1, chunk.start_char))
        chunk.clean_context_prefix_applied = chunk.clean_context_prefix_applied or any_cleaned
    if deduplicate:
        chunks = deduplicate_articles(chunks)
    return chunks


def article_chunks_to_documents(
    chunks: list[ArticleChunk],
    source_metadata: dict[str, Any] | None = None,
) -> list[Document]:
    """ArticleChunk listesini LangChain Document listesine cevir."""
    source_metadata = dict(source_metadata or {})
    documents: list[Document] = []

    for chunk in chunks:
        metadata = dict(source_metadata)
        metadata.update({
            "article_no": chunk.article_no,
            "article_title": chunk.article_title,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "chunk_type": "article",
            "legal_chunker": True,
            "title_source": chunk.title_source,
            "duplicate_source_count": chunk.duplicate_source_count,
            "duplicate_warning": chunk.duplicate_warning,
            "clean_context_prefix_applied": chunk.clean_context_prefix_applied,
        })
        heading = f"Madde {chunk.article_no}"
        if chunk.article_title:
            heading += f" - {chunk.article_title}"
        page_content = f"[{heading}]\n\n{chunk.content}"
        documents.append(Document(page_content=page_content, metadata=metadata))

    return documents


def looks_like_legal_text(text: str) -> bool:
    numbers = {match.group(2) for match in find_article_starts(text or "")}
    return len(numbers) >= 2
