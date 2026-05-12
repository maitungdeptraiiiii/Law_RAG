from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .crawl_laws import clean_legal_text


ARTICLE_RE = re.compile(r"^Điều\s+\d+[A-Za-z]?\.")
SPLIT_ARTICLE_RE = re.compile(r"^Điều$")
CHAPTER_RE = re.compile(r"^Chương\s+[IVXLCDM]+\b")
PART_RE = re.compile(r"^Phần thứ\s+")
SECTION_RE = re.compile(r"^(Mục|Tiểu mục)\b")
CLAUSE_RE = re.compile(r"^\d+[.)]\s")
POINT_RE = re.compile(r"^[a-zđ]\)\s")
INNER_AMENDMENT_ARTICLE_RE = re.compile(r'^["“]?Điều\s+\d+[A-Za-z]?\.')
AMENDMENT_TITLE_RE = re.compile(r"sửa đổi|bổ sung", re.IGNORECASE)
AMENDMENT_CONTEXT_RE = re.compile(
    r"(?:sửa đổi(?:,\s*bổ sung)?|bổ sung|thay thế|bãi bỏ)\s+(?:một số\s+)?(?:điều|khoản)"
    r"|(?:điều|khoản)\s+\d+[A-Za-z]?(?:\s*,\s*khoản\s+\d+)?\s+(?:được\s+)?(?:sửa đổi|bổ sung|thay thế|bãi bỏ)",
    re.IGNORECASE,
)

NOISE_MARKERS = [
    "THƯ VIỆN PHÁP LUẬT",
    "Bài liên quan:",
    "Hỏi đáp pháp luật",
    "PHÁP LUẬT DOANH NGHIỆP",
    "ĐĂNG KÝ THÀNH VIÊN MIỄN PHÍ",
    "Trang Thông tin điện tử tổng hợp",
]


FRAMEWORK_DESCRIPTION = {
    "normal_mode": {
        "root_chunk": "Điều",
        "split_if_long": ["Khoản", "Điểm"],
        "metadata": ["Phần", "Chương", "Mục", "Tiểu mục", "document_title"],
        "notes": "Phù hợp cho luật/bộ luật có cấu trúc tuyến tính, trong đó Điều ở cấp cao nhất.",
    },
    "amendment_mode": {
        "root_chunk": "Điều cấp cao nhất của luật sửa đổi",
        "split_if_long": ["Khoản của Điều sửa đổi", "điểm mục tiêu được sửa đổi"],
        "metadata": ["target_law", "target_article", "quoted_inner_articles"],
        "notes": "Không được coi các 'Điều X' nằm trong dấu ngoặc kép hoặc sau cụm 'như sau:' là chunk top-level mới.",
    },
}


@dataclass
class FileCheckResult:
    path: str
    status: str
    suggested_mode: str | None
    article_count: int
    clause_count: int
    point_count: int
    chapter_count: int
    part_count: int
    section_count: int
    split_article_lines: int
    amendment_title_hint: bool
    amendment_body_hits: int
    has_noise_markers: bool
    raw_length: int
    cleaned_length: int
    reasons: list[str]


def iter_text_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return

    for path in sorted(root.glob("*.txt")):
        yield path


def count_matches(lines: list[str], pattern: re.Pattern[str]) -> int:
    return sum(1 for line in lines if pattern.match(line))


def has_noise(text: str) -> bool:
    return any(marker in text for marker in NOISE_MARKERS)


def detect_amendment_title(path: Path, lines: list[str]) -> bool:
    normalized_name = path.name.lower()
    if "sua-doi" in normalized_name or normalized_name.startswith("luat-sua-doi"):
        return True

    title_lines: list[str] = []
    for line in lines[:12]:
        if line.startswith("Điều ") or line.startswith("Chương "):
            break
        title_lines.append(line)

    title_window = " ".join(title_lines).upper()
    title_markers = (
        "LUẬT SỬA ĐỔI",
        "BỘ LUẬT SỬA ĐỔI",
        "SỬA ĐỔI, BỔ SUNG MỘT SỐ ĐIỀU",
    )
    return any(marker in title_window for marker in title_markers)


def detect_amendment_body_hits(lines: list[str]) -> int:
    hits = 0
    for index, line in enumerate(lines):
        if not INNER_AMENDMENT_ARTICLE_RE.match(line):
            continue

        lookback_window = " ".join(lines[max(0, index - 2):index])
        has_quoted_article = line.startswith("“Điều") or line.startswith('"Điều')
        if AMENDMENT_CONTEXT_RE.search(lookback_window) or has_quoted_article:
            hits += 1
    return hits


