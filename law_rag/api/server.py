from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import APIError, AuthenticationError
from pydantic import BaseModel, Field

from ..app.ask_law import DEFAULT_CHAT_MODEL, DEFAULT_MEMORY_MODEL, answer_question
from ..core.conversation_state import append_history, load_session, save_session, utc_now_iso
from ..core.env_loader import load_project_env
from ..retrieval.build_vector_index import DEFAULT_EMBEDDING_MODEL
from ..retrieval.hybrid_retrieve import DEFAULT_QUERY_REWRITE_MODEL, build_retrieval_queries, hybrid_search


load_project_env()

ROOT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT_DIR / "output"
LAW_OUTPUT_DIR = OUTPUT_DIR / "laws"
CHUNKS_DIR = OUTPUT_DIR / "chunks"
SESSIONS_DIR = OUTPUT_DIR / "sessions"
UPLOADS_DIR = OUTPUT_DIR / "uploads"
RETRIEVAL_DIR = CHUNKS_DIR / "retrieval"
VECTOR_DIR = RETRIEVAL_DIR / "vector"
CHUNKS_PATH = CHUNKS_DIR / "all_chunks.jsonl"
BM25_INDEX_PATH = RETRIEVAL_DIR / "bm25_index.json"
FRAMEWORK_REPORT_PATH = OUTPUT_DIR / "chunk_framework_report.json"
CHUNK_REPORT_PATH = CHUNKS_DIR / "chunk_report.json"
JOBS_FILE = OUTPUT_DIR / "api_jobs.json"

DEFAULT_RETRIEVAL_SETTINGS = {
    "mode": "hybrid",
    "vector_backend": "faiss",
    "top_k": 5,
    "query_rewrite": True,
}

DOCUMENT_TYPE_MAP = {
    "bo_luat": "law",
    "luat": "law",
    "nghi_dinh": "decree",
    "thong_tu": "circular",
    "nghi_quyet": "resolution",
    "quyet_dinh": "decision",
}

ISSUING_AUTHORITY_MAP = {
    "law": "Quốc hội",
    "decree": "Chính phủ",
    "circular": "Bộ ngành",
    "resolution": "Quốc hội",
    "decision": "Cơ quan nhà nước",
    "guideline": "Cơ quan nhà nước",
    "other": "Cơ quan nhà nước",
}


class RetrievalSettingsPayload(BaseModel):
    mode: Literal["hybrid", "vector", "bm25"] = "hybrid"
    vectorBackend: Literal["faiss", "atlas"] = "faiss"
    topK: int = Field(default=5, ge=1, le=20)
    queryRewrite: bool = True
    model: str | None = None


class AskQuestionPayload(BaseModel):
    question: str = Field(min_length=1)
    sessionId: str | None = None
    settings: RetrievalSettingsPayload | None = None


class DebugQueryPayload(BaseModel):
    query: str = Field(min_length=1)
    settings: RetrievalSettingsPayload | None = None


class UpdateSessionPayload(BaseModel):
    title: str | None = None
    pinned: bool | None = None


