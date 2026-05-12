from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .chunk_framework_check import (
    ARTICLE_RE,
    CHAPTER_RE,
    CLAUSE_RE,
    PART_RE,
    POINT_RE,
    SECTION_RE,
    classify_file,
)
from .crawl_laws import clean_legal_text


INNER_ARTICLE_RE = re.compile(r'^\s*["“]?Điều\s+\d+[A-Za-z]?\.')
INNER_TARGET_RE = re.compile(r'(Điều\s+\d+[A-Za-z]?)')
TARGET_ARTICLE_RE = re.compile(
    r'(?:sửa đổi, bổ sung|bổ sung|thay thế|bãi bỏ)\s+(Điều\s+\d+[A-Za-z]?)',
    re.IGNORECASE,
)
INLINE_CLAUSE_RE = re.compile(r'(?<=[.;:])\s+(?=\d+[.)]\s+)')
INLINE_POINT_RE = re.compile(r'(?<=[;:])\s+(?=[a-zđ][.)]\s+)', re.IGNORECASE)


@dataclass
class Chunk:
    chunk_id: str
    source_file: str
    mode: str
    article_number: str | None
    article_title: str | None
    clause_number: str | None
    point_number: str | None
    text: str
    text_length: int
    document_title: str | None
    part: str | None
    chapter: str | None
    section: str | None
    subsection: str | None
    target_law: str | None
    target_article: str | None
    quoted_inner_articles: list[str]


def iter_text_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return

    for path in sorted(root.glob("*.txt")):
        yield path


def slug_to_title(path: Path) -> str:
    stem = path.stem
    parts = stem.split("_", 1)
    return parts[1].replace("-", " ") if len(parts) == 2 else stem.replace("-", " ")


def parse_article_heading(line: str) -> tuple[str | None, str | None]:
    match = re.match(r'^Điều\s+(\d+[A-Za-z]?)\.\s*(.*)$', line)
    if not match:
        return None, None
    article_number = match.group(1)
    article_title = match.group(2).strip() or None
    return article_number, article_title


def parse_clause_number(line: str) -> str | None:
    match = re.match(r'^(\d+)[.)]\s+', line)
    return match.group(1) if match else None


def parse_point_number(line: str) -> str | None:
    match = re.match(r'^([a-zđ])[.)]\s+', line, re.IGNORECASE)
    return match.group(1) if match else None


def collect_document_context(lines: list[str], file_path: Path) -> dict[str, str | None]:
    title = slug_to_title(file_path)
    for line in lines[:6]:
        if line.isupper() and len(line) > 8 and "LUẬT" in line:
            title = line.title()
            break
    return {
        "document_title": title,
        "part": None,
        "chapter": None,
        "section": None,
        "subsection": None,
    }


def is_uppercase_heading_line(line: str) -> bool:
    if len(line) < 8:
        return False
    if line.startswith("Điều ") or PART_RE.match(line) or CHAPTER_RE.match(line) or SECTION_RE.match(line):
        return False
    has_letters = any(character.isalpha() for character in line)
    return has_letters and not any(character.islower() for character in line)


def normalize_chunking_text(text: str) -> str:
    normalized = INLINE_CLAUSE_RE.sub("\n", text)
    normalized = INLINE_POINT_RE.sub("\n", normalized)
    return normalized


def split_articles(lines: list[str], *, ignore_quoted_articles: bool = False) -> list[dict]:
    articles: list[dict] = []
    current: dict | None = None
    quote_depth = 0

    for line in lines:
        if PART_RE.match(line):
            articles.append({"kind": "context", "part": line})
            quote_depth += line.count("“") - line.count("”")
            continue
        if CHAPTER_RE.match(line):
            articles.append({"kind": "context", "chapter": line})
            quote_depth += line.count("“") - line.count("”")
            continue
        if SECTION_RE.match(line):
            key = "subsection" if line.startswith("Tiểu mục") else "section"
            articles.append({"kind": "context", key: line})
            quote_depth += line.count("“") - line.count("”")
            continue
        if is_uppercase_heading_line(line):
            current = None
            quote_depth += line.count("“") - line.count("”")
            continue
        if ARTICLE_RE.match(line) and not (ignore_quoted_articles and quote_depth > 0):
            article_number, article_title = parse_article_heading(line)
            current = {
                "kind": "article",
                "heading": line,
                "article_number": article_number,
                "article_title": article_title,
                "lines": [line],
            }
            articles.append(current)
            quote_depth += line.count("“") - line.count("”")
            continue
        if current is not None:
            current["lines"].append(line)
        quote_depth += line.count("“") - line.count("”")

    context = {"part": None, "chapter": None, "section": None, "subsection": None}
    resolved: list[dict] = []
    for item in articles:
        if item["kind"] == "context":
            for key in ("part", "chapter", "section", "subsection"):
                if key in item:
                    if key == "section":
                        context["subsection"] = None
                    context[key] = item[key]
            continue
        item["context"] = context.copy()
        resolved.append(item)
    return resolved


