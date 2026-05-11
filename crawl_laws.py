from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
import zipfile
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://thuvienphapluat.vn/",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}
URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")
WORD_NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def extract_links_from_docx(docx_path: Path) -> list[dict]:
    with zipfile.ZipFile(docx_path) as archive:
        document_root = ET.fromstring(archive.read("word/document.xml"))
        relationships_root = ET.fromstring(archive.read("word/_rels/document.xml.rels"))

    hyperlink_map = {
        relationship.attrib["Id"]: relationship.attrib.get("Target", "")
        for relationship in relationships_root.findall("rel:Relationship", WORD_NS)
        if relationship.attrib.get("TargetMode") == "External"
    }

    items: list[dict] = []
    current_main: dict | None = None

    for paragraph in document_root.findall(".//w:body/w:p", WORD_NS):
        paragraph_text = extract_paragraph_text(paragraph)
        paragraph_urls = extract_paragraph_urls(paragraph, hyperlink_map)
        if not paragraph_urls:
            continue

        is_bold = paragraph_is_bold(paragraph)
        is_indented = paragraph_is_indented(paragraph)
        level = classify_paragraph(
            is_bold=is_bold,
            is_indented=is_indented,
            has_current_main=current_main is not None,
        )

        for url in paragraph_urls:
            item = {
                "url": url,
                "label": paragraph_text or slug_to_title(url),
                "level": level,
                "is_bold": is_bold,
                "is_indented": is_indented,
                "parent_main_url": current_main["url"] if level == "supplementary" and current_main else None,
                "parent_main_label": current_main["label"] if level == "supplementary" and current_main else None,
            }
            items.append(item)

            if level == "main":
                current_main = {"url": url, "label": item["label"]}

    return items


def extract_urls_from_docx(docx_path: Path) -> list[str]:
    return [item["url"] for item in extract_links_from_docx(docx_path)]


def extract_paragraph_urls(paragraph: ET.Element, hyperlink_map: dict[str, str]) -> list[str]:
    urls: list[str] = []
    for hyperlink in paragraph.findall("w:hyperlink", WORD_NS):
        relationship_id = hyperlink.attrib.get(f"{{{WORD_NS['r']}}}id")
        target = hyperlink_map.get(relationship_id or "", "").strip()
        if target:
            urls.append(unescape_xml(target))
            continue

        inline_text = extract_paragraph_text(hyperlink)
        match = URL_PATTERN.search(inline_text)
        if match:
            urls.append(unescape_xml(match.group(0)))
    return urls


def extract_paragraph_text(node: ET.Element) -> str:
    chunks = [text_node.text or "" for text_node in node.findall(".//w:t", WORD_NS)]
    return "".join(chunks).strip()


def paragraph_is_bold(paragraph: ET.Element) -> bool:
    return paragraph.find(".//w:b", WORD_NS) is not None


def paragraph_is_indented(paragraph: ET.Element) -> bool:
    if paragraph.find(".//w:tab", WORD_NS) is not None:
        return True

    indent = paragraph.find("w:pPr/w:ind", WORD_NS)
    if indent is None:
        return False

    indent_keys = ("left", "start", "hanging", "firstLine")
    for key in indent_keys:
        value = indent.attrib.get(f"{{{WORD_NS['w']}}}{key}", "0") or "0"
        if int(value) > 0:
            return True
    return False


def classify_paragraph(*, is_bold: bool, is_indented: bool, has_current_main: bool) -> str:
    if is_bold and not is_indented:
        return "main"
    if is_indented:
        return "supplementary"
    if has_current_main and not is_bold:
        return "supplementary"
    return "main"


def unescape_xml(text: str) -> str:
    return (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
    )


def slug_to_title(url: str) -> str:
    slug = Path(urlparse(url).path).stem
    slug = re.sub(r"-\d+$", "", slug)
    return slug.replace("-", " ").strip() or url


