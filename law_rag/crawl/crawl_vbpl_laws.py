from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup


API_BASE = "https://vbpl-bientap-gateway.moj.gov.vn/api"
DOC_ALL_ENDPOINT = f"{API_BASE}/qtdc/public/doc/all"
DOC_DETAIL_ENDPOINT = f"{API_BASE}/qtdc/public/doc"

DOC_TYPE_LAW = "11025e19-2dd6-4165-85ad-ab6241186a1a"
DOC_TYPE_CODE = "404b68a7-8e71-4ee5-a6c0-07e59f35f824"
STATUS_EFFECTIVE = "1419f6be-4a15-44a7-97ac-ea042770a514"
STATUS_PARTLY_EXPIRED = "9c20e89d-e048-4f3a-b6c2-df87fe0b1ada"
STATUS_PARTLY_SUSPENDED = "d1189072-7aed-44d8-bcaf-d89409adcded"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
ARTICLE_HEADING_RE = re.compile(r"^\s*\u0110i\u1ec1u\s+(\d+[A-Za-z]?)\s*[\.:]?", re.IGNORECASE)
MAX_CHUNK_CHARS = 10_000

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "https://vbpl.vn",
            "Referer": "https://vbpl.vn/van-ban/trung-uong",
        }
    )
    return session


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def collapse_lines(text: str) -> str:
    lines = [clean_text(line) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def sanitize_filename(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return normalized[:150] or fallback


def name_of(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("name")
    if isinstance(value, str):
        return value
    return None


def code_of(value: Any) -> str | None:
    return value.get("code") if isinstance(value, dict) else None


def names_from_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        if isinstance(item, dict) and item.get("name"):
            names.append(item["name"])
        elif isinstance(item, str):
            names.append(item)
    return names


def fetch_list(session: requests.Session, page_number: int, page_size: int, timeout: int) -> dict:
    payload = {
        "pageNumber": page_number,
        "pageSize": page_size,
        "docType": [DOC_TYPE_LAW, DOC_TYPE_CODE],
        "effStatus": [STATUS_EFFECTIVE, STATUS_PARTLY_EXPIRED, STATUS_PARTLY_SUSPENDED],
    }
    response = session.post(DOC_ALL_ENDPOINT, json=payload, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success", True):
        raise RuntimeError(payload)
    return payload["data"]


def fetch_detail(session: requests.Session, doc_id: str, timeout: int) -> dict:
    response = session.get(f"{DOC_DETAIL_ENDPOINT}/{doc_id}", timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success", True):
        raise RuntimeError(payload)
    return payload["data"]


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return collapse_lines(soup.get_text("\n"))


def html_blocks(html: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "lxml")
    blocks: list[dict] = []
    for node in soup.select("p, td, th, li"):
        text = clean_text(node.get_text(" "))
        if not text:
            continue
        classes = node.get("class", [])
        blocks.append(
            {
                "id": node.get("id"),
                "class": " ".join(classes) if isinstance(classes, list) else str(classes),
                "text": text,
            }
        )
    return blocks


def preprocess_blocks(blocks: list[dict]) -> list[dict]:
    cleaned: list[dict] = []
    last_text = ""
    for block in blocks:
        text = clean_text(str(block.get("text") or ""))
        if not text:
            continue
        if text == last_text:
            continue
        cleaned.append(
            {
                "id": block.get("id"),
                "class": clean_text(str(block.get("class") or "")),
                "text": text,
            }
        )
        last_text = text
    return cleaned


def flatten_tree(nodes: Any, depth: int = 0, parent_id: str | None = None) -> list[dict]:
    if not isinstance(nodes, list):
        return []
    flattened: list[dict] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or node.get("provisionId") or node.get("key") or "")
        title = node.get("title") or node.get("name") or node.get("label") or node.get("text")
        item = {
            "id": node_id or None,
            "parent_id": parent_id,
            "depth": depth,
            "title": clean_text(str(title)) if title else None,
            "type": node.get("type") or node.get("provisionType") or node.get("nodeType"),
            "article_number": node.get("articleNumber") or node.get("number"),
        }
        flattened.append(item)
        children = (
            node.get("children")
            or node.get("childrens")
            or node.get("items")
            or node.get("provisions")
            or []
        )
        flattened.extend(flatten_tree(children, depth + 1, node_id or parent_id))
    return flattened


def chunk_by_articles(blocks: list[dict], metadata: dict) -> list[dict]:
    blocks = preprocess_blocks(blocks)
    chunks: list[dict] = []
    current: dict | None = None
    context: dict[str, str | None] = {"part": None, "chapter": None, "section": None}

    heading_classes = {
        "prov-part": "part",
        "prov-chapter": "chapter",
        "prov-section": "section",
    }

    for block in blocks:
        block_class = block.get("class") or ""
        text = block["text"]
        for class_name, key in heading_classes.items():
            if class_name in block_class:
                context[key] = text

        is_article = is_article_heading(text)
        if is_article:
            if current:
                chunks.extend(split_long_chunk(finalize_chunk(current)))
            article_number = extract_article_number(text)
            current = {
                "chunk_id": f"{metadata['vbpl_id']}:article:{article_number or len(chunks) + 1}",
                "vbpl_id": metadata["vbpl_id"],
                "doc_number": metadata.get("doc_number"),
                "document_title": metadata.get("title"),
                "article_number": article_number,
                "article_title": text,
                "part": context["part"],
                "chapter": context["chapter"],
                "section": context["section"],
                "texts": [text],
            }
            continue

        if current:
            current["texts"].append(text)

    if current:
        chunks.extend(split_long_chunk(finalize_chunk(current)))

    if chunks:
        return ensure_unique_chunk_ids([chunk for chunk in chunks if chunk.get("text")])

    full_text = "\n".join(block["text"] for block in blocks)
    fallback = {
        "chunk_id": f"{metadata['vbpl_id']}:full",
        "vbpl_id": metadata["vbpl_id"],
        "doc_number": metadata.get("doc_number"),
        "document_title": metadata.get("title"),
        "article_number": None,
        "article_title": None,
        "text": full_text,
        "text_length": len(full_text),
    }
    return split_long_chunk(fallback) if full_text.strip() else []


def is_article_heading(text: str) -> bool:
    return bool(ARTICLE_HEADING_RE.match(text))


def split_long_chunk(chunk: dict, max_chars: int = MAX_CHUNK_CHARS) -> list[dict]:
    text = str(chunk.get("text") or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        chunk["text"] = text
        chunk["text_length"] = len(text)
        return [chunk]

    parts: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in text.splitlines():
        paragraph = clean_text(paragraph)
        if not paragraph:
            continue
        if len(paragraph) > max_chars:
            if current:
                parts.append("\n".join(current))
                current = []
                current_len = 0
            parts.extend(split_text_by_sentences(paragraph, max_chars))
            continue
        extra = len(paragraph) + (1 if current else 0)
        if current and current_len + extra > max_chars:
            parts.append("\n".join(current))
            current = [paragraph]
            current_len = len(paragraph)
        else:
            current.append(paragraph)
            current_len += extra
    if current:
        parts.append("\n".join(current))

    if len(parts) <= 1:
        chunk["text"] = text[:max_chars]
        chunk["text_length"] = len(chunk["text"])
        return [chunk]

    results: list[dict] = []
    total = len(parts)
    for index, part in enumerate(parts, start=1):
        subchunk = dict(chunk)
        subchunk["chunk_id"] = f"{chunk['chunk_id']}:part:{index}"
        subchunk["subchunk_number"] = index
        subchunk["subchunk_count"] = total
        subchunk["text"] = part
        subchunk["text_length"] = len(part)
        results.append(subchunk)
    return results


def split_text_by_sentences(text: str, max_chars: int) -> list[str]:
    sentences = re.split(r"(?<=[.;:])\s+", text)
    parts: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > max_chars:
            if current:
                parts.append(current)
                current = ""
            parts.extend(sentence[index : index + max_chars] for index in range(0, len(sentence), max_chars))
            continue
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_chars:
            parts.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def ensure_unique_chunk_ids(chunks: list[dict]) -> list[dict]:
    seen: dict[str, int] = {}
    for chunk in chunks:
        chunk_id = str(chunk["chunk_id"])
        count = seen.get(chunk_id, 0)
        if count:
            chunk["chunk_id"] = f"{chunk_id}:dup:{count + 1}"
        seen[chunk_id] = count + 1
    return chunks


def build_chunk_quality_report(chunks: list[dict]) -> dict:
    ids = [chunk.get("chunk_id") for chunk in chunks]
    lengths = [int(chunk.get("text_length") or len(chunk.get("text") or "")) for chunk in chunks]
    return {
        "chunk_count": len(chunks),
        "duplicate_chunk_ids": len(ids) - len(set(ids)),
        "empty_chunks": sum(1 for chunk in chunks if not str(chunk.get("text") or "").strip()),
        "short_chunks_lt_50_chars": sum(1 for length in lengths if length < 50),
        "long_chunks_gt_max_chars": sum(1 for length in lengths if length > MAX_CHUNK_CHARS),
        "max_chunk_chars": max(lengths) if lengths else 0,
    }


def extract_article_number(text: str) -> str | None:
    match = ARTICLE_HEADING_RE.match(text)
    return match.group(1).lower() if match else None


def finalize_chunk(chunk: dict) -> dict:
    text = "\n".join(clean_text(line) for line in chunk.pop("texts") if clean_text(line))
    chunk["text"] = text
    chunk["text_length"] = len(text)
    return chunk


def metadata_from_detail(detail: dict) -> dict:
    return {
        "vbpl_id": str(detail.get("id")),
        "title": detail.get("title"),
        "doc_number": detail.get("docNum"),
        "doc_type": name_of(detail.get("docType")),
        "doc_type_code": code_of(detail.get("docType")),
        "agency_name": detail.get("agencyName"),
        "issue_date": detail.get("issueDate"),
        "effective_from": detail.get("effFrom"),
        "effective_to": detail.get("effTo"),
        "public_date": detail.get("publicDate"),
        "updated_date": detail.get("updatedDate"),
        "effective_status": name_of(detail.get("effStatus")),
        "effective_status_code": code_of(detail.get("effStatus")),
        "majors": names_from_list(detail.get("documentMajors")),
        "fields": names_from_list(detail.get("documentFields")),
        "issues": names_from_list(detail.get("documentIssues")),
        "signer_title": detail.get("signerTitle") or detail.get("positionName") or detail.get("signerPosition"),
        "signer": detail.get("signer") or detail.get("signerName"),
        "organization": name_of(detail.get("organization")),
        "has_content": detail.get("hasContent"),
        "is_old": detail.get("isOld"),
        "source_url": f"https://vbpl.vn/van-ban/chi-tiet/{detail.get('id')}",
    }


def write_csv(path: Path, records: list[dict]) -> None:
    if not records:
        path.write_text("", encoding="utf-8-sig")
        return
    fields = [
        "vbpl_id",
        "title",
        "doc_number",
        "doc_type",
        "agency_name",
        "issue_date",
        "effective_from",
        "effective_to",
        "effective_status",
        "majors",
        "fields",
        "signer_title",
        "signer",
        "text_length",
        "chunks_file",
        "text_file",
        "html_file",
        "source_url",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = {field: record.get(field, "") for field in fields}
            row["majors"] = " | ".join(record.get("majors") or [])
            row["fields"] = " | ".join(record.get("fields") or [])
            writer.writerow(row)


def crawl(args: argparse.Namespace) -> dict:
    output_dir = Path(args.output)
    html_dir = output_dir / "html"
    text_dir = output_dir / "texts"
    chunks_dir = output_dir / "chunks"
    tree_dir = output_dir / "toc"
    for directory in [html_dir, text_dir, chunks_dir, tree_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    session = create_session()
    records: list[dict] = []
    errors: list[dict] = []
    all_chunks: list[dict] = []
    page_number = 1
    total: int | None = None

    while True:
        page = fetch_list(session, page_number, args.page_size, args.timeout)
        total = total or page["total"]
        items = page.get("items", [])
        print(f"[list page {page_number}] fetched {len(items)} / total {total}", flush=True)

        for item in items:
            if args.limit and len(records) >= args.limit:
                break
            doc_id = str(item["id"])
            try:
                detail = fetch_detail(session, doc_id, args.timeout)
                metadata = metadata_from_detail(detail)
                stem = sanitize_filename(
                    f"{metadata.get('doc_number') or doc_id}_{metadata.get('title') or ''}",
                    fallback=f"vbpl_{doc_id}",
                )
                html = (detail.get("documentContent") or {}).get("content") or ""
                text = html_to_text(html)
                blocks = html_blocks(html)
                toc = flatten_tree(detail.get("provisionTree"))
                chunks = chunk_by_articles(blocks, metadata)

                html_file = html_dir / f"{stem}.html"
                text_file = text_dir / f"{stem}.txt"
                chunks_file = chunks_dir / f"{stem}.chunks.json"
                toc_file = tree_dir / f"{stem}.toc.json"

                html_file.write_text(html, encoding="utf-8")
                text_file.write_text(text, encoding="utf-8")
                chunks_file.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
                toc_file.write_text(json.dumps(toc, ensure_ascii=False, indent=2), encoding="utf-8")

                record = {
                    **metadata,
                    "text_length": len(text),
                    "chunk_count": len(chunks),
                    "toc_count": len(toc),
                    "html_file": f"html/{html_file.name}",
                    "text_file": f"texts/{text_file.name}",
                    "chunks_file": f"chunks/{chunks_file.name}",
                    "toc_file": f"toc/{toc_file.name}",
                }
                records.append(record)
                all_chunks.extend(chunks)
                print(f"[doc {len(records)}] OK {metadata.get('doc_number')} chunks={len(chunks)} text={len(text)}")
            except Exception as exc:
                errors.append({"id": doc_id, "title": item.get("title"), "error": str(exc)})
                print(f"[doc ERR] {doc_id} -> {exc}", flush=True)
            time.sleep(args.delay)

        if args.limit and len(records) >= args.limit:
            break
        if len(records) + len(errors) >= total:
            break
        if not items:
            break
        page_number += 1

    chunk_quality = build_chunk_quality_report(all_chunks)
    manifest = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "https://vbpl.vn/van-ban/trung-uong",
        "filters": {
            "doc_types": ["Luật", "Bộ luật"],
            "effective_statuses": [
                "Còn hiệu lực",
                "Hết hiệu lực một phần",
                "Ngưng hiệu lực một phần",
            ],
        },
        "total_reported": total,
        "success": len(records),
        "failed": len(errors),
        "errors": errors,
        "chunk_quality": chunk_quality,
    }
    (output_dir / "documents.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (output_dir / "documents.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    with (output_dir / "all_chunks.jsonl").open("w", encoding="utf-8") as handle:
        for chunk in all_chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    write_csv(output_dir / "documents.csv", records)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if args.zip:
        archive = shutil.make_archive(str(output_dir), "zip", output_dir)
        manifest["zip_file"] = archive
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"ZIP: {archive}")

    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl VBPL central laws/codes by status, without downloading files."
    )
    parser.add_argument("--output", default="output/vbpl_laws_active_partial")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--zip", action="store_true")
    return parser.parse_args()


def main() -> int:
    manifest = crawl(parse_args())
    print(f"Done: success={manifest['success']}, failed={manifest['failed']}")
    return 0 if manifest["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