def split_clauses(article_lines: list[str]) -> list[dict]:
    body_lines = article_lines[1:]
    clauses: list[dict] = []
    intro_lines: list[str] = []
    current: dict | None = None

    for line in body_lines:
        if CLAUSE_RE.match(line):
            current = {
                "clause_number": parse_clause_number(line),
                "lines": [line],
            }
            clauses.append(current)
            continue
        if current is None:
            intro_lines.append(line)
            continue
        current["lines"].append(line)

    if intro_lines:
        clauses.insert(
            0,
            {
                "clause_number": None,
                "lines": intro_lines,
            },
        )
    return clauses


def split_points(clause_lines: list[str]) -> list[dict]:
    points: list[dict] = []
    intro_lines: list[str] = []
    current: dict | None = None

    for line in clause_lines:
        if POINT_RE.match(line):
            current = {
                "point_number": parse_point_number(line),
                "lines": [line],
            }
            points.append(current)
            continue
        if current is None:
            intro_lines.append(line)
            continue
        current["lines"].append(line)

    if intro_lines:
        points.insert(0, {"point_number": None, "lines": intro_lines})
    return points


def join_lines(lines: list[str]) -> str:
    return "\n".join(line for line in lines if line).strip()


def build_normal_chunks(file_path: Path, text: str, max_chunk_chars: int) -> list[Chunk]:
    lines = [line.strip() for line in normalize_chunking_text(text).splitlines() if line.strip()]
    document_context = collect_document_context(lines, file_path)
    articles = split_articles(lines)
    chunks: list[Chunk] = []

    for article_index, article in enumerate(articles, start=1):
        article_text = join_lines(article["lines"])
        base_meta = {
            "source_file": file_path.name,
            "mode": "normal_mode",
            "article_number": article["article_number"],
            "article_title": article["article_title"],
            "document_title": document_context["document_title"],
            "part": article["context"].get("part"),
            "chapter": article["context"].get("chapter"),
            "section": article["context"].get("section"),
            "subsection": article["context"].get("subsection"),
            "target_law": None,
            "target_article": None,
            "quoted_inner_articles": [],
        }

        if len(article_text) <= max_chunk_chars:
            chunks.append(
                Chunk(
                    chunk_id=f"{file_path.stem}:article:{article_index}",
                    clause_number=None,
                    point_number=None,
                    text=article_text,
                    text_length=len(article_text),
                    **base_meta,
                )
            )
            continue

        clauses = split_clauses(article["lines"])
        for clause_index, clause in enumerate(clauses, start=1):
            clause_text = join_lines([article["heading"], *clause["lines"]])
            if len(clause_text) <= max_chunk_chars:
                chunks.append(
                    Chunk(
                        chunk_id=f"{file_path.stem}:article:{article_index}:clause:{clause_index}",
                        clause_number=clause["clause_number"],
                        point_number=None,
                        text=clause_text,
                        text_length=len(clause_text),
                        **base_meta,
                    )
                )
                continue

            points = split_points(clause["lines"])
            for point_index, point in enumerate(points, start=1):
                point_text = join_lines([article["heading"], *point["lines"]])
                chunks.append(
                    Chunk(
                        chunk_id=(
                            f"{file_path.stem}:article:{article_index}:clause:{clause_index}:point:{point_index}"
                        ),
                        clause_number=clause["clause_number"],
                        point_number=point["point_number"],
                        text=point_text,
                        text_length=len(point_text),
                        **base_meta,
                    )
                )
    return chunks


def detect_target_law(lines: list[str], file_path: Path) -> str | None:
    for line in lines[:12]:
        if line.isupper() and ("SỬA ĐỔI" in line or "BỔ SUNG" in line):
            return line.title()
    return slug_to_title(file_path)