def sanitize_filename(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return normalized[:120] or fallback


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session


def warm_up_session(session: requests.Session, timeout: int) -> None:
    try:
        session.get("https://thuvienphapluat.vn/", timeout=timeout, allow_redirects=True)
    except requests.RequestException:
        pass


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    try:
        import fitz
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Thieu PyMuPDF. Cai dat bang lenh: pip install PyMuPDF"
        ) from exc

    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        pages = [page.get_text("text") for page in document]
    return "\n".join(page.strip() for page in pages if page.strip()).strip()


def collapse_text_lines(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    compact = [line for line in lines if line]
    return "\n".join(compact)


LEGAL_START_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"^(QUỐC HỘI|ỦY BAN THƯỜNG VỤ QUỐC HỘI|CHÍNH PHỦ|BỘ [A-ZĂÂÊÔƠƯĐ].*)$",
        r"^CỘNG HÒA XÃ( HỘI)? CHỦ NGHĨA VIỆT NAM$",
        r"^(Luật|Nghị định|Nghị quyết|Thông tư|Quyết định|Pháp lệnh) số:$",
        r"^(LUẬT|BỘ LUẬT|NGHỊ QUYẾT|NGHỊ ĐỊNH|PHÁP LỆNH|THÔNG TƯ|QUYẾT ĐỊNH)$",
    )
]
DOCUMENT_TITLE_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"^(LUẬT|BỘ LUẬT|NGHỊ QUYẾT|NGHỊ ĐỊNH|PHÁP LỆNH|THÔNG TƯ|QUYẾT ĐỊNH)$",
        r"^(PHẦN|CHƯƠNG)\s+.+$",
        r"^Điều\s+1\."
    )
]
FOOTER_MARKERS = {
    "Lưu trữ",
    "Ghi chú",
    "Ý kiến",
    "Facebook",
    "Email",
    "In",
    "Bài liên quan:",
    "Hỏi đáp pháp luật",
    "PHÁP LUẬT DOANH NGHIỆP",
}
EXCLUDED_HTML_CONTAINER_CLASSES = {
    "NoiDungChiaSe",
    "box_bm_m",
    "ttlq",
}
ROMAN_NUMERAL_RE = re.compile(r"^(?=[IVXLCDM]+$)[IVXLCDM]+$")
ARTICLE_NUMBER_RE = re.compile(r"^\d+[A-Za-z]?\.")
CLAUSE_LINE_RE = re.compile(r"^\d+[.)]\s")
POINT_LINE_RE = re.compile(r"^[a-zđ][.)]\s", re.IGNORECASE)
VIETNAMESE_VOWEL_CHARS = set("aeiouyAEIOUYăâêôơưĂÂÊÔƠƯáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵÁÀẢÃẠẮẰẲẴẶẤẦẨẪẬÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢÚÙỦŨỤỨỪỬỮỰÝỲỶỸỴ")
COMMON_LEGAL_REPLACEMENTS = [
    (re.compile(pattern), replacement)
    for pattern, replacement in (
        (r"\bS ửa\b", "Sửa"),
        (r"\bs ửa\b", "sửa"),
        (r"\bB ổ sung\b", "Bổ sung"),
        (r"\bb ổ sung\b", "bổ sung"),
        (r"\bĐ ối\b", "Đối"),
        (r"\bđ ối\b", "đối"),
        (r"\bPh ụ\b", "Phụ"),
        (r"\bph ụ\b", "phụ"),
        (r"\bNgư ời\b", "Người"),
        (r"\bngư ời\b", "người"),
        (r"\bđư ợc\b", "được"),
        (r"\bĐư ợc\b", "Được"),
        (r"\bTrư ờng\b", "Trường"),
        (r"\btrư ờng\b", "trường"),
        (r"\bTh ời\b", "Thời"),
        (r"\bth ời\b", "thời"),
        (r"\bC ủa\b", "Của"),
        (r"\bc ủa\b", "của"),
        (r"\bVi ph ạm\b", "Vi phạm"),
        (r"\bvi ph ạm\b", "vi phạm"),
        (r"\bPh ạm\b", "Phạm"),
        (r"\bph ạm\b", "phạm"),
        (r"\bHo ặc\b", "Hoặc"),
        (r"\bho ặc\b", "hoặc"),
        (r"\bThi ệt\b", "Thiệt"),
        (r"\bthi ệt\b", "thiệt"),
        (r"\bQuy đ ịnh\b", "Quy định"),
        (r"\bquy đ ịnh\b", "quy định"),
        (r"\bTòaán\b", "Tòa án"),
        (r"\bTÒAÁN\b", "TÒA ÁN"),
        (r"\bBảnán\b", "Bản án"),
        (r"\bCôngan\b", "Công an"),
        (r"\bViệcyêu cầu\b", "Việc yêu cầu"),
        (r"\bđượcyêu cầu\b", "được yêu cầu"),
        (r"\bĐượcyêu cầu\b", "Được yêu cầu"),
        (r"\bđãyêu cầu\b", "đã yêu cầu"),
        (r"\bĐãyêu cầu\b", "Đã yêu cầu"),
        (r"\bđượcáp dụng\b", "được áp dụng"),
        (r"\bthi hànhán\b", "thi hành án"),
        (r"\bkếtán\b", "kết án"),
        (r"\bXóaán\b", "Xóa án"),
        (r"\bxóaán\b", "xóa án"),
        (r"\bquyếtđịnh\b", "quyết định"),
        (r"\bViệtNamở\b", "Việt Nam ở"),
    )
]


