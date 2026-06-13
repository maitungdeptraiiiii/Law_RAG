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

from law_rag.legal_chunking import DEFAULT_MAX_CHUNK_CHARS, build_chunk_quality_report, chunk_blocks_by_articles


API_BASE = "https://vbpl-bientap-gateway.moj.gov.vn/api"
DOC_ALL_ENDPOINT = f"{API_BASE}/qtdc/public/doc/all"
DOC_DETAIL_ENDPOINT = f"{API_BASE}/qtdc/public/doc"
COMBOBOX_ENDPOINT = f"{API_BASE}/qtdc/public/doc/combobox"

DOC_TYPE_LAW = "11025e19-2dd6-4165-85ad-ab6241186a1a"
DOC_TYPE_CODE = "404b68a7-8e71-4ee5-a6c0-07e59f35f824"
DOC_TYPE_DECREE = "0d08b84c-7de7-4800-8760-2a68265e7890"
DOC_TYPE_CIRCULAR = "178c63a9-73ff-4fd4-9d91-18d690520090"
DOC_TYPE_DECISION = "0a5362e8-cdca-436e-96cd-979598df3b16"
STATUS_EFFECTIVE = "1419f6be-4a15-44a7-97ac-ea042770a514"
STATUS_PARTLY_EXPIRED = "9c20e89d-e048-4f3a-b6c2-df87fe0b1ada"
STATUS_PARTLY_SUSPENDED = "d1189072-7aed-44d8-bcaf-d89409adcded"

DOC_TYPE_IDS = {
    "Bộ luật": DOC_TYPE_CODE,
    "Luật": DOC_TYPE_LAW,
    "Nghị định": DOC_TYPE_DECREE,
    "Thông tư": DOC_TYPE_CIRCULAR,
    "Quyết định": DOC_TYPE_DECISION,
}
EFFECTIVE_STATUS_IDS = {
    "Còn hiệu lực": STATUS_EFFECTIVE,
    "Hết hiệu lực một phần": STATUS_PARTLY_EXPIRED,
    "Ngưng hiệu lực một phần": STATUS_PARTLY_SUSPENDED,
}
DEFAULT_DOC_TYPES = ["Nghị định", "Thông tư", "Quyết định"]
DEFAULT_EFFECTIVE_STATUSES = ["Còn hiệu lực", "Hết hiệu lực một phần", "Ngưng hiệu lực một phần"]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
MAX_CHUNK_CHARS = DEFAULT_MAX_CHUNK_CHARS

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


def slugify_vietnamese(value: str, fallback: str) -> str:
    replacements = {
        "à": "a",
        "á": "a",
        "ạ": "a",
        "ả": "a",
        "ã": "a",
        "â": "a",
        "ầ": "a",
        "ấ": "a",
        "ậ": "a",
        "ẩ": "a",
        "ẫ": "a",
        "ă": "a",
        "ằ": "a",
        "ắ": "a",
        "ặ": "a",
        "ẳ": "a",
        "ẵ": "a",
        "è": "e",
        "é": "e",
        "ẹ": "e",
        "ẻ": "e",
        "ẽ": "e",
        "ê": "e",
        "ề": "e",
        "ế": "e",
        "ệ": "e",
        "ể": "e",
        "ễ": "e",
        "ì": "i",
        "í": "i",
        "ị": "i",
        "ỉ": "i",
        "ĩ": "i",
        "ò": "o",
        "ó": "o",
        "ọ": "o",
        "ỏ": "o",
        "õ": "o",
        "ô": "o",
        "ồ": "o",
        "ố": "o",
        "ộ": "o",
        "ổ": "o",
        "ỗ": "o",
        "ơ": "o",
        "ờ": "o",
        "ớ": "o",
        "ợ": "o",
        "ở": "o",
        "ỡ": "o",
        "ù": "u",
        "ú": "u",
        "ụ": "u",
        "ủ": "u",
        "ũ": "u",
        "ư": "u",
        "ừ": "u",
        "ứ": "u",
        "ự": "u",
        "ử": "u",
        "ữ": "u",
        "ỳ": "y",
        "ý": "y",
        "ỵ": "y",
        "ỷ": "y",
        "ỹ": "y",
        "đ": "d",
    }
    ascii_value = "".join(replacements.get(char.lower(), char.lower()) for char in value)
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug or fallback


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


