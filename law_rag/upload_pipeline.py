from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
import shutil
import threading
from typing import Any, Literal

import faiss
import numpy as np

from .core.embedding_client import embed_texts
from .retrieval.retrieve_chunks import build_index_payload, build_searchable_text, save_index

LOW_CONFIDENCE_THRESHOLD = 0.7
WORKSPACE = Literal["private", "public"]
EmbeddingTarget = Literal["none", "api", "local", "both"]
_MANIFEST_LOCK = threading.Lock()


@dataclass
class UploadChunk:
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
    upload_id: str
    workspace: str
    ocr_confidence: float


ARTICLE_RE = re.compile(r"^Điều\s+(\d+[A-Za-z]?)\.\s*(.*)$", re.IGNORECASE)
CLAUSE_RE = re.compile(r"^(\d+)[.)]\s+")
POINT_RE = re.compile(r"^([a-zđ])[.)]\s+", re.IGNORECASE)
PART_RE = re.compile(r"^Phần\s+", re.IGNORECASE)
CHAPTER_RE = re.compile(r"^Chương\s+", re.IGNORECASE)
SECTION_RE = re.compile(r"^(Mục|Tiểu mục)\s+", re.IGNORECASE)


def quality_warning(confidence: float) -> str | None:
    if confidence >= LOW_CONFIDENCE_THRESHOLD:
        return None
    return (
        "Độ tin cậy OCR thấp. Nên tải lại file scan rõ hơn, chụp thẳng góc, đủ sáng, "
        "không bị mờ hoặc mất mép văn bản trước khi đưa vào tìm kiếm."
    )