def looks_like_legal_start(line: str) -> bool:
    return any(pattern.match(line) for pattern in LEGAL_START_PATTERNS)


def trim_non_content_prefix(lines: list[str]) -> list[str]:
    for index, line in enumerate(lines):
        if line == "MỤC LỤC":
            return lines[index + 1 :]

    for index, line in enumerate(lines):
        if any(pattern.match(line) for pattern in DOCUMENT_TITLE_PATTERNS):
            return lines[index:]

    start_index = 0
    for index, line in enumerate(lines):
        if looks_like_legal_start(line):
            start_index = index
            break
    return lines[start_index:]


def trim_tvpl_footer(lines: list[str]) -> list[str]:
    for index, line in enumerate(lines):
        if line not in FOOTER_MARKERS:
            continue

        nearby = lines[index : index + 8]
        marker_hits = sum(1 for candidate in nearby if candidate in FOOTER_MARKERS)
        if marker_hits >= 2:
            return lines[:index]
    return lines


def normalize_heading_lines(lines: list[str]) -> list[str]:
    normalized: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]

        if line == "Điều" and index + 1 < len(lines):
            normalized.append(f"Điều {lines[index + 1]}")
            index += 2
            continue

        if re.match(r"^Điều\s+\d+[A-Za-z]?\.", line) and index + 1 < len(lines):
            next_line = lines[index + 1]
            if not is_heading_line(next_line) and not is_list_item_start(next_line):
                title_parts = [line, next_line]
                step = 2
                while index + step < len(lines):
                    candidate = lines[index + step]
                    if is_heading_line(candidate) or is_list_item_start(candidate):
                        break
                    title_parts.append(candidate)
                    step += 1
                    if step >= 3:
                        break
                normalized.append(" ".join(title_parts))
                index += step
                continue

        if line in {"Phần", "Chương", "Mục", "Tiểu mục"} and index + 1 < len(lines):
            pieces = [line, lines[index + 1]]
            step = 2
            if line == "Chương" and ROMAN_NUMERAL_RE.match(lines[index + 1]) and index + 2 < len(lines):
                pieces.append(lines[index + 2])
                step = 3
            elif line in {"Mục", "Tiểu mục"} and index + 2 < len(lines):
                pieces.append(lines[index + 2])
                step = 3
            normalized.append(" ".join(pieces))
            index += step
            continue

        if re.match(r"^Phần thứ\s+", line) and index + 1 < len(lines):
            next_line = lines[index + 1]
            if next_line.isupper():
                normalized.append(f"{line} {next_line}")
                index += 2
                continue

        normalized.append(line)
        index += 1

    return normalized


def is_heading_line(line: str) -> bool:
    if re.match(r"^Điều\s+\d+[A-Za-z]?\.", line):
        return True
    return line.startswith(("Phần ", "Chương ", "Mục ", "Tiểu mục "))