def extract_quoted_inner_articles(text: str) -> list[str]:
    body_text = "\n".join(text.splitlines()[1:])
    seen: list[str] = []
    for match in INNER_TARGET_RE.findall(body_text):
        if match not in seen:
            seen.append(match)
    return seen


def detect_target_article(text: str) -> str | None:
    match = TARGET_ARTICLE_RE.search(text)
    if match:
        return match.group(1)

    quoted_inner_articles = extract_quoted_inner_articles(text)
    return quoted_inner_articles[0] if quoted_inner_articles else None


def build_amendment_chunks(file_path: Path, text: str, max_chunk_chars: int) -> list[Chunk]:
    lines = [line.strip() for line in normalize_chunking_text(text).splitlines() if line.strip()]
    document_context = collect_document_context(lines, file_path)
    target_law = detect_target_law(lines, file_path)
    articles = split_articles(lines, ignore_quoted_articles=True)
    chunks: list[Chunk] = []

    for article_index, article in enumerate(articles, start=1):
        article_text = join_lines(article["lines"])
        quoted_inner_articles = extract_quoted_inner_articles(article_text)
        target_article = detect_target_article(article_text)
        base_meta = {
            "source_file": file_path.name,
            "mode": "amendment_mode",
            "article_number": article["article_number"],
            "article_title": article["article_title"],
            "document_title": document_context["document_title"],
            "part": article["context"].get("part"),
            "chapter": article["context"].get("chapter"),
            "section": article["context"].get("section"),
            "subsection": article["context"].get("subsection"),
            "target_law": target_law,
        }

        if len(article_text) <= max_chunk_chars:
            chunks.append(
                Chunk(
                    chunk_id=f"{file_path.stem}:amendment:{article_index}",
                    clause_number=None,
                    point_number=None,
                    text=article_text,
                    text_length=len(article_text),
                    target_article=target_article,
                    quoted_inner_articles=quoted_inner_articles,
                    **base_meta,
                )
            )
            continue

        clauses = split_clauses(article["lines"])
        for clause_index, clause in enumerate(clauses, start=1):
            clause_text = join_lines([article["heading"], *clause["lines"]])
            clause_target_article = detect_target_article(clause_text)
            clause_inner_articles = extract_quoted_inner_articles(clause_text)
            chunks.append(
                Chunk(
                    chunk_id=f"{file_path.stem}:amendment:{article_index}:clause:{clause_index}",
                    clause_number=clause["clause_number"],
                    point_number=None,
                    text=clause_text,
                    text_length=len(clause_text),
                    target_article=clause_target_article,
                    quoted_inner_articles=clause_inner_articles,
                    **base_meta,
                )
            )
    return chunks


def chunk_file(file_path: Path, max_chunk_chars: int) -> tuple[dict, list[Chunk]]:
    classification = classify_file(file_path)
    raw_text = file_path.read_text(encoding="utf-8")
    cleaned_text = clean_legal_text(raw_text)

    if classification.suggested_mode == "normal_mode":
        chunks = build_normal_chunks(file_path, cleaned_text, max_chunk_chars)
    elif classification.suggested_mode == "amendment_mode":
        chunks = build_amendment_chunks(file_path, cleaned_text, max_chunk_chars)
    else:
        chunks = []

    return asdict(classification), chunks


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chunk corpus luật cho chatbot/RAG.")
    parser.add_argument("--input", default="output/laws", help="Thư mục .txt hoặc file .txt cụ thể.")
    parser.add_argument("--output-dir", default="output/chunks", help="Nơi ghi file chunk.")
    parser.add_argument("--max-chars", type=int, default=1800, help="Ngưỡng tách nhỏ chunk.")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_chunks: list[dict] = []
    report: list[dict] = []

    for file_path in iter_text_files(input_path):
        classification, chunks = chunk_file(file_path, args.max_chars)
        report.append(
            {
                "file": file_path.name,
                "classification": classification,
                "chunk_count": len(chunks),
            }
        )
        if not chunks:
            continue
        chunk_payload = [asdict(chunk) for chunk in chunks]
        write_json(output_dir / f"{file_path.stem}.chunks.json", chunk_payload)
        all_chunks.extend(chunk_payload)

    write_json(output_dir / "chunk_report.json", report)
    (output_dir / "all_chunks.jsonl").write_text(
        "\n".join(json.dumps(chunk, ensure_ascii=False) for chunk in all_chunks),
        encoding="utf-8",
    )

    print(json.dumps({"files": len(report), "chunks": len(all_chunks), "output_dir": str(output_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()