def fetch_list(
    session: requests.Session,
    page_number: int,
    page_size: int,
    timeout: int,
    *,
    doc_type_ids: list[str],
    effective_status_ids: list[str],
) -> dict:
    payload = {
        "pageNumber": page_number,
        "pageSize": page_size,
        "docType": doc_type_ids,
        "effStatus": effective_status_ids,
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


def fetch_combobox(session: requests.Session, group_code: str, timeout: int) -> list[dict]:
    response = session.get(
        COMBOBOX_ENDPOINT,
        params={"groupCode": group_code, "includeInactive": "true"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success", True):
        raise RuntimeError(payload)
    data = payload.get("data") or {}
    return data.get("items") or []


def resolve_category_ids(
    session: requests.Session,
    *,
    names: list[str],
    group_code: str,
    fallback: dict[str, str],
    timeout: int,
) -> dict[str, str]:
    resolved = dict(fallback)
    try:
        for item in fetch_combobox(session, group_code, timeout):
            name = item.get("name")
            item_id = item.get("id")
            if name and item_id:
                resolved[name] = item_id
    except Exception as exc:
        print(f"[warn] cannot fetch {group_code} combobox, using built-in ids: {exc}", flush=True)

    missing = [name for name in names if name not in resolved]
    if missing:
        raise ValueError(f"Unknown {group_code}: {', '.join(missing)}")
    return {name: resolved[name] for name in names}


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


def metadata_text(metadata: dict) -> str:
    fields = [
        ("Số hiệu", metadata.get("doc_number")),
        ("Loại văn bản", metadata.get("doc_type")),
        ("Ngành", " | ".join(metadata.get("majors") or [])),
        ("Ngày ban hành", metadata.get("issue_date")),
        ("Lĩnh vực", " | ".join(metadata.get("fields") or [])),
        ("Ngày có hiệu lực", metadata.get("effective_from")),
        ("Tình trạng hiệu lực", metadata.get("effective_status")),
        ("Ngày hết hiệu lực", metadata.get("effective_to") or "--"),
        ("Cơ quan ban hành", metadata.get("agency_name") or metadata.get("organization")),
        ("Chức danh", metadata.get("signer_title")),
        ("Người ký", metadata.get("signer")),
        ("Nguồn", metadata.get("source_url")),
    ]
    lines = ["THUỘC TÍNH VĂN BẢN"]
    for label, value in fields:
        if value is None:
            value = ""
        lines.append(f"{label}: {value}")
    return "\n".join(lines)


def enrich_chunks(chunks: list[dict], metadata: dict, *, text_file: str, chunks_file: str) -> list[dict]:
    property_text = metadata_text(metadata)
    for chunk in chunks:
        chunk.update(
            {
                "doc_type": metadata.get("doc_type"),
                "doc_type_code": metadata.get("doc_type_code"),
                "effective_status": metadata.get("effective_status"),
                "effective_status_code": metadata.get("effective_status_code"),
                "agency_name": metadata.get("agency_name"),
                "issue_date": metadata.get("issue_date"),
                "effective_from": metadata.get("effective_from"),
                "effective_to": metadata.get("effective_to"),
                "majors": metadata.get("majors") or [],
                "fields": metadata.get("fields") or [],
                "signer_title": metadata.get("signer_title"),
                "signer": metadata.get("signer"),
                "source_url": metadata.get("source_url"),
                "metadata_text": property_text,
                "source_file": text_file,
                "text_file": text_file,
                "chunks_file": chunks_file,
            }
        )
    return chunks


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
        "organization",
        "public_date",
        "updated_date",
        "source_url",
        "text_length",
        "chunk_count",
        "toc_count",
        "chunks_file",
        "text_file",
        "html_file",
        "toc_file",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = {field: record.get(field, "") for field in fields}
            row["majors"] = " | ".join(record.get("majors") or [])
            row["fields"] = " | ".join(record.get("fields") or [])
            writer.writerow(row)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def append_jsonl(path: Path, records: list[dict]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def record_from_chunk_file(output_dir: Path, chunks_file: Path, chunks: list[dict]) -> dict | None:
    if not chunks:
        return None
    first = chunks[0]
    vbpl_id = first.get("vbpl_id")
    if not vbpl_id:
        return None
    text_file = first.get("text_file")
    text_length = 0
    if isinstance(text_file, str):
        text_path = output_dir / text_file
        if text_path.exists():
            text_length = len(text_path.read_text(encoding="utf-8"))
    return {
        "vbpl_id": str(vbpl_id),
        "title": first.get("document_title"),
        "doc_number": first.get("doc_number"),
        "doc_type": first.get("doc_type"),
        "doc_type_code": first.get("doc_type_code"),
        "agency_name": first.get("agency_name"),
        "issue_date": first.get("issue_date"),
        "effective_from": first.get("effective_from"),
        "effective_to": first.get("effective_to"),
        "effective_status": first.get("effective_status"),
        "effective_status_code": first.get("effective_status_code"),
        "majors": first.get("majors") or [],
        "fields": first.get("fields") or [],
        "signer_title": first.get("signer_title"),
        "signer": first.get("signer"),
        "source_url": first.get("source_url"),
        "text_length": text_length,
        "chunk_count": len(chunks),
        "chunks_file": chunks_file.relative_to(output_dir).as_posix(),
        "text_file": text_file,
    }


def load_resume_state(output_dir: Path) -> tuple[list[dict], list[dict], set[str]]:
    documents_path = output_dir / "documents.jsonl"
    chunks_path = output_dir / "all_chunks.jsonl"
    records = load_jsonl(documents_path)
    chunks = load_jsonl(chunks_path)
    seen_ids = {str(record["vbpl_id"]) for record in records if record.get("vbpl_id")}

    seen_ids.update(str(chunk["vbpl_id"]) for chunk in chunks if chunk.get("vbpl_id"))
    chunk_files = sorted(output_dir.glob("**/chunks/*.chunks.json"))
    for chunk_file in chunk_files:
        try:
            file_chunks = json.loads(chunk_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(file_chunks, list):
            continue
        chunks.extend(file_chunks)
        record = record_from_chunk_file(output_dir, chunk_file, file_chunks)
        if record and record["vbpl_id"] not in seen_ids:
            records.append(record)
            seen_ids.add(record["vbpl_id"])

    deduped_records: list[dict] = []
    deduped_ids: set[str] = set()
    for record in records:
        vbpl_id = record.get("vbpl_id")
        if not vbpl_id or str(vbpl_id) in deduped_ids:
            continue
        deduped_records.append(record)
        deduped_ids.add(str(vbpl_id))

    deduped_chunks: list[dict] = []
    deduped_chunk_ids: set[str] = set()
    for chunk in chunks:
        chunk_id = chunk.get("chunk_id")
        if not chunk_id or str(chunk_id) in deduped_chunk_ids:
            continue
        deduped_chunks.append(chunk)
        deduped_chunk_ids.add(str(chunk_id))

    return deduped_records, deduped_chunks, deduped_ids


def crawl(args: argparse.Namespace) -> dict:
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    session = create_session()
    doc_type_names = args.doc_types or DEFAULT_DOC_TYPES
    effective_status_names = args.effective_statuses or DEFAULT_EFFECTIVE_STATUSES
    doc_type_map = resolve_category_ids(
        session,
        names=doc_type_names,
        group_code="LoaiVanBan",
        fallback=DOC_TYPE_IDS,
        timeout=args.timeout,
    )
    effective_status_map = resolve_category_ids(
        session,
        names=effective_status_names,
        group_code="TrangThaiHieuLuc",
        fallback=EFFECTIVE_STATUS_IDS,
        timeout=args.timeout,
    )
    doc_type_ids = list(doc_type_map.values())
    effective_status_ids = list(effective_status_map.values())

    def doc_dirs(doc_type: str | None) -> tuple[Path, Path, Path, Path, str]:
        doc_type_slug = slugify_vietnamese(doc_type or "khong-xac-dinh", "khong-xac-dinh")
        base_dir = output_dir / doc_type_slug if args.split_by_doc_type else output_dir
        html_dir = base_dir / "html"
        text_dir = base_dir / "texts"
        chunks_dir = base_dir / "chunks"
        tree_dir = base_dir / "toc"
        for directory in [html_dir, text_dir, chunks_dir, tree_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        return html_dir, text_dir, chunks_dir, tree_dir, doc_type_slug

    if args.resume:
        records, all_chunks, crawled_ids = load_resume_state(output_dir)
        print(
            f"[resume] loaded {len(crawled_ids)} documents and {len(all_chunks)} chunks from {output_dir}",
            flush=True,
        )
    else:
        records = []
        all_chunks = []
        crawled_ids = set()

    errors: list[dict] = []
    page_number = 1
    total: int | None = None

    while True:
        page = fetch_list(
            session,
            page_number,
            args.page_size,
            args.timeout,
            doc_type_ids=doc_type_ids,
            effective_status_ids=effective_status_ids,
        )
        total = total or page["total"]
        items = page.get("items", [])
        print(f"[list page {page_number}] fetched {len(items)} / total {total}", flush=True)

        for item in items:
            if args.limit and len(records) >= args.limit:
                break
            doc_id = str(item["id"])
            if doc_id in crawled_ids:
                continue
            try:
                detail = fetch_detail(session, doc_id, args.timeout)
                metadata = metadata_from_detail(detail)
                html_dir, text_dir, chunks_dir, tree_dir, doc_type_slug = doc_dirs(metadata.get("doc_type"))
                stem = sanitize_filename(
                    f"{metadata.get('doc_number') or doc_id}_{metadata.get('title') or ''}",
                    fallback=f"vbpl_{doc_id}",
                )
                html = (detail.get("documentContent") or {}).get("content") or ""
                text = html_to_text(html)
                blocks = html_blocks(html)
                toc = flatten_tree(detail.get("provisionTree"))
                chunks = chunk_blocks_by_articles(blocks, metadata, max_chars=MAX_CHUNK_CHARS)

                html_file = html_dir / f"{stem}.html"
                text_file = text_dir / f"{stem}.txt"
                chunks_file = chunks_dir / f"{stem}.chunks.json"
                toc_file = tree_dir / f"{stem}.toc.json"
                html_rel = html_file.relative_to(output_dir).as_posix()
                text_rel = text_file.relative_to(output_dir).as_posix()
                chunks_rel = chunks_file.relative_to(output_dir).as_posix()
                toc_rel = toc_file.relative_to(output_dir).as_posix()
                chunks = enrich_chunks(chunks, metadata, text_file=text_rel, chunks_file=chunks_rel)
                full_text = f"{metadata_text(metadata)}\n\nNỘI DUNG VĂN BẢN\n{text}".strip()

                html_file.write_text(html, encoding="utf-8")
                text_file.write_text(full_text, encoding="utf-8")
                chunks_file.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
                toc_file.write_text(json.dumps(toc, ensure_ascii=False, indent=2), encoding="utf-8")

                record = {
                    **metadata,
                    "doc_type_folder": doc_type_slug,
                    "text_length": len(full_text),
                    "chunk_count": len(chunks),
                    "toc_count": len(toc),
                    "html_file": html_rel,
                    "text_file": text_rel,
                    "chunks_file": chunks_rel,
                    "toc_file": toc_rel,
                }
                records.append(record)
                all_chunks.extend(chunks)
                crawled_ids.add(doc_id)
                if args.checkpoint:
                    append_jsonl(output_dir / "documents.jsonl", [record])
                    append_jsonl(output_dir / "all_chunks.jsonl", chunks)
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
        "source": "https://vbpl.vn/",
        "filters": {
            "doc_types": doc_type_names,
            "doc_type_ids": doc_type_map,
            "effective_statuses": effective_status_names,
            "effective_status_ids": effective_status_map,
            "split_by_doc_type": args.split_by_doc_type,
            "resume": args.resume,
            "checkpoint": args.checkpoint,
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
        description="Crawl VBPL documents by type and effective status, without downloading files."
    )
    parser.add_argument("--output", default="output/vbpl_business_guidance_mvp")
    parser.add_argument(
        "--doc-types",
        nargs="+",
        default=DEFAULT_DOC_TYPES,
        help="VBPL document type names to crawl. Default: Nghị định, Thông tư, Quyết định.",
    )
    parser.add_argument(
        "--effective-statuses",
        nargs="+",
        default=DEFAULT_EFFECTIVE_STATUSES,
        help="Effective status names to crawl.",
    )
    parser.add_argument(
        "--split-by-doc-type",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Store html/text/chunks/toc under one folder per document type.",
    )
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip documents already present in documents.jsonl/all_chunks.jsonl or existing chunk files.",
    )
    parser.add_argument(
        "--checkpoint",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Append documents.jsonl and all_chunks.jsonl after each successfully crawled document.",
    )
    parser.add_argument("--zip", action="store_true")
    return parser.parse_args()


def main() -> int:
    manifest = crawl(parse_args())
    print(f"Done: success={manifest['success']}, failed={manifest['failed']}")
    return 0 if manifest["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