def classify_file(path: Path) -> FileCheckResult:
    raw_text = path.read_text(encoding="utf-8")
    cleaned_text = clean_legal_text(raw_text)

    raw_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    cleaned_lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]

    article_count = count_matches(cleaned_lines, ARTICLE_RE)
    clause_count = count_matches(cleaned_lines, CLAUSE_RE)
    point_count = count_matches(cleaned_lines, POINT_RE)
    chapter_count = count_matches(cleaned_lines, CHAPTER_RE)
    part_count = count_matches(cleaned_lines, PART_RE)
    section_count = count_matches(cleaned_lines, SECTION_RE)
    split_article_lines = count_matches(cleaned_lines, SPLIT_ARTICLE_RE)
    amendment_title_hint = detect_amendment_title(path, cleaned_lines)
    amendment_body_hits = detect_amendment_body_hits(cleaned_lines)
    noise_present = has_noise(raw_text)

    reasons: list[str] = []
    status = "not_ready"
    suggested_mode: str | None = None

    if noise_present:
        reasons.append("raw text vẫn còn marker nhiễu từ TVPL")

    if article_count == 0:
        reasons.append("không tìm thấy đủ mốc 'Điều X.' sau khi làm sạch")

    if split_article_lines > 0:
        reasons.append("vẫn còn dòng 'Điều' bị tách riêng, cần chuẩn hóa thêm")

    if amendment_title_hint:
        reasons.append("tiêu đề cho thấy đây là văn bản sửa đổi/bổ sung")

    if amendment_body_hits >= 5:
        reasons.append("phần thân có các 'Điều X' lồng bên trong luật sửa đổi")

    if noise_present and article_count >= 1:
        status = "needs_cleaning_first"
        suggested_mode = "normal_mode"
    elif amendment_title_hint or amendment_body_hits >= 5:
        status = "compatible_with_special_handling"
        suggested_mode = "amendment_mode"
    elif article_count >= 3:
        status = "compatible"
        suggested_mode = "normal_mode"
        reasons.append("có thể chunk theo Điều, rồi hạ xuống Khoản/Điểm nếu quá dài")
    else:
        status = "not_ready"
        suggested_mode = None

    return FileCheckResult(
        path=str(path.name),
        status=status,
        suggested_mode=suggested_mode,
        article_count=article_count,
        clause_count=clause_count,
        point_count=point_count,
        chapter_count=chapter_count,
        part_count=part_count,
        section_count=section_count,
        split_article_lines=split_article_lines,
        amendment_title_hint=amendment_title_hint,
        amendment_body_hits=amendment_body_hits,
        has_noise_markers=noise_present,
        raw_length=len(raw_text),
        cleaned_length=len(cleaned_text),
        reasons=reasons,
    )


def print_summary(results: list[FileCheckResult]) -> None:
    totals: dict[str, int] = {}
    for result in results:
        totals[result.status] = totals.get(result.status, 0) + 1

    print("Chunking framework:")
    print(json.dumps(FRAMEWORK_DESCRIPTION, ensure_ascii=False, indent=2))
    print()
    print("Status summary:")
    for status in sorted(totals):
        print(f"- {status}: {totals[status]}")

    print()
    print("Detailed results:")
    for result in results:
        reason_text = "; ".join(result.reasons) if result.reasons else "không có cảnh báo đặc biệt"
        print(
            f"- {result.path}: status={result.status}, mode={result.suggested_mode}, "
            f"articles={result.article_count}, amendment_hits={result.amendment_body_hits}, "
            f"noise={result.has_noise_markers} | {reason_text}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Đánh giá file luật nào phù hợp với khung chunking theo Điều/Khoản/Điểm."
    )
    parser.add_argument(
        "--input",
        default="output/laws",
        help="Thư mục chứa .txt hoặc một file .txt cụ thể để đánh giá.",
    )
    parser.add_argument(
        "--json-out",
        help="Nếu có, ghi kết quả chi tiết ra file JSON.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    results = [classify_file(path) for path in iter_text_files(input_path)]

    if not results:
        raise SystemExit(f"Không tìm thấy file .txt trong: {input_path}")

    print_summary(results)

    if args.json_out:
        json_path = Path(args.json_out)
        json_path.write_text(
            json.dumps(
                {
                    "framework": FRAMEWORK_DESCRIPTION,
                    "results": [asdict(result) for result in results],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print()
        print(f"Đã ghi JSON: {json_path}")


if __name__ == "__main__":
    main()