app = FastAPI(title="Law RAG API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def now_utc() -> datetime:
    return datetime.now(UTC)


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_json_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_settings(settings: RetrievalSettingsPayload | None) -> dict[str, Any]:
    if settings is None:
        return dict(DEFAULT_RETRIEVAL_SETTINGS)
    return {
        "mode": settings.mode,
        "vector_backend": settings.vectorBackend,
        "top_k": settings.topK,
        "query_rewrite": settings.queryRewrite,
        "model": settings.model,
    }


def session_title_from_history(history: list[dict[str, Any]]) -> str:
    for item in history:
        if item.get("role") == "user":
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            return content[:60] + ("..." if len(content) > 60 else "")
    return "Cuộc hội thoại mới"


def parse_iso_datetime(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return fallback


def serialize_datetime(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return value


def slug_to_title(slug: str) -> str:
    text = re.sub(r"^[0-9]+_", "", slug)
    text = text.replace("-", " ").replace("_", " ").strip()
    return re.sub(r"\s+", " ", text).title()


def detect_document_type(identifier: str) -> str:
    normalized = re.sub(r"^[0-9]+[_-]*", "", identifier.casefold().replace("-", "_"))
    for prefix, document_type in DOCUMENT_TYPE_MAP.items():
        if normalized.startswith(prefix):
            return document_type
    return "other"


def extract_document_number(text: str) -> str:
    match = re.search(r"Luật số:\s*([^\n]+)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"số[:\s]+([^\n]+)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def extract_issued_date(text: str) -> str | None:
    match = re.search(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", text, flags=re.IGNORECASE)
    if not match:
        return None
    day, month, year = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return f"{year:04d}-{month:02d}-{day:02d}"


@lru_cache(maxsize=1)
def load_law_manifest() -> dict[str, Any]:
    manifest_path = LAW_OUTPUT_DIR / "manifest.json"
    payload = safe_json_load(manifest_path, {"items": []})
    items = payload.get("items", []) if isinstance(payload, dict) else []
    by_text_file: dict[str, dict[str, Any]] = {}
    by_json_file: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        text_file = item.get("text_file")
        json_file = item.get("json_file")
        if text_file:
            by_text_file[str(text_file)] = item
        if json_file:
            by_json_file[str(json_file)] = item
    return {"items": items, "by_text_file": by_text_file, "by_json_file": by_json_file}


@lru_cache(maxsize=1)
def load_chunk_report_map() -> dict[str, int]:
    payload = safe_json_load(CHUNK_REPORT_PATH, [])
    results: dict[str, int] = {}
    if not isinstance(payload, list):
        return results
    for item in payload:
        if not isinstance(item, dict):
            continue
        file_name = item.get("file")
        chunk_count = item.get("chunk_count")
        if isinstance(file_name, str) and isinstance(chunk_count, int):
            results[file_name] = chunk_count
    return results


def load_law_payload(json_file: str) -> dict[str, Any]:
    path = LAW_OUTPUT_DIR / json_file
    return safe_json_load(path, {})


@lru_cache(maxsize=1)
def load_documents_cache() -> list[dict[str, Any]]:
    manifest = load_law_manifest()
    chunk_counts = load_chunk_report_map()
    bm25_built = BM25_INDEX_PATH.exists()
    vector_built = (VECTOR_DIR / "faiss.index").exists() or (VECTOR_DIR / "atlas_manifest.json").exists()
    documents: list[dict[str, Any]] = []

    for item in manifest["items"]:
        json_file = item.get("json_file")
        text_file = item.get("text_file")
        if not isinstance(json_file, str) or not isinstance(text_file, str):
            continue

        law_payload = load_law_payload(json_file)
        source_title = str(law_payload.get("title") or "").strip()
        text_body = str(law_payload.get("text") or "")
        slug = Path(text_file).stem
        chunk_count = int(chunk_counts.get(text_file, 0))
        document_type = detect_document_type(slug)
        issued_date = extract_issued_date(text_body) or ""
        title = source_title or slug_to_title(slug)
        document_number = extract_document_number(text_body) or slug
        status = "crawled"
        if chunk_count > 0:
            status = "indexed" if (bm25_built or vector_built) else "chunked"

        fetched_at = law_payload.get("fetched_at")
        updated_at = serialize_datetime(fetched_at) or utc_now_iso()
        documents.append(
            {
                "id": slug,
                "title": title,
                "documentNumber": document_number,
                "documentType": document_type,
                "issuedDate": issued_date,
                "effectiveDate": None,
                "issuingAuthority": ISSUING_AUTHORITY_MAP.get(document_type, "Cơ quan nhà nước"),
                "sourceUrl": law_payload.get("final_url") or law_payload.get("source_url") or "",
                "status": status,
                "chunkCount": chunk_count,
                "crawledAt": updated_at,
                "lastUpdated": updated_at,
                "previewText": text_body[:500],
            }
        )

    documents.sort(key=lambda item: item["id"])
    return documents


def map_retrieved_source(item: dict[str, Any]) -> dict[str, Any]:
    manifest = load_law_manifest()
    text_file = item.get("source_file")
    manifest_item = manifest["by_text_file"].get(str(text_file), {}) if text_file else {}
    chunk_sources = item.get("sources") or []
    retrieval_origin = "hybrid" if len(chunk_sources) > 1 else (chunk_sources[0] if chunk_sources else "hybrid")
    return {
        "id": item.get("chunk_id") or str(uuid.uuid4()),
        "documentId": Path(str(text_file)).stem if text_file else str(item.get("chunk_id") or "unknown"),
        "documentTitle": item.get("document_title") or slug_to_title(Path(str(text_file)).stem if text_file else "document"),
        "articleNumber": item.get("article_number"),
        "clauseNumber": item.get("clause_number"),
        "targetArticle": item.get("target_article"),
        "chunkText": item.get("text") or item.get("preview") or "",
        "relevanceScore": float(item.get("rrf_score") or item.get("score") or 0.0),
        "retrievalOrigin": retrieval_origin,
        "sourceUrl": manifest_item.get("final_url") or manifest_item.get("source_url"),
        "issuedDate": None,
        "documentType": detect_document_type(Path(str(text_file)).stem if text_file else ""),
    }


def session_message_to_api(message: dict[str, Any], fallback_time: datetime) -> dict[str, Any]:
    timestamp = parse_iso_datetime(message.get("timestamp"), fallback_time)
    payload = {
        "id": message.get("id") or f"msg-{uuid.uuid4().hex[:12]}",
        "role": message.get("role") or "assistant",
        "content": message.get("content") or "",
        "timestamp": serialize_datetime(timestamp),
    }
    sources = message.get("sources")
    if isinstance(sources, list) and sources:
        payload["sources"] = sources
    metadata = message.get("metadata")
    if isinstance(metadata, dict) and metadata:
        payload["metadata"] = metadata
    return payload


def load_session_documents() -> list[dict[str, Any]]:
    ensure_directory(SESSIONS_DIR)
    sessions: list[dict[str, Any]] = []
    for path in SESSIONS_DIR.glob("*.json"):
        payload = safe_json_load(path, {})
        history = payload.get("history", []) if isinstance(payload.get("history"), list) else []
        if not history:
            continue
        updated_at = parse_iso_datetime(payload.get("updated_at"), datetime.fromtimestamp(path.stat().st_mtime, tz=UTC))
        created_at = datetime.fromtimestamp(path.stat().st_ctime, tz=UTC)
        custom_title = str(payload.get("title") or "").strip()
        sessions.append(
            {
                "id": payload.get("session_id") or path.stem,
                "title": custom_title or session_title_from_history(history),
                "createdAt": serialize_datetime(created_at),
                "updatedAt": serialize_datetime(updated_at),
                "messageCount": len(history),
                "preview": next((str(item.get("content", "")).strip() for item in history if item.get("role") == "user"), ""),
                "archived": bool(payload.get("archived", False)),
                "pinned": bool(payload.get("pinned", False)),
            }
        )
    sessions.sort(key=lambda item: (bool(item.get("pinned")), str(item.get("updatedAt") or "")), reverse=True)
    return sessions


def load_jobs() -> list[dict[str, Any]]:
    ensure_directory(OUTPUT_DIR)
    payload = safe_json_load(JOBS_FILE, [])
    if not isinstance(payload, list):
        return []
    return payload


def save_jobs(jobs: list[dict[str, Any]]) -> None:
    ensure_directory(OUTPUT_DIR)
    JOBS_FILE.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")


def upsert_job(job: dict[str, Any]) -> None:
    jobs = load_jobs()
    for index, item in enumerate(jobs):
        if item.get("id") == job.get("id"):
            jobs[index] = job
            save_jobs(jobs)
            return
    jobs.insert(0, job)
    save_jobs(jobs)


def create_job(job_type: str) -> dict[str, Any]:
    job = {
        "id": f"job-{uuid.uuid4().hex[:12]}",
        "type": job_type,
        "status": "running",
        "progress": 5,
        "startedAt": utc_now_iso(),
        "completedAt": None,
        "error": None,
        "metadata": {},
    }
    upsert_job(job)
    return job


def run_pipeline_job(job: dict[str, Any], commands: list[list[str]]) -> None:
    try:
        total = max(len(commands), 1)
        for index, command in enumerate(commands, start=1):
            subprocess.run(command, cwd=ROOT_DIR, check=True, capture_output=True, text=True)
            job["progress"] = min(95, int(index / total * 100))
            upsert_job(job)
        job["status"] = "completed"
        job["progress"] = 100
        job["completedAt"] = utc_now_iso()
    except subprocess.CalledProcessError as exc:
        job["status"] = "failed"
        job["error"] = (exc.stderr or exc.stdout or str(exc)).strip()[:2000]
        job["completedAt"] = utc_now_iso()
    upsert_job(job)
    load_documents_cache.cache_clear()
    load_chunk_report_map.cache_clear()


def start_job(job_type: str, commands: list[list[str]]) -> dict[str, Any]:
    job = create_job(job_type)
    thread = threading.Thread(target=run_pipeline_job, args=(job, commands), daemon=True)
    thread.start()
    return job


def atlas_settings_from_env() -> dict[str, str | None]:
    return {
        "atlas_uri": os.getenv("MONGODB_ATLAS_URI"),
        "atlas_db": os.getenv("MONGODB_ATLAS_DB"),
        "atlas_collection": os.getenv("MONGODB_ATLAS_COLLECTION"),
        "atlas_vector_index": os.getenv("MONGODB_ATLAS_VECTOR_INDEX"),
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat/ask")
def ask_question_endpoint(payload: AskQuestionPayload) -> dict[str, Any]:
    started = time.perf_counter()
    settings = normalize_settings(payload.settings)
    session_id = payload.sessionId or f"session-{uuid.uuid4().hex[:12]}"
    atlas_settings = atlas_settings_from_env()

    try:
        result = answer_question(
            payload.question,
            chunks_path=CHUNKS_PATH,
            bm25_index_path=BM25_INDEX_PATH,
            vector_dir=VECTOR_DIR,
            query_rewrite_mode="llm" if settings["query_rewrite"] else "none",
            query_rewrite_model=DEFAULT_QUERY_REWRITE_MODEL,
            query_rewrite_count=4,
            retrieval_mode=settings["mode"],
            vector_backend=settings["vector_backend"],
            embedding_model=DEFAULT_EMBEDDING_MODEL,
            atlas_uri=atlas_settings["atlas_uri"],
            atlas_db=atlas_settings["atlas_db"],
            atlas_collection=atlas_settings["atlas_collection"],
            atlas_vector_index=atlas_settings["atlas_vector_index"],
            model=settings.get("model") or DEFAULT_CHAT_MODEL,
            memory_model=DEFAULT_MEMORY_MODEL,
            top_k=settings["top_k"],
            session_id=session_id,
            session_dir=SESSIONS_DIR,
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail="OpenAI API key is invalid or expired.") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except APIError as exc:
        raise HTTPException(status_code=502, detail="OpenAI request failed. Check API availability and billing.") from exc

    sources = [map_retrieved_source(item) for item in result.get("retrieved", [])]
    processing_time_ms = int((time.perf_counter() - started) * 1000)
    session = load_session(session_id, SESSIONS_DIR)
    message_id = f"msg-{uuid.uuid4().hex[:12]}"
    if session.get("history"):
        last_message = session["history"][-1]
        if last_message.get("role") == "assistant":
            last_message.setdefault("id", message_id)
            message_id = str(last_message["id"])
            if sources:
                last_message["sources"] = sources
            last_message["metadata"] = {
                "retrievalMode": settings["mode"],
                "modelUsed": settings.get("model") or DEFAULT_CHAT_MODEL,
                "queryRewritten": result.get("retrieval_input") if result.get("retrieval_input") != payload.question else None,
                "processingTimeMs": processing_time_ms,
            }
            save_session(session, SESSIONS_DIR)

    return {
        "success": True,
        "data": {
            "answer": result.get("answer", ""),
            "sessionId": session_id,
            "messageId": message_id,
            "sources": sources,
            "metadata": {
                "retrievalMode": settings["mode"],
                "modelUsed": settings.get("model") or DEFAULT_CHAT_MODEL,
                "queryRewritten": result.get("retrieval_input") if result.get("retrieval_input") != payload.question else None,
                "processingTimeMs": processing_time_ms,
            },
        },
    }


@app.get("/api/sessions")
def get_sessions() -> dict[str, Any]:
    return {"success": True, "data": load_session_documents()}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    for session in load_session_documents():
        if session["id"] == session_id:
            return {"success": True, "data": session}
    return {"success": False, "error": "Session not found"}


@app.patch("/api/sessions/{session_id}")
def update_session(session_id: str, payload: UpdateSessionPayload) -> dict[str, Any]:
    session = load_session(session_id, SESSIONS_DIR)
    if not session.get("history"):
        return {"success": False, "error": "Session not found"}

    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            return {"success": False, "error": "Tiêu đề không được để trống"}
        session["title"] = title[:120]

    if payload.pinned is not None:
        session["pinned"] = payload.pinned

    save_session(session, SESSIONS_DIR, touch_updated_at=False)
    for item in load_session_documents():
        if item["id"] == session_id:
            return {"success": True, "data": item}
    return {"success": False, "error": "Session not found"}


@app.get("/api/sessions/{session_id}/conversation")
def get_conversation(session_id: str) -> dict[str, Any]:
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return {"success": False, "error": "Conversation not found"}

    session = safe_json_load(path, {})
    history = session.get("history", []) if isinstance(session.get("history"), list) else []
    base_time = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC) - timedelta(minutes=max(len(history) - 1, 0))
    messages = [
        session_message_to_api(item, base_time + timedelta(minutes=index))
        for index, item in enumerate(history)
        if isinstance(item, dict)
    ]
    return {"success": True, "data": {"sessionId": session_id, "messages": messages}}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, Any]:
    path = SESSIONS_DIR / f"{session_id}.json"
    if path.exists():
        path.unlink()
    return {"success": True, "data": None}


@app.post("/api/sessions/{session_id}/archive")
def archive_session(session_id: str) -> dict[str, Any]:
    session = load_session(session_id, SESSIONS_DIR)
    if not session.get("history"):
        return {"success": False, "error": "Session not found"}
    session["archived"] = True
    save_session(session, SESSIONS_DIR, touch_updated_at=False)
    for item in load_session_documents():
        if item["id"] == session_id:
            item["archived"] = True
            return {"success": True, "data": item}
    return {"success": False, "error": "Session not found"}


@app.get("/api/documents")
def get_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    status: str | None = None,
    type: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    documents = load_documents_cache()
    filtered = documents
    if status:
        filtered = [item for item in filtered if item["status"] == status]
    if type:
        filtered = [item for item in filtered if item["documentType"] == type]
    if search:
        needle = search.casefold()
        filtered = [
            item for item in filtered
            if needle in item["title"].casefold() or needle in item["documentNumber"].casefold()
        ]

    start = (page - 1) * page_size
    items = filtered[start:start + page_size]
    return {
        "success": True,
        "data": {
            "items": items,
            "total": len(filtered),
            "page": page,
            "pageSize": page_size,
            "hasMore": start + page_size < len(filtered),
        },
    }


@app.get("/api/documents/{document_id}")
def get_document(document_id: str) -> dict[str, Any]:
    for document in load_documents_cache():
        if document["id"] == document_id:
            return {"success": True, "data": document}
    return {"success": False, "error": "Document not found"}


@app.get("/api/admin/corpus-status")
def get_corpus_status() -> dict[str, Any]:
    documents = load_documents_cache()
    total_documents = len(documents)
    crawled_documents = len([item for item in documents if item["status"] in {"crawled", "chunked", "indexed"}])
    chunked_documents = len([item for item in documents if item["chunkCount"] > 0])
    total_chunks = sum(int(item["chunkCount"] or 0) for item in documents)
    bm25_exists = BM25_INDEX_PATH.exists()
    vector_exists = (VECTOR_DIR / "faiss.index").exists() or (VECTOR_DIR / "atlas_manifest.json").exists()
    bm25_updated = serialize_datetime(datetime.fromtimestamp(BM25_INDEX_PATH.stat().st_mtime, tz=UTC)) if bm25_exists else None
    vector_target = VECTOR_DIR / "faiss.index" if (VECTOR_DIR / "faiss.index").exists() else VECTOR_DIR / "atlas_manifest.json"
    vector_updated = serialize_datetime(datetime.fromtimestamp(vector_target.stat().st_mtime, tz=UTC)) if vector_exists else None

    return {
        "success": True,
        "data": {
            "totalDocuments": total_documents,
            "crawledDocuments": crawled_documents,
            "chunkedDocuments": chunked_documents,
            "totalChunks": total_chunks,
            "bm25IndexStatus": {
                "built": bm25_exists,
                "documentCount": chunked_documents,
                "lastUpdated": bm25_updated,
                "sizeBytes": BM25_INDEX_PATH.stat().st_size if bm25_exists else None,
            },
            "vectorIndexStatus": {
                "built": vector_exists,
                "documentCount": chunked_documents,
                "lastUpdated": vector_updated,
                "sizeBytes": vector_target.stat().st_size if vector_exists else None,
            },
            "lastCrawlAt": max((item["lastUpdated"] for item in documents), default=None),
            "lastIndexAt": max(filter(None, [bm25_updated, vector_updated]), default=None),
        },
    }


@app.get("/api/admin/jobs")
def get_jobs() -> dict[str, Any]:
    return {"success": True, "data": load_jobs()}


@app.post("/api/admin/jobs/crawl")
def trigger_crawl() -> dict[str, Any]:
    commands = [
        [sys.executable, "-m", "law_rag.crawl.crawl_laws", "--docx", "luat.docx", "--output", "output/laws", "--clean"],
    ]
    job = start_job("crawl", commands)
    return {"success": True, "data": job}


@app.post("/api/admin/jobs/chunk")
def trigger_chunking() -> dict[str, Any]:
    commands = [
        [sys.executable, "-m", "law_rag.crawl.chunk_framework_check", "--input", "output/laws", "--json-out", "output/chunk_framework_report.json"],
        [sys.executable, "-m", "law_rag.crawl.chunk_laws", "--input", "output/laws", "--output-dir", "output/chunks"],
    ]
    job = start_job("chunk", commands)
    return {"success": True, "data": job}


@app.post("/api/admin/jobs/index-bm25")
def trigger_bm25() -> dict[str, Any]:
    commands = [
        [sys.executable, "-m", "law_rag.retrieval.retrieve_chunks", "build", "--chunks", "output/chunks/all_chunks.jsonl", "--output", "output/chunks/retrieval/bm25_index.json"],
    ]
    job = start_job("index_bm25", commands)
    return {"success": True, "data": job}


@app.post("/api/admin/jobs/index-vector")
def trigger_vector() -> dict[str, Any]:
    commands = [
        [sys.executable, "-m", "law_rag.retrieval.build_vector_index", "--chunks", "output/chunks/all_chunks.jsonl", "--output-dir", "output/chunks/retrieval/vector", "--backend", "faiss"],
    ]
    job = start_job("index_vector", commands)
    return {"success": True, "data": job}


@app.post("/api/admin/debug/query")
def debug_query(payload: DebugQueryPayload) -> dict[str, Any]:
    settings = normalize_settings(payload.settings)
    atlas_settings = atlas_settings_from_env()
    query_rewrite_mode = "llm" if settings["query_rewrite"] else "none"

    rewrite_started = time.perf_counter()
    retrieval_plan = build_retrieval_queries(
        payload.query,
        rewrite_mode=query_rewrite_mode,
        rewrite_model=DEFAULT_QUERY_REWRITE_MODEL,
        max_rewrites=4,
    )
    rewrite_ms = int((time.perf_counter() - rewrite_started) * 1000) if settings["query_rewrite"] else None

    bm25_results: list[dict[str, Any]] = []
    vector_results: list[dict[str, Any]] = []
    fused_results: list[dict[str, Any]] = []

    bm25_ms = 0
    if settings["mode"] in {"bm25", "hybrid"}:
        started = time.perf_counter()
        bm25_results = hybrid_search(
            payload.query,
            retrieval_queries=retrieval_plan["retrieval_queries"],
            chunks_path=CHUNKS_PATH,
            bm25_index_path=BM25_INDEX_PATH,
            vector_dir=VECTOR_DIR,
            retrieval_mode="bm25",
            vector_backend=settings["vector_backend"],
            embedding_model=DEFAULT_EMBEDDING_MODEL,
            atlas_uri=atlas_settings["atlas_uri"],
            atlas_db=atlas_settings["atlas_db"],
            atlas_collection=atlas_settings["atlas_collection"],
            atlas_vector_index=atlas_settings["atlas_vector_index"],
            bm25_top_k=max(settings["top_k"] * 2, 8),
            vector_top_k=max(settings["top_k"] * 2, 8),
            final_top_k=settings["top_k"],
        )
        bm25_ms = int((time.perf_counter() - started) * 1000)

    vector_ms = 0
    if settings["mode"] in {"vector", "hybrid"}:
        started = time.perf_counter()
        vector_results = hybrid_search(
            payload.query,
            retrieval_queries=retrieval_plan["retrieval_queries"],
            chunks_path=CHUNKS_PATH,
            bm25_index_path=BM25_INDEX_PATH,
            vector_dir=VECTOR_DIR,
            retrieval_mode="vector",
            vector_backend=settings["vector_backend"],
            embedding_model=DEFAULT_EMBEDDING_MODEL,
            atlas_uri=atlas_settings["atlas_uri"],
            atlas_db=atlas_settings["atlas_db"],
            atlas_collection=atlas_settings["atlas_collection"],
            atlas_vector_index=atlas_settings["atlas_vector_index"],
            bm25_top_k=max(settings["top_k"] * 2, 8),
            vector_top_k=max(settings["top_k"] * 2, 8),
            final_top_k=settings["top_k"],
        )
        vector_ms = int((time.perf_counter() - started) * 1000)

    fusion_started = time.perf_counter()
    if settings["mode"] == "hybrid":
        fused_results = hybrid_search(
            payload.query,
            retrieval_queries=retrieval_plan["retrieval_queries"],
            chunks_path=CHUNKS_PATH,
            bm25_index_path=BM25_INDEX_PATH,
            vector_dir=VECTOR_DIR,
            retrieval_mode="hybrid",
            vector_backend=settings["vector_backend"],
            embedding_model=DEFAULT_EMBEDDING_MODEL,
            atlas_uri=atlas_settings["atlas_uri"],
            atlas_db=atlas_settings["atlas_db"],
            atlas_collection=atlas_settings["atlas_collection"],
            atlas_vector_index=atlas_settings["atlas_vector_index"],
            bm25_top_k=max(settings["top_k"] * 2, 8),
            vector_top_k=max(settings["top_k"] * 2, 8),
            final_top_k=settings["top_k"],
        )
    else:
        fused_results = bm25_results if settings["mode"] == "bm25" else vector_results
    fusion_ms = int((time.perf_counter() - fusion_started) * 1000)

    total_ms = (rewrite_ms or 0) + bm25_ms + vector_ms + fusion_ms
    return {
        "success": True,
        "data": {
            "originalQuery": payload.query,
            "rewrittenQuery": retrieval_plan["retrieval_queries"][1] if len(retrieval_plan["retrieval_queries"]) > 1 else None,
            "bm25Results": [map_retrieved_source(item) for item in bm25_results],
            "vectorResults": [map_retrieved_source(item) for item in vector_results],
            "fusedResults": [map_retrieved_source(item) for item in fused_results],
            "timings": {
                "queryRewrite": rewrite_ms,
                "bm25Search": bm25_ms,
                "vectorSearch": vector_ms,
                "fusion": fusion_ms,
                "total": total_ms,
            },
        },
    }


@app.post("/api/uploads")
async def upload_document(file: UploadFile = File(...)) -> dict[str, Any]:
    ensure_directory(UPLOADS_DIR)
    upload_id = f"upload-{uuid.uuid4().hex[:12]}"
    destination = UPLOADS_DIR / f"{upload_id}-{file.filename}"
    content = await file.read()
    destination.write_bytes(content)
    extension = destination.suffix.casefold()
    if extension == ".pdf":
        file_type = "pdf"
    elif extension in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        file_type = "image"
    else:
        file_type = "docx"

    created_at = utc_now_iso()
    status_path = UPLOADS_DIR / f"{upload_id}.json"
    metadata = {
        "id": upload_id,
        "fileName": file.filename,
        "fileType": file_type,
        "fileSize": len(content),
        "uploadedAt": created_at,
        "status": "processing",
        "ocrProgress": 0,
    }
    status_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"success": True, "data": metadata}


@app.get("/api/uploads/{upload_id}")
def get_upload_status(upload_id: str) -> dict[str, Any]:
    status_path = UPLOADS_DIR / f"{upload_id}.json"
    if not status_path.exists():
        return {"success": False, "error": "Upload not found"}
    return {"success": True, "data": safe_json_load(status_path, {})}