def normalize_uploaded_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"(?<=\w)-\n(?=\w)", "", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def persist_reviewed_upload(
    *,
    upload_id: str,
    file_name: str,
    text: str,
    metadata: dict[str, Any],
    output_dir: Path,
    law_output_dir: Path,
    chunks_dir: Path,
    embedding_target: EmbeddingTarget = "none",
    max_chunk_chars: int = 1800,
) -> dict[str, Any]:
    workspace = "public" if metadata.get("workspace") == "public" else "private"
    confidence = float(metadata.get("confidence") or 0.0)
    normalized_text = normalize_uploaded_text(text)

    upload_db_dir = output_dir / "upload_documents" / workspace / upload_id
    upload_db_dir.mkdir(parents=True, exist_ok=True)
    if workspace == "private":
        (upload_db_dir / "embeddings" / "api").mkdir(parents=True, exist_ok=True)
        (upload_db_dir / "embeddings" / "local").mkdir(parents=True, exist_ok=True)
    else:
        (chunks_dir / "retrieval" / "vector-openai").mkdir(parents=True, exist_ok=True)
        (chunks_dir / "retrieval" / "vector-local").mkdir(parents=True, exist_ok=True)

    source_txt_name = f"{upload_id}_{_safe_stem(file_name)}.txt"
    source_json_name = f"{upload_id}_{_safe_stem(file_name)}.json"
    upload_txt_path = upload_db_dir / source_txt_name
    upload_json_path = upload_db_dir / source_json_name
    upload_txt_path.write_text(normalized_text, encoding="utf-8")

    chunks = build_upload_chunks(
        upload_id=upload_id,
        source_file=source_txt_name,
        file_name=file_name,
        text=normalized_text,
        workspace=workspace,
        confidence=confidence,
        max_chunk_chars=max_chunk_chars,
    )
    chunk_payload = [asdict(chunk) for chunk in chunks]
    (upload_db_dir / "chunks.json").write_text(json.dumps(chunk_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    chunks_jsonl_path = upload_db_dir / "chunks.jsonl"
    chunks_jsonl_path.write_text(
        "\n".join(json.dumps(chunk, ensure_ascii=False) for chunk in chunk_payload) + ("\n" if chunk_payload else ""),
        encoding="utf-8",
    )

    document_payload = {
        "id": upload_id,
        "fileName": file_name,
        "workspace": workspace,
        "documentType": metadata.get("documentType") or "other",
        "text": normalized_text,
        "confidence": confidence,
        "qualityWarning": quality_warning(confidence),
        "chunkCount": len(chunks),
        "sourceTextFile": source_txt_name,
        "sourceJsonFile": source_json_name,
    }
    upload_json_path.write_text(json.dumps(document_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    embedding_status: dict[str, Any] = {"requested": embedding_target, "api": None, "local": None}

    if workspace == "public":
        _persist_public_document(
            source_txt_name=source_txt_name,
            source_json_name=source_json_name,
            text=normalized_text,
            document_payload=document_payload,
            chunk_payload=chunk_payload,
            law_output_dir=law_output_dir,
            chunks_dir=chunks_dir,
        )
        _build_bm25(chunks_dir / "all_chunks.jsonl", chunks_dir / "retrieval" / "bm25_index.json")
        embedding_status = _build_requested_embeddings(
            embedding_target=embedding_target,
            chunks_path=chunks_dir / "all_chunks.jsonl",
            output_root=chunks_dir / "retrieval",
            public_index=True,
        )
    else:
        embedding_status = _build_requested_embeddings(
            embedding_target=embedding_target,
            chunks_path=chunks_jsonl_path,
            output_root=upload_db_dir / "embeddings",
            public_index=False,
        )

    manifest_path = output_dir / "upload_documents" / f"{workspace}_manifest.json"
    _upsert_manifest_item(
        manifest_path,
        {
            "id": upload_id,
            "fileName": file_name,
            "workspace": workspace,
            "documentType": document_payload["documentType"],
            "confidence": confidence,
            "qualityWarning": document_payload["qualityWarning"],
            "chunkCount": len(chunks),
            "embeddingStatus": embedding_status,
            "documentPath": str(upload_json_path.relative_to(output_dir)),
            "chunksPath": str((upload_db_dir / "chunks.json").relative_to(output_dir)),
        },
    )

    return {
        "workspace": workspace,
        "qualityWarning": document_payload["qualityWarning"],
        "chunkCount": len(chunks),
        "embeddingStatus": embedding_status,
        "documentStorePath": str(upload_json_path.relative_to(output_dir)),
        "chunkStorePath": str((upload_db_dir / "chunks.json").relative_to(output_dir)),
    }


def list_processed_uploads(output_dir: Path) -> list[dict[str, Any]]:
    documents_root = output_dir / "upload_documents"
    results: list[dict[str, Any]] = []
    for workspace in ("private", "public"):
        manifest_path = documents_root / f"{workspace}_manifest.json"
        if not manifest_path.exists():
            continue
        manifest = _read_json_file(manifest_path, {"items": []})
        for item in manifest.get("items", []):
            results.append({"workspace": workspace, **item})
    return sorted(results, key=lambda item: item.get("id", ""), reverse=True)


def delete_processed_upload(*, upload_id: str, output_dir: Path, law_output_dir: Path, chunks_dir: Path) -> bool:
    item = next((entry for entry in list_processed_uploads(output_dir) if entry.get("id") == upload_id), None)
    if not item:
        return False

    workspace = item.get("workspace") or "private"
    _remove_manifest_item(output_dir / "upload_documents" / f"{workspace}_manifest.json", upload_id)

    document_path_value = item.get("documentPath")
    document_path = output_dir / str(document_path_value) if document_path_value else None
    document_payload = json.loads(document_path.read_text(encoding="utf-8")) if document_path and document_path.exists() else {}
    source_txt_name = document_payload.get("sourceTextFile") or f"{upload_id}_{_safe_stem(str(item.get('fileName') or upload_id))}.txt"
    source_json_name = document_payload.get("sourceJsonFile") or f"{Path(source_txt_name).stem}.json"

    upload_dir = output_dir / "upload_documents" / str(workspace) / upload_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir)

    if workspace == "public":
        for path in [
            law_output_dir / source_txt_name,
            law_output_dir / source_json_name,
            chunks_dir / f"{Path(source_txt_name).stem}.chunks.json",
        ]:
            if path.exists():
                path.unlink()
        _remove_public_manifest_item(law_output_dir / "manifest.json", source_txt_name)
        _remove_chunks_from_jsonl(chunks_dir / "all_chunks.jsonl", source_txt_name)
        _remove_chunk_report_item(chunks_dir / "chunk_report.json", source_txt_name)
        _build_bm25(chunks_dir / "all_chunks.jsonl", chunks_dir / "retrieval" / "bm25_index.json")

    return True


def build_upload_chunks(
    *,
    upload_id: str,
    source_file: str,
    file_name: str,
    text: str,
    workspace: str,
    confidence: float,
    max_chunk_chars: int,
) -> list[UploadChunk]:
    lines = [line.strip() for line in _prepare_lines(text) if line.strip()]
    document_title = _detect_title(lines, file_name)
    sections = _split_legal_sections(lines)
    if not sections:
        sections = [{"heading": None, "article_number": None, "article_title": None, "lines": lines, "context": {}}]

    chunks: list[UploadChunk] = []
    for article_index, section in enumerate(sections, start=1):
        section_text = "\n".join(section["lines"]).strip()
        base = {
            "source_file": source_file,
            "mode": "upload_legal",
            "article_number": section.get("article_number"),
            "article_title": section.get("article_title"),
            "document_title": document_title,
            "part": section.get("context", {}).get("part"),
            "chapter": section.get("context", {}).get("chapter"),
            "section": section.get("context", {}).get("section"),
            "subsection": section.get("context", {}).get("subsection"),
            "target_law": None,
            "target_article": None,
            "quoted_inner_articles": [],
            "upload_id": upload_id,
            "workspace": workspace,
            "ocr_confidence": confidence,
        }
        if len(section_text) <= max_chunk_chars:
            chunks.append(
                UploadChunk(
                    chunk_id=f"{upload_id}:article:{article_index}",
                    clause_number=None,
                    point_number=None,
                    text=section_text,
                    text_length=len(section_text),
                    **base,
                )
            )
            continue

        for clause_index, clause in enumerate(_split_by_clause(section["lines"]), start=1):
            clause_text = "\n".join(clause["lines"]).strip()
            if section.get("heading") and not clause_text.startswith(section["heading"]):
                clause_text = f"{section['heading']}\n{clause_text}".strip()
            if len(clause_text) <= max_chunk_chars:
                chunks.append(
                    UploadChunk(
                        chunk_id=f"{upload_id}:article:{article_index}:clause:{clause_index}",
                        clause_number=clause.get("clause_number"),
                        point_number=None,
                        text=clause_text,
                        text_length=len(clause_text),
                        **base,
                    )
                )
                continue

            for point_index, point in enumerate(_split_by_size(clause_text, max_chunk_chars), start=1):
                chunks.append(
                    UploadChunk(
                        chunk_id=f"{upload_id}:article:{article_index}:clause:{clause_index}:part:{point_index}",
                        clause_number=clause.get("clause_number"),
                        point_number=None,
                        text=point,
                        text_length=len(point),
                        **base,
                    )
                )
    return chunks


def _persist_public_document(
    *,
    source_txt_name: str,
    source_json_name: str,
    text: str,
    document_payload: dict[str, Any],
    chunk_payload: list[dict[str, Any]],
    law_output_dir: Path,
    chunks_dir: Path,
) -> None:
    law_output_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir.mkdir(parents=True, exist_ok=True)
    (law_output_dir / source_txt_name).write_text(text, encoding="utf-8")
    (law_output_dir / source_json_name).write_text(json.dumps(document_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path = law_output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"items": []}
    items = [item for item in manifest.get("items", []) if item.get("text_file") != source_txt_name]
    items.insert(
        0,
        {
            "title": document_payload.get("fileName") or Path(source_txt_name).stem,
            "text_file": source_txt_name,
            "json_file": source_json_name,
            "source_url": "",
            "final_url": "",
            "fetched_at": None,
        },
    )
    manifest_path.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")

    (chunks_dir / f"{Path(source_txt_name).stem}.chunks.json").write_text(
        json.dumps(chunk_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    all_chunks_path = chunks_dir / "all_chunks.jsonl"
    existing = all_chunks_path.read_text(encoding="utf-8").splitlines() if all_chunks_path.exists() else []
    source_file = source_txt_name
    existing = [
        line for line in existing
        if not (line.strip() and json.loads(line).get("source_file") == source_file)
    ]
    existing.extend(json.dumps(chunk, ensure_ascii=False) for chunk in chunk_payload)
    all_chunks_path.write_text("\n".join(existing) + ("\n" if existing else ""), encoding="utf-8")

    report_path = chunks_dir / "chunk_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else []
    report = [item for item in report if item.get("file") != source_txt_name]
    report.append({"file": source_txt_name, "classification": {"suggested_mode": "upload_legal"}, "chunk_count": len(chunk_payload)})
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_requested_embeddings(
    *,
    embedding_target: EmbeddingTarget,
    chunks_path: Path,
    output_root: Path,
    public_index: bool,
) -> dict[str, Any]:
    status: dict[str, Any] = {"requested": embedding_target, "api": None, "local": None}
    if embedding_target in {"api", "both"}:
        target_dir = output_root / ("vector-openai" if public_index else "api")
        status["api"] = _try_build_embedding_index(
            chunks_path=chunks_path,
            output_dir=target_dir,
            provider="openai",
            model=_env("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        )
    if embedding_target in {"local", "both"}:
        target_dir = output_root / ("vector-local" if public_index else "local")
        status["local"] = _try_build_embedding_index(
            chunks_path=chunks_path,
            output_dir=target_dir,
            provider=_env("LOCAL_EMBEDDING_PROVIDER", "sentence-transformers"),
            model=_env("LOCAL_EMBEDDING_MODEL", "intfloat/multilingual-e5-base"),
        )
    return status


def _try_build_embedding_index(*, chunks_path: Path, output_dir: Path, provider: str, model: str) -> dict[str, Any]:
    try:
        return _build_embedding_index(chunks_path=chunks_path, output_dir=output_dir, provider=provider, model=model)
    except Exception as exc:
        output_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "built": False,
            "provider": provider,
            "model": model,
            "error": str(exc),
        }
        (output_dir / "vector_manifest.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8")
        return failure


def _build_embedding_index(*, chunks_path: Path, output_dir: Path, provider: str, model: str) -> dict[str, Any]:
    chunks = [json.loads(line) for line in chunks_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not chunks:
        raise RuntimeError("Không có chunk để embedding.")

    output_dir.mkdir(parents=True, exist_ok=True)
    texts = [build_searchable_text(chunk) for chunk in chunks]
    vectors = embed_texts(texts, model=model, provider=provider)
    matrix = np.array(vectors, dtype="float32")
    faiss.normalize_L2(matrix)
    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)

    metadata = [
        {
            "chunk_id": chunk["chunk_id"],
            "source_file": chunk["source_file"],
            "mode": chunk["mode"],
            "article_number": chunk.get("article_number"),
            "clause_number": chunk.get("clause_number"),
            "point_number": chunk.get("point_number"),
            "document_title": chunk.get("document_title"),
            "chapter": chunk.get("chapter"),
            "part": chunk.get("part"),
            "target_article": chunk.get("target_article"),
            "text": chunk["text"],
            "searchable_text": searchable_text,
            "workspace": chunk.get("workspace"),
            "upload_id": chunk.get("upload_id"),
        }
        for chunk, searchable_text in zip(chunks, texts)
    ]

    faiss.write_index(index, str(output_dir / "faiss.index"))
    (output_dir / "vector_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "built": True,
        "provider": provider,
        "embedding_provider": provider,
        "model": model,
        "embedding_model": model,
        "dimension": int(matrix.shape[1]),
        "chunk_count": len(chunks),
        "chunks_path": str(chunks_path),
        "index_path": str(output_dir / "faiss.index"),
        "metadata_path": str(output_dir / "vector_metadata.json"),
    }
    (output_dir / "vector_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _build_bm25(chunks_path: Path, output_path: Path) -> None:
    if not chunks_path.exists():
        return
    save_index(build_index_payload(chunks_path), output_path)


def _env(name: str, fallback: str) -> str:
    import os

    return os.getenv(name) or fallback


def _read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        try:
            payload, _end = decoder.raw_decode(raw)
        except json.JSONDecodeError:
            return default
        _write_json_file(path, payload)
        return payload


def _write_json_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _upsert_manifest_item(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _MANIFEST_LOCK:
        manifest = _read_json_file(path, {"items": []}) if path.exists() else {"items": []}
        items = [existing for existing in manifest.get("items", []) if existing.get("id") != item["id"]]
        items.insert(0, item)
        _write_json_file(path, {"items": items})


def _remove_manifest_item(path: Path, upload_id: str) -> None:
    if not path.exists():
        return
    with _MANIFEST_LOCK:
        manifest = _read_json_file(path, {"items": []})
        items = [item for item in manifest.get("items", []) if item.get("id") != upload_id]
        _write_json_file(path, {"items": items})


def _remove_public_manifest_item(path: Path, source_file: str) -> None:
    if not path.exists():
        return
    manifest = _read_json_file(path, {"items": []})
    items = [item for item in manifest.get("items", []) if item.get("text_file") != source_file]
    _write_json_file(path, {"items": items})


def _remove_chunks_from_jsonl(path: Path, source_file: str) -> None:
    if not path.exists():
        return
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        if json.loads(line).get("source_file") == source_file:
            continue
        lines.append(line)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _remove_chunk_report_item(path: Path, source_file: str) -> None:
    if not path.exists():
        return
    report = json.loads(path.read_text(encoding="utf-8"))
    report = [item for item in report if item.get("file") != source_file]
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _prepare_lines(text: str) -> list[str]:
    text = re.sub(r"(?<=[.;:])\s+(?=\d+[.)]\s+)", "\n", text)
    text = re.sub(r"(?<=[;:])\s+(?=[a-zđ][.)]\s+)", "\n", text, flags=re.IGNORECASE)
    return text.splitlines()


def _split_legal_sections(lines: list[str]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    context: dict[str, str | None] = {"part": None, "chapter": None, "section": None, "subsection": None}

    for line in lines:
        if PART_RE.match(line):
            context["part"] = line
            continue
        if CHAPTER_RE.match(line):
            context["chapter"] = line
            continue
        if SECTION_RE.match(line):
            key = "subsection" if line.casefold().startswith("tiểu mục") else "section"
            context[key] = line
            continue

        article_match = ARTICLE_RE.match(line)
        if article_match:
            current = {
                "heading": line,
                "article_number": article_match.group(1),
                "article_title": article_match.group(2).strip() or None,
                "lines": [line],
                "context": context.copy(),
            }
            sections.append(current)
            continue

        if current is not None:
            current["lines"].append(line)

    return sections


def _split_by_clause(lines: list[str]) -> list[dict[str, Any]]:
    clauses: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in lines[1:] if lines and ARTICLE_RE.match(lines[0]) else lines:
        match = CLAUSE_RE.match(line)
        if match:
            current = {"clause_number": match.group(1), "lines": [line]}
            clauses.append(current)
            continue
        if current is None:
            current = {"clause_number": None, "lines": []}
            clauses.append(current)
        current["lines"].append(line)
    return clauses or [{"clause_number": None, "lines": lines}]


def _split_by_size(text: str, max_chars: int) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in text.split("\n") if paragraph.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 1 > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n{paragraph}".strip()
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]


def _detect_title(lines: list[str], file_name: str) -> str:
    for line in lines[:20]:
        if len(line) >= 8 and line.upper() == line and any(char.isalpha() for char in line):
            return line.title()
    return Path(file_name).stem.replace("-", " ").replace("_", " ").title()


def _safe_stem(file_name: str) -> str:
    stem = Path(file_name).stem
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", stem)
    return stem.strip(".-") or "document"