def is_standalone_uppercase_title(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 120:
        return False
    if stripped.endswith((".", ";", ":", ",")):
        return False
    if any(character.islower() for character in stripped):
        return False

    letters = [character for character in stripped if character.isalpha()]
    if not letters:
        return False

    return all(character.isupper() for character in letters)


def is_list_item_start(line: str) -> bool:
    return bool(CLAUSE_LINE_RE.match(line) or POINT_LINE_RE.match(line))


def should_join_without_space(previous_line: str, next_line: str) -> bool:
    previous = previous_line.strip()
    upcoming = next_line.strip()
    if not previous or not upcoming:
        return False

    if upcoming[0] in ",.;:)]}":
        return True

    last_token = previous.split()[-1]
    if len(last_token) > 4 or not last_token.isalpha():
        return False

    first_char = upcoming[0]
    return first_char.isalpha() and first_char in VIETNAMESE_VOWEL_CHARS


def merge_wrapped_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    buffer = ""

    for line in lines:
        if is_heading_line(line) or is_standalone_uppercase_title(line):
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append(line)
            continue

        if is_list_item_start(line):
            if buffer:
                merged.append(buffer)
            buffer = line
            continue

        if not buffer:
            buffer = line
            continue

        separator = "" if should_join_without_space(buffer, line) else " "
        buffer = f"{buffer}{separator}{line}"

    if buffer:
        merged.append(buffer)

    return merged


def should_fix_word_gap(left: str, right: str) -> bool:
    if not left or not right:
        return False

    if right[0].lower() not in VIETNAMESE_VOWEL_CHARS:
        return False

    if len(left) == 1:
        return True

    consonants_only = all(character.lower() not in VIETNAMESE_VOWEL_CHARS for character in left)
    if consonants_only and len(left) <= 2:
        return True

    return left[0].isupper() and len(left) <= 3 and left[-1].lower() in {"ư", "i", "u", "y"}


def repair_split_words(line: str) -> str:
    tokens = line.split()
    if not tokens:
        return ""

    repaired: list[str] = []
    index = 0

    while index < len(tokens):
        current = tokens[index]

        while index + 1 < len(tokens) and should_fix_word_gap(current, tokens[index + 1]):
            current = f"{current}{tokens[index + 1]}"
            index += 1

        if repaired and current in {",", ".", ";", ":", ")"}:
            repaired[-1] = f"{repaired[-1]}{current}"
        else:
            repaired.append(current)

        index += 1

    return " ".join(repaired)


def repair_common_legal_phrases(line: str) -> str:
    repaired = line
    for pattern, replacement in COMMON_LEGAL_REPLACEMENTS:
        repaired = pattern.sub(replacement, repaired)
    return repaired


def split_runon_article_heading(line: str) -> list[str]:
    match = re.match(r"^(Điều\s+\d+[A-Za-z]?\.\s+)(.+)$", line)
    if not match:
        return [line]

    prefix, remainder = match.groups()
    if remainder.startswith("Áp dụng"):
        return [line]

    body_markers = (
        "Trong Luật này",
        "Trong Bộ luật này",
        "Luật này quy định",
        "Bộ luật này quy định",
        "Luật này áp dụng",
        "Bộ luật này áp dụng",
        "Việc ",
        "Khi ",
        "Tòa án có",
        "Tòa án phải",
        "Tòa án tiến hành",
        "Tòa án quyết định",
        "Tòa án xem xét",
        "Người nào",
        "Người bị",
        "Người được",
        "Người tham gia",
        "Người có",
        "Trường hợp ",
    )

    candidate_indexes = [
        remainder.find(marker)
        for marker in body_markers
        if remainder.find(marker) > 12
    ]
    if not candidate_indexes:
        return [line]

    marker_index = min(candidate_indexes)
    title = remainder[:marker_index].rstrip()
    body = remainder[marker_index:].strip()
    if not title or not body:
        return [line]

    return [f"{prefix}{title}", body]

    return [line]


def split_runon_heading_lines(lines: list[str]) -> list[str]:
    normalized: list[str] = []
    for line in lines:
        normalized.extend(split_runon_article_heading(line))
    return normalized


def clean_legal_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""

    lines = trim_non_content_prefix(lines)
    lines = trim_tvpl_footer(lines)
    lines = normalize_heading_lines(lines)
    lines = merge_wrapped_lines(lines)
    lines = [repair_split_words(line) for line in lines]
    lines = [repair_common_legal_phrases(line) for line in lines]
    lines = split_runon_heading_lines(lines)
    return "\n".join(lines).strip()


def has_excluded_html_ancestor(node: BeautifulSoup) -> bool:
    parent = node
    while parent is not None:
        classes = parent.get("class", []) if hasattr(parent, "get") else []
        if any(class_name in EXCLUDED_HTML_CONTAINER_CLASSES for class_name in classes):
            return True
        parent = getattr(parent, "parent", None)
    return False


def extract_paragraph_like_lines(node: BeautifulSoup) -> list[str]:
    def collect(selector: str) -> list[str]:
        lines: list[str] = []
        seen: set[str] = set()

        for block in node.select(selector):
            if has_excluded_html_ancestor(block):
                continue
            text = " ".join(block.get_text(" ", strip=True).split())
            if not text or text in seen or text in FOOTER_MARKERS:
                continue
            seen.add(text)
            lines.append(text)

        return lines

    paragraph_lines = collect("p, li")
    if paragraph_lines:
        return paragraph_lines

    return collect("tr")


def extract_tvpl_document_text(soup: BeautifulSoup) -> str:
    selectors = [
        "#ctl00_Content_ThongTinVB_pnlDocContent",
        "#divContentDoc",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue

        paragraph_lines = extract_paragraph_like_lines(node)
        if paragraph_lines:
            text = "\n".join(trim_tvpl_footer(paragraph_lines))
        else:
            text = collapse_text_lines(node.get_text("\n"))
        if "Điều 1." in text or "Chương I" in text:
            return text
    return ""


def extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    document_text = extract_tvpl_document_text(soup)
    if document_text:
        return document_text

    return collapse_text_lines(soup.get_text("\n"))


def detect_document_type(content_type: str, final_url: str) -> str:
    content_type = content_type.lower()
    if "pdf" in content_type or final_url.lower().endswith(".pdf"):
        return "pdf"
    if "html" in content_type or final_url.lower().endswith((".aspx", ".html", ".htm")):
        return "html"
    return "unknown"


def fetch_document(
    session: requests.Session,
    url: str,
    timeout: int,
    max_attempts: int = 3,
    apply_clean: bool = False,
) -> dict:
    response: requests.Response | None = None
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        active_session = session if attempt == 1 else create_session()
        try:
            if attempt > 1:
                warm_up_session(active_session, timeout)
            response = active_session.get(url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            break
        except requests.HTTPError as exc:
            last_error = exc
            if response is None or response.status_code != 403 or attempt == max_attempts:
                raise
            time.sleep(min(3 * attempt, 12))
        except requests.RequestException as exc:
            last_error = exc
            if attempt == max_attempts:
                raise
            time.sleep(min(attempt, 3))
    else:
        raise RuntimeError(f"Khong the tai tai lieu: {url}") from last_error

    content_type = response.headers.get("Content-Type", "")
    final_url = response.url
    doc_type = detect_document_type(content_type, final_url)

    if doc_type == "pdf":
        content_text = extract_text_from_pdf(response.content)
    else:
        response.encoding = response.encoding or response.apparent_encoding or "utf-8"
        content_text = extract_text_from_html(response.text)

    if apply_clean:
        content_text = clean_legal_text(content_text)

    return {
        "source_url": url,
        "final_url": final_url,
        "content_type": content_type,
        "document_type": doc_type,
        "title": slug_to_title(url),
        "text": content_text,
        "text_length": len(content_text),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def save_document(output_dir: Path, payload: dict, index: int) -> dict:
    file_index = int(payload.get("source_index", index))
    base_name = sanitize_filename(
        Path(urlparse(payload["source_url"]).path).stem,
        fallback=f"document_{file_index:03d}",
    )
    json_path = output_dir / f"{file_index:03d}_{base_name}.json"
    text_path = output_dir / f"{file_index:03d}_{base_name}.txt"

    text_path.write_text(payload["text"], encoding="utf-8")
    json_payload = {**payload, "text_path": str(text_path.name)}
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "index": file_index,
        "source_url": payload["source_url"],
        "level": payload.get("level"),
        "parent_main_url": payload.get("parent_main_url"),
        "parent_main_label": payload.get("parent_main_label"),
        "final_url": payload["final_url"],
        "document_type": payload["document_type"],
        "text_length": payload["text_length"],
        "json_file": json_path.name,
        "text_file": text_path.name,
    }


def crawl_all(
    link_items: Iterable[dict],
    output_dir: Path,
    delay_seconds: float,
    timeout: int,
    apply_clean: bool,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    session = create_session()

    manifest: list[dict] = []
    errors: list[dict] = []

    for index, link_item in enumerate(link_items, start=1):
        url = link_item["url"]
        try:
            payload = fetch_document(session, url, timeout=timeout, apply_clean=apply_clean)
            payload.update(
                {
                    "source_index": link_item.get("source_index", index),
                    "level": link_item.get("level"),
                    "is_bold": link_item.get("is_bold"),
                    "is_indented": link_item.get("is_indented"),
                    "label": link_item.get("label"),
                    "parent_main_url": link_item.get("parent_main_url"),
                    "parent_main_label": link_item.get("parent_main_label"),
                }
            )
            if not payload["text"].strip():
                raise ValueError("Extracted text is empty")
            saved = save_document(output_dir, payload, index)
            manifest.append(saved)
            print(
                f"[{index}] OK  {url} [{payload['level']}] -> "
                f"{saved['text_file']} ({saved['text_length']} chars)"
            )
        except Exception as exc:
            errors.append(
                {
                    "index": index,
                    "url": url,
                    "level": link_item.get("level"),
                    "parent_main_url": link_item.get("parent_main_url"),
                    "error": str(exc),
                }
            )
            print(f"[{index}] ERR {url} -> {exc}")
        time.sleep(delay_seconds)

    manifest_path = output_dir / "manifest.json"
    manifest_payload = {
        "total": len(manifest) + len(errors),
        "success": len(manifest),
        "failed": len(errors),
        "items": manifest,
        "errors": errors,
    }
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl danh sach van ban luat tu file DOCX va luu thanh JSON/TXT"
    )
    parser.add_argument(
        "--docx",
        default="luat.docx",
        help="Duong dan toi file DOCX chua danh sach URL",
    )
    parser.add_argument(
        "--output",
        default="output/laws",
        help="Thu muc luu ket qua crawl",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="So giay nghi giua moi request",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout cho moi request, tinh bang giay",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Chi crawl N URL dau tien de test nhanh",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Ap dung clean_legal_text truoc khi luu. Mac dinh la tat de luu raw extracted text.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    docx_path = Path(args.docx)
    if not docx_path.exists():
        raise FileNotFoundError(f"Khong tim thay file DOCX: {docx_path}")

    link_items = extract_links_from_docx(docx_path)
    if args.limit is not None:
        link_items = link_items[: args.limit]

    if not link_items:
        raise ValueError("Khong tim thay URL nao trong file DOCX")

    main_count = sum(1 for item in link_items if item["level"] == "main")
    supplementary_count = sum(1 for item in link_items if item["level"] == "supplementary")
    print(
        f"Tim thay {len(link_items)} URL de crawl "
        f"({main_count} main, {supplementary_count} supplementary)"
    )
    manifest = crawl_all(
        link_items=link_items,
        output_dir=Path(args.output),
        delay_seconds=args.delay,
        timeout=args.timeout,
        apply_clean=args.clean,
    )
    print(
        f"Hoan tat: {manifest['success']} thanh cong, {manifest['failed']} that bai. "
        f"Manifest: {Path(args.output) / 'manifest.json'}"
    )
    return 0 if manifest["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())