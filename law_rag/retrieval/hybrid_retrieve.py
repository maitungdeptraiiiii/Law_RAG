from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from ..core.embedding_client import DEFAULT_EMBEDDING_MODEL, embed_query as embed_query_text, embed_texts, embedding_provider
from ..core.env_loader import load_project_env
from ..core.llm_client import chat_completion_json, get_chat_client
from ..core.runtime_config import default_vector_dir, query_rewrite_model
from .atlas_vector_store import atlas_vector_search, get_atlas_collection
from .graph_retrieve import expand_with_neo4j_graph
from .retrieve_chunks import (
    build_index_payload,
    load_index,
    query_index,
    save_index,
)
from .sqlite_retrieval_store import (
    SQLiteRetrievalStore,
    build_sqlite_retrieval_store,
    default_store_path_for_bm25_index,
    default_store_path_for_chunks,
    open_store_if_exists,
)
from .model_reranker import rerank_candidates_with_model


DEFAULT_QUERY_REWRITE_MODEL = query_rewrite_model()
TOKEN_RE = re.compile(r"\w+", re.UNICODE)
ARTICLE_RE = re.compile(r"\b(?:điều|dieu|article)\s+(\d+[a-z]?)\b", re.IGNORECASE)
LEGAL_NUMBER_RE = re.compile(r"\b\d{1,4}\s*[/\-]\s*\d{4}\s*[/\-]\s*[A-Za-zĐđ]+[A-Za-z0-9Đđ]*\b")

MAX_RETRIEVAL_QUERY_CHARS = 180
MAX_ACTIVE_RETRIEVAL_QUERIES = 3

_VECTOR_ASSET_CACHE_LOCK = threading.RLock()
_VECTOR_ASSET_CACHE: dict[
    Path,
    tuple[
        tuple[tuple[str, int, int], ...],
        tuple[dict, list[dict] | SQLiteRetrievalStore, faiss.Index],
    ],
] = {}

DEFAULT_LEGAL_ISSUE_RULES_PATH = Path(__file__).with_name("legal_issues_full_all_added.json")
DEFAULT_LEGAL_ISSUE_SEMANTIC_INDEX_DIR = Path("output/legal_issue_semantic_index")
_LEGAL_ISSUE_RULES_CACHE: list[dict[str, Any]] | None = None
_LEGAL_ISSUE_RULES_CACHE_SIGNATURE: tuple[str, int, int] | None = None
_LEGAL_ISSUE_SEMANTIC_CACHE: tuple[tuple[str, str, str, str], dict[str, Any]] | None = None


load_project_env()


QUERY_REWRITE_SYSTEM_PROMPT = """Ban viet lai cau hoi de tim van ban phap luat Viet Nam.
Bat buoc:
- Giu dung chu de cua cau hoi goc, khong suy dien sang chu de khac.
- Neu cau hoi mo ta tinh tiet doi thuong, hay suy luan van de phap ly co kha nang nhat va dua vao retrieval_queries.
- Neu co nhieu kha nang phap ly gan nhau, tao query cho 2-3 gia thuyet chinh de retrieval doi chieu.
- Vi du: "muon xe roi ban lay tien" co the la lam dung tin nhiem chiem doat tai san Dieu 175; neu gian doi ngay tu dau thi doi chieu lua dao chiem doat tai san Dieu 174.
- Vi du: "vay tien khong tra" thuong can doi chieu hop dong vay tai san/nghia vu tra no Bo luat Dan su, khong mac dinh la toi hinh su neu thieu dau hieu chiem doat.
- Chi viet bang tieng Viet.
- Neu cau hoi la "toi danh nguoi bi toi gi", chu de la co y gay thuong tich/gay ton hai suc khoe, Dieu 134 Bo luat Hinh su.
- Tra ve dung JSON, khong markdown, khong giai thich.
- JSON phai co dung 2 khoa: "legal_intent" la chuoi, "retrieval_queries" la mang chuoi.
- Moi retrieval query ngan hon 120 ky tu.
Vi du:
{"legal_intent":"xac dinh trach nhiem hinh su khi danh nguoi gay thuong tich","retrieval_queries":["co y gay thuong tich Dieu 134 Bo luat Hinh su","danh nguoi gay thuong tich bi xu ly the nao","ty le thuong tat truy cuu trach nhiem hinh su"]}
"""


def deduplicate_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for query in queries:
        normalized = compact_retrieval_query(query)
        if not normalized:
            continue
        lowered = normalized.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        ordered.append(normalized)
    return ordered


def compact_retrieval_query(query: str, *, max_chars: int = MAX_RETRIEVAL_QUERY_CHARS) -> str:
    normalized = " ".join(str(query or "").split())
    if len(normalized) <= max_chars:
        return normalized

    clipped = normalized[:max_chars].rsplit(" ", 1)[0].strip()
    return clipped or normalized[:max_chars].strip()


def max_active_retrieval_queries() -> int:
    try:
        return max(1, int(os.getenv("MAX_ACTIVE_RETRIEVAL_QUERIES", str(MAX_ACTIVE_RETRIEVAL_QUERIES))))
    except ValueError:
        return MAX_ACTIVE_RETRIEVAL_QUERIES


def limit_retrieval_queries(queries: list[str], *, max_queries: int | None = None) -> list[str]:
    max_queries = max_queries or max_active_retrieval_queries()
    return deduplicate_queries(queries)[:max_queries]


def issue_rule_confidence_threshold() -> float:
    try:
        return float(os.getenv("LEGAL_ISSUE_RULE_CONFIDENCE", "0.9"))
    except ValueError:
        return 0.9


def _env_enabled(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def legal_issue_semantic_enabled() -> bool:
    return _env_enabled("LEGAL_ISSUE_SEMANTIC_ENABLED", default=True)


def legal_issue_semantic_threshold() -> float:
    try:
        return float(os.getenv("LEGAL_ISSUE_SEMANTIC_THRESHOLD", "0.78"))
    except ValueError:
        return 0.78


def legal_issue_semantic_top_k() -> int:
    try:
        return max(1, int(os.getenv("LEGAL_ISSUE_SEMANTIC_TOP_K", "3")))
    except ValueError:
        return 3


def legal_issue_rules_path() -> Path:
    configured_path = os.getenv("LEGAL_ISSUE_RULES_PATH")
    if configured_path:
        path = Path(configured_path)
        return path if path.is_absolute() else Path.cwd() / path
    return DEFAULT_LEGAL_ISSUE_RULES_PATH


def legal_issue_semantic_index_dir() -> Path:
    configured_path = os.getenv("LEGAL_ISSUE_SEMANTIC_INDEX_DIR")
    if configured_path:
        path = Path(configured_path)
        return path if path.is_absolute() else Path.cwd() / path
    return DEFAULT_LEGAL_ISSUE_SEMANTIC_INDEX_DIR


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_legal_issue_rules() -> list[dict[str, Any]]:
    global _LEGAL_ISSUE_RULES_CACHE, _LEGAL_ISSUE_RULES_CACHE_SIGNATURE
    path = legal_issue_rules_path()
    if not path.exists():
        _LEGAL_ISSUE_RULES_CACHE = []
        _LEGAL_ISSUE_RULES_CACHE_SIGNATURE = None
        return _LEGAL_ISSUE_RULES_CACHE

    stat = path.stat()
    signature = (str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    if _LEGAL_ISSUE_RULES_CACHE is not None and _LEGAL_ISSUE_RULES_CACHE_SIGNATURE == signature:
        return _LEGAL_ISSUE_RULES_CACHE

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Legal issue rules must be a JSON array: {path}")
    _LEGAL_ISSUE_RULES_CACHE = [item for item in payload if isinstance(item, dict)]
    _LEGAL_ISSUE_RULES_CACHE_SIGNATURE = signature
    return _LEGAL_ISSUE_RULES_CACHE



def rule_retrieval_queries(rule: dict[str, Any]) -> list[str]:
    values = rule.get("retrieval_queries", [])
    if not isinstance(values, list):
        return []
    return [str(item) for item in values if str(item).strip()]


def rule_str_list(rule: dict[str, Any], key: str) -> list[str]:
    values = rule.get(key, [])
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def rule_semantic_queries(rule: dict[str, Any]) -> list[str]:
    return rule_str_list(rule, "semantic_queries")


def rule_search_texts(rule: dict[str, Any]) -> list[str]:
    values = [
        str(rule.get("display_name") or "").strip(),
        str(rule.get("issue_type_name") or "").strip(),
        str(rule.get("description") or "").strip(),
        *rule_semantic_queries(rule),
        *rule_retrieval_queries(rule),
    ]
    return deduplicate_queries([value for value in values if value])


def rule_match_payload(
    rule: dict[str, Any],
    *,
    confidence: float,
    match_source: str,
    semantic_score: float | None = None,
    semantic_query: str | None = None,
) -> dict[str, Any]:
    payload = {
        "label": str(rule.get("label") or rule.get("issue_type") or "").strip(),
        "issue_type": str(rule.get("issue_type") or "").strip(),
        "display_name": str(rule.get("display_name") or "").strip(),
        "issue_type_name": str(rule.get("issue_type_name") or "").strip(),
        "description": str(rule.get("description") or "").strip(),
        "confidence": confidence,
        "retrieval_queries": rule_retrieval_queries(rule),
        "semantic_queries": rule_semantic_queries(rule),
        "preferred_articles": rule_str_list(rule, "preferred_articles"),
        "distinguish_from_articles": rule_str_list(
            rule,
            "distinguish_from_articles" if "distinguish_from_articles" in rule else "avoid_articles",
        ),
        "document_title_hints": rule_str_list(rule, "document_title_hints"),
        "match_source": match_source,
    }
    if semantic_score is not None:
        payload["semantic_score"] = round(semantic_score, 6)
    if semantic_query:
        payload["semantic_query"] = semantic_query
    return payload



def _semantic_rule_cache_signature(rules: list[dict[str, Any]]) -> tuple[str, str, str, str]:
    path = legal_issue_rules_path()
    provider = embedding_provider()
    model = DEFAULT_EMBEDDING_MODEL
    try:
        return (str(path.resolve()), _file_sha256(path), provider, model)
    except OSError:
        fallback_hash = hashlib.sha256(
            json.dumps(rules, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return (str(path), fallback_hash, provider, model)


def _cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator <= 0:
        return 0.0
    return float(np.dot(left, right) / denominator)


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 0:
        return vector.astype("float32")
    return (vector / norm).astype("float32")


def _rule_from_semantic_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": entry.get("label"),
        "issue_type": entry.get("issue_type"),
        "display_name": entry.get("display_name"),
        "issue_type_name": entry.get("issue_type_name"),
        "description": entry.get("description"),
        "confidence": entry.get("confidence"),
        "semantic_queries": entry.get("semantic_queries", []),
        "retrieval_queries": entry.get("retrieval_queries", []),
        "preferred_articles": entry.get("preferred_articles", []),
        "distinguish_from_articles": entry.get("distinguish_from_articles", []),
        "document_title_hints": entry.get("document_title_hints", []),
    }


def load_legal_issue_semantic_index_from_disk(signature: tuple[str, str, str, str]) -> dict[str, Any]:
    index_dir = legal_issue_semantic_index_dir()
    metadata_path = index_dir / "metadata.json"
    faiss_path = index_dir / "faiss.index"
    vectors_path = index_dir / "vectors.npy"
    if not metadata_path.exists():
        return {}

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        return {}
    if metadata.get("rules_sha256") != signature[1]:
        return {}
    if metadata.get("embedding_provider") != signature[2]:
        return {}
    if metadata.get("embedding_model") != signature[3]:
        return {}

    entries = metadata.get("entries")
    if not isinstance(entries, list) or not entries:
        return {}

    normalized_entries = [entry for entry in entries if isinstance(entry, dict)]
    if len(normalized_entries) != len(entries):
        return {}

    if faiss_path.exists():
        faiss_index = faiss.read_index(str(faiss_path))
        if faiss_index.ntotal != len(normalized_entries):
            return {}
        return {"entries": normalized_entries, "faiss_index": faiss_index, "source": "faiss"}

    if not vectors_path.exists():
        return {}
    vectors = np.load(vectors_path).astype("float32")
    if vectors.shape[0] != len(normalized_entries):
        return {}
    return {"entries": normalized_entries, "vectors": vectors, "source": "vectors"}


def legal_issue_semantic_index(rules: list[dict[str, Any]]) -> dict[str, Any]:
    global _LEGAL_ISSUE_SEMANTIC_CACHE
    signature = _semantic_rule_cache_signature(rules)
    if _LEGAL_ISSUE_SEMANTIC_CACHE is not None and _LEGAL_ISSUE_SEMANTIC_CACHE[0] == signature:
        return _LEGAL_ISSUE_SEMANTIC_CACHE[1]

    disk_index = load_legal_issue_semantic_index_from_disk(signature)
    if disk_index:
        _LEGAL_ISSUE_SEMANTIC_CACHE = (signature, disk_index)
        return disk_index

    entries: list[dict[str, Any]] = []
    texts: list[str] = []
    for rule in rules:
        for semantic_query in rule_search_texts(rule):
            entries.append({"rule": rule, "semantic_query": semantic_query})
            texts.append(semantic_query)

    if texts:
        vectors = embed_texts(texts)
        for entry, vector in zip(entries, vectors, strict=False):
            entry["vector"] = _normalize_vector(np.asarray(vector, dtype="float32"))

    index = {
        "entries": [
            {
                **entry,
                "rule": entry["rule"],
            }
            for entry in entries
            if "vector" in entry
        ],
        "vectors": np.asarray([entry["vector"] for entry in entries if "vector" in entry], dtype="float32"),
        "source": "memory",
    }
    _LEGAL_ISSUE_SEMANTIC_CACHE = (signature, index)
    return index


def match_legal_issue_rules_semantically(query: str, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not legal_issue_semantic_enabled() or not query.strip():
        return []

    index = legal_issue_semantic_index(rules)
    if not index:
        return []

    query_vector = _normalize_vector(np.asarray(embed_query_text(query), dtype="float32"))
    threshold = legal_issue_semantic_threshold()
    top_k = legal_issue_semantic_top_k()
    best_by_label: dict[str, dict[str, Any]] = {}
    rules_by_label = {
        str(rule.get("label") or rule.get("issue_type") or "").strip(): rule
        for rule in rules
        if str(rule.get("label") or rule.get("issue_type") or "").strip()
    }

    candidate_entries: list[tuple[dict[str, Any], float]] = []
    entries = index.get("entries", [])
    faiss_index = index.get("faiss_index")
    if faiss_index is not None:
        search_k = min(max(top_k * 8, top_k, 16), len(entries))
        scores, indices = faiss_index.search(query_vector.reshape(1, -1), search_k)
        for score, entry_index in zip(scores[0], indices[0], strict=False):
            if entry_index < 0:
                continue
            candidate_entries.append((entries[int(entry_index)], float(score)))
    else:
        vectors = index.get("vectors")
        if vectors is None:
            return []
        for entry, vector in zip(entries, vectors, strict=False):
            candidate_entries.append((entry, _cosine_similarity(query_vector, vector)))

    for entry, score in candidate_entries:
        entry_label = str(entry.get("label") or entry.get("issue_type") or "").strip()
        rule = entry.get("rule") or rules_by_label.get(entry_label) or _rule_from_semantic_entry(entry)
        label = str(rule.get("label") or rule.get("issue_type") or "").strip()
        if not label:
            continue
        if score < threshold:
            continue
        existing = best_by_label.get(label)
        if existing is not None and float(existing.get("semantic_score") or 0.0) >= score:
            continue
        base_confidence = float(rule.get("confidence") or 0.0)
        confidence = min(0.99, max(base_confidence, score))
        best_by_label[label] = rule_match_payload(
            rule,
            confidence=confidence,
            match_source="semantic",
            semantic_score=score,
            semantic_query=str(entry.get("semantic_query") or ""),
        )

    matches = list(best_by_label.values())
    matches.sort(key=lambda item: item["confidence"], reverse=True)
    return matches[:top_k]


def prune_weaker_legal_issue_matches(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not matches:
        return []

    top_confidence = float(matches[0].get("confidence") or 0.0)
    if top_confidence < 0.9:
        return matches

    minimum_confidence = max(legal_issue_semantic_threshold(), top_confidence - 0.08)
    return [match for match in matches if float(match.get("confidence") or 0.0) >= minimum_confidence]


def extract_legal_issues_with_rules(query: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    matched_labels: set[str] = set()
    rules = load_legal_issue_rules()

    try:
        semantic_matches = match_legal_issue_rules_semantically(query, rules)
    except Exception:
        semantic_matches = []

    for match in semantic_matches:
        if match["label"] in matched_labels:
            continue
        matches.append(match)
        matched_labels.add(match["label"])

    matches.sort(key=lambda item: item["confidence"], reverse=True)
    matches = prune_weaker_legal_issue_matches(matches)
    retrieval_queries = [
        retrieval_query
        for match in matches
        for retrieval_query in match["retrieval_queries"]
    ]
    confidence = matches[0]["confidence"] if matches else 0.0
    return {
        "confidence": confidence,
        "labels": [item["label"] for item in matches if item["label"]],
        "retrieval_queries": deduplicate_queries(retrieval_queries),
        "matches": matches,
        "high_confidence": confidence >= issue_rule_confidence_threshold(),
    }



def normalize_text(text: str) -> str:
    normalized = str(text or "").casefold().replace("đ", "d")
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(character for character in normalized if unicodedata.category(character) != "Mn")
    return re.sub(r"\s+", " ", normalized).strip()


def tokenize(text: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(normalize_text(text)) if len(token) >= 2]


def extract_article_numbers(text: str) -> set[str]:
    return {match.group(1).casefold() for match in ARTICLE_RE.finditer(str(text or ""))}


def result_text(item: dict) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in (
            "source_file",
            "document_title",
            "article_number",
            "clause_number",
            "target_article",
            "chapter",
            "preview",
            "text",
        )
    )


def lexical_overlap_score(queries: list[str], item: dict) -> float:
    query_tokens = set(token for query in queries for token in tokenize(query))
    if not query_tokens:
        return 0.0
    text_tokens = set(tokenize(result_text(item)))
    if not text_tokens:
        return 0.0
    return len(query_tokens & text_tokens) / len(query_tokens)


def article_match_score(queries: list[str], item: dict) -> float:
    query_articles = {article for query in queries for article in extract_article_numbers(query)}
    if not query_articles:
        return 0.0
    actual_article = normalize_text(item.get("article_number"))
    target_article = normalize_text(item.get("target_article"))
    if actual_article in query_articles:
        return 1.0
    if any(article and article in target_article for article in query_articles):
        return 0.6
    return 0.0


def legal_issue_article_score(legal_issue_matches: list[dict[str, Any]] | None, item: dict) -> float:
    if not legal_issue_matches:
        return 0.0

    actual_article = normalize_text(item.get("article_number"))
    target_article = normalize_text(item.get("target_article"))
    item_title = normalize_text(
        " ".join(
            str(item.get(key) or "")
            for key in ("document_title", "doc_number", "doc_type", "source_file", "preview")
        )
    )
    best_score = 0.0
    for match in legal_issue_matches:
        preferred_articles = {normalize_text(article) for article in match.get("preferred_articles", [])}
        if not preferred_articles:
            continue
        article_matches = actual_article in preferred_articles or any(
            article and article in target_article for article in preferred_articles
        )
        if not article_matches:
            continue

        title_hints = [normalize_text(hint) for hint in match.get("document_title_hints", []) if str(hint).strip()]
        if title_hints:
            if any(hint and hint in item_title for hint in title_hints):
                best_score = max(best_score, 1.0)
            else:
                best_score = max(best_score, 0.55)
        else:
            best_score = max(best_score, 0.75)
    return best_score


def source_coverage_score(item: dict) -> float:
    sources = set(item.get("sources") or [])
    if {"bm25", "vector"}.issubset(sources):
        return 1.0
    if sources:
        return 0.4
    return 0.0


def normalize_identifier(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_text(text))


def query_document_identifiers(queries: list[str]) -> set[str]:
    identifiers: set[str] = set()
    for query in queries:
        for match in LEGAL_NUMBER_RE.finditer(query):
            identifiers.add(normalize_identifier(match.group(0)))
    return identifiers


def pinned_document_chunks(chunks_paths: list[Path], queries: list[str], *, limit_per_document: int = 4) -> list[dict]:
    identifiers = query_document_identifiers(queries)
    if not identifiers:
        return []

    pinned: list[dict] = []
    pinned_count_by_source: dict[str, int] = {}
    for chunks_path in chunks_paths:
        if not chunks_path.exists():
            continue
        if chunks_path.stat().st_size > 250 * 1024 * 1024:
            continue
        with chunks_path.open(encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                source_file = str(chunk.get("source_file") or "")
                searchable_identifier = " ".join(
                    str(chunk.get(key) or "")
                    for key in ("source_file", "doc_number", "document_title")
                )
                normalized_source = normalize_identifier(searchable_identifier)
                if not any(identifier in normalized_source for identifier in identifiers):
                    continue
                if pinned_count_by_source.get(source_file, 0) >= limit_per_document:
                    continue
                pinned_count_by_source[source_file] = pinned_count_by_source.get(source_file, 0) + 1
                text = str(chunk.get("text") or "")
                pinned.append(
                    {
                        "score": 1.0,
                        "chunk_id": chunk["chunk_id"],
                        "source_file": source_file,
                        "vbpl_id": chunk.get("vbpl_id"),
                        "doc_number": chunk.get("doc_number"),
                        "doc_type": chunk.get("doc_type"),
                        "source_url": chunk.get("source_url"),
                        "issue_date": chunk.get("issue_date"),
                        "article_number": chunk.get("article_number"),
                        "clause_number": chunk.get("clause_number"),
                        "point_number": chunk.get("point_number"),
                        "parent_chunk_id": chunk.get("parent_chunk_id"),
                        "parent_context_text": chunk.get("parent_context_text"),
                        "merged_short_chunk": chunk.get("merged_short_chunk"),
                        "merged_chunk_ids": chunk.get("merged_chunk_ids"),
                        "document_title": chunk.get("document_title"),
                        "chapter": chunk.get("chapter"),
                        "section": chunk.get("section"),
                        "target_article": chunk.get("target_article"),
                        "preview": text[:400],
                        "text": text,
                        "search_source": "document",
                    }
                )
    return pinned


def pinned_legal_issue_chunks(
    chunks_paths: list[Path],
    legal_issue_matches: list[dict[str, Any]] | None,
    *,
    limit_per_issue: int = 3,
) -> list[dict]:
    if not legal_issue_matches:
        return []

    pinned: list[dict] = []
    pinned_count_by_issue: dict[str, int] = {}
    for chunks_path in chunks_paths:
        if not chunks_path.exists():
            continue
        if chunks_path.stat().st_size > 250 * 1024 * 1024:
            continue
        with chunks_path.open(encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                for match in legal_issue_matches:
                    label = str(match.get("label") or match.get("issue_type") or "").strip()
                    if not label:
                        continue
                    if pinned_count_by_issue.get(label, 0) >= limit_per_issue:
                        continue
                    if legal_issue_article_score([match], chunk) < 1.0:
                        continue
                    pinned_count_by_issue[label] = pinned_count_by_issue.get(label, 0) + 1
                    text = str(chunk.get("text") or "")
                    pinned.append(
                        {
                            "score": 1.0,
                            "chunk_id": chunk["chunk_id"],
                            "source_file": str(chunk.get("source_file") or ""),
                            "vbpl_id": chunk.get("vbpl_id"),
                            "doc_number": chunk.get("doc_number"),
                            "doc_type": chunk.get("doc_type"),
                            "source_url": chunk.get("source_url"),
                            "issue_date": chunk.get("issue_date"),
                            "article_number": chunk.get("article_number"),
                            "clause_number": chunk.get("clause_number"),
                            "point_number": chunk.get("point_number"),
                            "parent_chunk_id": chunk.get("parent_chunk_id"),
                            "parent_context_text": chunk.get("parent_context_text"),
                            "merged_short_chunk": chunk.get("merged_short_chunk"),
                            "merged_chunk_ids": chunk.get("merged_chunk_ids"),
                            "document_title": chunk.get("document_title"),
                            "chapter": chunk.get("chapter"),
                            "section": chunk.get("section"),
                            "target_article": chunk.get("target_article"),
                            "preview": text[:400],
                            "text": text,
                            "search_source": "document",
                            "legal_issue_label": label,
                        }
                    )
    return pinned


def rerank_results(
    results: list[dict],
    *,
    queries: list[str],
    top_k: int,
    legal_issue_matches: list[dict[str, Any]] | None = None,
) -> list[dict]:
    if not results:
        return []

    max_rrf = max(float(item.get("rrf_score") or 0.0) for item in results) or 1.0
    reranked: list[dict] = []
    for item in results:
        rrf_component = float(item.get("rrf_score") or 0.0) / max_rrf
        lexical_component = lexical_overlap_score(queries, item)
        article_component = article_match_score(queries, item)
        legal_issue_component = legal_issue_article_score(legal_issue_matches, item)
        coverage_component = source_coverage_score(item)
        pinned_component = 1.0 if "document" in set(item.get("sources") or []) else 0.0
        rerank_score = (
            0.38 * rrf_component
            + 0.20 * lexical_component
            + 0.12 * article_component
            + 0.15 * legal_issue_component
            + 0.05 * coverage_component
            + 0.10 * pinned_component
        )
        reranked.append(
            {
                **item,
                "rerank_score": round(rerank_score, 6),
                "rerank_features": {
                    "rrf": round(rrf_component, 6),
                    "lexical_overlap": round(lexical_component, 6),
                    "article_match": round(article_component, 6),
                    "legal_issue_article": round(legal_issue_component, 6),
                    "source_coverage": round(coverage_component, 6),
                    "pinned_document": round(pinned_component, 6),
                },
            }
        )

    reranked.sort(key=lambda item: item["rerank_score"], reverse=True)
    return reranked[:top_k]


def rerank_candidates(
    results: list[dict],
    *,
    queries: list[str],
    top_k: int,
    legal_issue_matches: list[dict[str, Any]] | None = None,
    debug_timings: dict[str, Any] | None = None,
) -> list[dict]:
    model_reranked = rerank_candidates_with_model(results, queries=queries, top_k=top_k, debug_timings=debug_timings)
    if model_reranked is not None:
        return model_reranked
    return rerank_results(results, queries=queries, top_k=top_k, legal_issue_matches=legal_issue_matches)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def rerank_min_score() -> float:
    return max(0.0, _env_float("RERANK_MIN_SCORE", 0.15))


def rerank_min_results(top_k: int) -> int:
    default_min = min(3, max(top_k, 0))
    return max(0, min(top_k, _env_int("RERANK_MIN_RESULTS", default_min)))


def graph_pin_min_rerank_score() -> float:
    return max(0.0, _env_float("GRAPH_PIN_MIN_RERANK_SCORE", 0.45))


def graph_pin_min_model_score() -> float | None:
    raw_value = os.getenv("GRAPH_PIN_MIN_MODEL_SCORE")
    if raw_value is None or not raw_value.strip():
        return None
    return _env_float("GRAPH_PIN_MIN_MODEL_SCORE", 0.0)


def filter_reranked_results(
    results: list[dict],
    *,
    top_k: int,
    debug_timings: dict[str, Any] | None = None,
) -> list[dict]:
    if not results or top_k <= 0:
        return []

    min_score = rerank_min_score()
    min_results = rerank_min_results(top_k)
    if min_score <= 0:
        filtered = results[:top_k]
    else:
        filtered = [item for item in results if float(item.get("rerank_score") or 0.0) >= min_score]
        seen = {str(item.get("chunk_id")) for item in filtered}
        for item in results:
            if len(filtered) >= min_results:
                break
            chunk_id = str(item.get("chunk_id"))
            if chunk_id in seen:
                continue
            filtered.append(item)
            seen.add(chunk_id)
        filtered = filtered[:top_k]

    if debug_timings is not None:
        debug_timings["rerankMinScore"] = min_score
        debug_timings["rerankMinResults"] = min_results
        debug_timings["rerankFilteredFrom"] = len(results)
        debug_timings["rerankFilteredTo"] = len(filtered)
    return filtered


def _pinned_result_promotable(item: dict) -> bool:
    if float(item.get("rerank_score") or 0.0) < graph_pin_min_rerank_score():
        return False

    min_model_score = graph_pin_min_model_score()
    if min_model_score is not None and float(item.get("model_rerank_score") or 0.0) < min_model_score:
        return False

    return True


def prioritize_pinned_results(
    results: list[dict],
    pinned_results: list[dict],
    *,
    top_k: int,
    max_pinned: int = 3,
    debug_timings: dict[str, Any] | None = None,
) -> list[dict]:
    if not pinned_results:
        return results[:top_k]

    merged: list[dict] = []
    seen: set[str] = set()
    ranked_by_id = {str(item.get("chunk_id")): item for item in results}
    considered = 0
    promoted = 0
    skipped_low_score = 0
    for pinned in pinned_results[:max_pinned]:
        considered += 1
        chunk_id = str(pinned.get("chunk_id"))
        item = ranked_by_id.get(chunk_id)
        if item is None or not _pinned_result_promotable(item):
            skipped_low_score += 1
            continue
        sources = list(dict.fromkeys([*(item.get("sources") or []), "document"]))
        merged.append({**item, "sources": sources})
        seen.add(chunk_id)
        promoted += 1

    for item in results:
        chunk_id = str(item.get("chunk_id"))
        if chunk_id in seen:
            continue
        merged.append(item)
        seen.add(chunk_id)
        if len(merged) >= top_k:
            break

    if debug_timings is not None:
        debug_timings["graphPinnedConsidered"] = considered
        debug_timings["graphPinnedPromoted"] = promoted
        debug_timings["graphPinnedSkippedLowScore"] = skipped_low_score
        debug_timings["graphPinMinRerankScore"] = graph_pin_min_rerank_score()
        debug_timings["graphPinMinModelScore"] = graph_pin_min_model_score()

    return merged[:top_k]


def rewrite_query_with_llm(query: str, *, model: str, max_rewrites: int) -> dict:
    client = get_chat_client()
    payload = chat_completion_json(
        client,
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": QUERY_REWRITE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Cau hoi goc: {query}\n"
                    f"Hay tra ve toi da {max_rewrites} retrieval_queries bang JSON."
                ),
            },
        ],
    )
    retrieval_queries = payload.get("retrieval_queries", [])
    if not isinstance(retrieval_queries, list):
        retrieval_queries = []
    original_terms = set(normalize_text(query).split())
    filtered_queries: list[str] = []
    legal_terms = {
        "luat",
        "phap",
        "dieu",
        "khoan",
        "hinh",
        "su",
        "toi",
        "thuong",
        "tich",
        "trach",
        "nhiem",
        "xu",
        "ly",
    }
    for item in retrieval_queries:
        value = str(item).strip()
        if not value:
            continue
        normalized_value = normalize_text(value)
        value_terms = set(normalized_value.split())
        if original_terms and not (original_terms & value_terms) and not (legal_terms & value_terms):
            continue
        filtered_queries.append(value)
    return {
        "legal_intent": str(payload.get("legal_intent", "")).strip(),
        "retrieval_queries": deduplicate_queries(filtered_queries[:max_rewrites]),
    }


def build_retrieval_queries(
    query: str,
    *,
    rewrite_mode: str,
    rewrite_model: str,
    max_rewrites: int,
) -> dict:
    issue_plan = extract_legal_issues_with_rules(query)
    local_queries = deduplicate_queries(issue_plan["retrieval_queries"])
    if rewrite_mode == "none":
        return {
            "original_query": query,
            "legal_intent": ", ".join(issue_plan["labels"]),
            "retrieval_queries": limit_retrieval_queries([query, *local_queries]),
            "rewrite_source": "rules_only",
            "legal_issue_confidence": issue_plan["confidence"],
            "legal_issue_labels": issue_plan["labels"],
            "legal_issue_matches": issue_plan["matches"],
        }

    if issue_plan["high_confidence"]:
        return {
            "original_query": query,
            "legal_intent": ", ".join(issue_plan["labels"]),
            "retrieval_queries": limit_retrieval_queries([query, *local_queries]),
            "rewrite_source": "rules_high_confidence",
            "legal_issue_confidence": issue_plan["confidence"],
            "legal_issue_labels": issue_plan["labels"],
            "legal_issue_matches": issue_plan["matches"],
        }

    rewritten = rewrite_query_with_llm(query, model=rewrite_model, max_rewrites=max_rewrites)
    retrieval_queries = limit_retrieval_queries([query, *local_queries, *rewritten["retrieval_queries"]])
    return {
        "original_query": query,
        "legal_intent": rewritten["legal_intent"],
        "retrieval_queries": retrieval_queries or [query],
        "rewrite_source": "llm_with_rule_hints" if local_queries else "llm",
        "legal_issue_confidence": issue_plan["confidence"],
        "legal_issue_labels": issue_plan["labels"],
        "legal_issue_matches": issue_plan["matches"],
    }


def ensure_bm25_index(chunks_path: Path, bm25_index_path: Path) -> dict | SQLiteRetrievalStore:
    sqlite_store_path = default_store_path_for_bm25_index(bm25_index_path)
    sqlite_store = open_store_if_exists(sqlite_store_path)
    if sqlite_store is not None:
        return sqlite_store

    if chunks_path.exists():
        build_sqlite_retrieval_store(chunks_path=chunks_path, output_path=sqlite_store_path)
        return SQLiteRetrievalStore(sqlite_store_path)

    if bm25_index_path.exists():
        return load_index(bm25_index_path)

    payload = build_index_payload(chunks_path)
    save_index(payload, bm25_index_path)
    return payload


def resolve_vector_store_path(vector_dir: Path, manifest: dict) -> Path:
    configured_path = manifest.get("retrieval_store_path")
    if configured_path:
        return Path(configured_path)
    chunks_path = manifest.get("chunks_path")
    if chunks_path:
        return default_store_path_for_chunks(Path(chunks_path))
    return vector_dir / "retrieval_store.sqlite"


def vector_asset_signature(vector_dir: Path, manifest: dict) -> tuple[tuple[str, int, int], ...]:
    paths = [
        vector_dir / "vector_manifest.json",
        vector_dir / "faiss.index",
    ]
    sqlite_store_path = resolve_vector_store_path(vector_dir, manifest)
    if sqlite_store_path.exists():
        paths.append(sqlite_store_path)
    else:
        paths.append(vector_dir / "vector_metadata.json")

    signature: list[tuple[str, int, int]] = []
    for path in paths:
        stat = path.stat()
        signature.append((str(path.resolve()), stat.st_mtime_ns, stat.st_size))
    return tuple(signature)


def load_vector_assets_uncached(vector_dir: Path) -> tuple[dict, list[dict] | SQLiteRetrievalStore, faiss.Index]:
    manifest = json.loads((vector_dir / "vector_manifest.json").read_text(encoding="utf-8"))
    sqlite_store_path = resolve_vector_store_path(vector_dir, manifest)
    metadata_store = open_store_if_exists(sqlite_store_path)
    if metadata_store is not None:
        metadata: list[dict] | SQLiteRetrievalStore = metadata_store
    else:
        metadata = json.loads((vector_dir / "vector_metadata.json").read_text(encoding="utf-8"))
    index = faiss.read_index(str(vector_dir / "faiss.index"))
    return manifest, metadata, index


def load_vector_assets(
    vector_dir: Path,
    debug_timings: dict[str, Any] | None = None,
) -> tuple[dict, list[dict] | SQLiteRetrievalStore, faiss.Index]:
    started = time.perf_counter()
    vector_dir = vector_dir.resolve()
    manifest = json.loads((vector_dir / "vector_manifest.json").read_text(encoding="utf-8"))
    signature = vector_asset_signature(vector_dir, manifest)

    with _VECTOR_ASSET_CACHE_LOCK:
        cached = _VECTOR_ASSET_CACHE.get(vector_dir)
        if cached and cached[0] == signature:
            if debug_timings is not None:
                debug_timings["vectorAssetCacheHit"] = int(debug_timings.get("vectorAssetCacheHit", 0)) + 1
                debug_timings["vectorAssetCacheHitLastMs"] = int((time.perf_counter() - started) * 1000)
            return cached[1]

        assets = load_vector_assets_uncached(vector_dir)
        stale = _VECTOR_ASSET_CACHE.get(vector_dir)
        if stale:
            stale_metadata = stale[1][1]
            if isinstance(stale_metadata, SQLiteRetrievalStore):
                stale_metadata.close()
        _VECTOR_ASSET_CACHE[vector_dir] = (signature, assets)
        if debug_timings is not None:
            debug_timings["vectorAssetCacheMiss"] = int(debug_timings.get("vectorAssetCacheMiss", 0)) + 1
            debug_timings["vectorAssetCacheMissLastMs"] = int((time.perf_counter() - started) * 1000)
        return assets



def load_atlas_manifest(vector_dir: Path) -> dict:
    manifest_path = vector_dir / "atlas_manifest.json"
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def normalize_query_for_faiss(vector: np.ndarray) -> np.ndarray:
    normalized = vector.reshape(1, -1)
    faiss.normalize_L2(normalized)
    return normalized


def faiss_vector_search(
    query: str,
    vector_dir: Path,
    top_k: int,
    embedding_model: str | None = None,
    debug_timings: dict[str, Any] | None = None,
) -> list[dict]:
    load_started = time.perf_counter()
    manifest, metadata, index = load_vector_assets(vector_dir, debug_timings=debug_timings)
    load_ms = int((time.perf_counter() - load_started) * 1000)
    model = manifest.get("embedding_model") or embedding_model or DEFAULT_EMBEDDING_MODEL
    provider = manifest.get("embedding_provider") or embedding_provider()
    embed_started = time.perf_counter()
    raw_query_vector = np.array(embed_query_text(query, model=model, provider=provider), dtype="float32")
    embed_ms = int((time.perf_counter() - embed_started) * 1000)
    query_vector = normalize_query_for_faiss(raw_query_vector)
    search_started = time.perf_counter()
    scores, indices = index.search(query_vector, top_k)
    search_ms = int((time.perf_counter() - search_started) * 1000)
    metadata_started = time.perf_counter()

    results: list[dict] = []
    metadata_by_index = (
        metadata.get_metadata_by_vector_indices(int(idx) for idx in indices[0] if idx >= 0)
        if isinstance(metadata, SQLiteRetrievalStore)
        else {}
    )
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        item = metadata_by_index.get(int(idx)) if isinstance(metadata, SQLiteRetrievalStore) else metadata[idx]
        if not item:
            continue
        results.append(
            {
                "score": float(score),
                "chunk_id": item["chunk_id"],
                "source_file": item["source_file"],
                "vbpl_id": item.get("vbpl_id"),
                "doc_number": item.get("doc_number"),
                "doc_type": item.get("doc_type"),
                "source_url": item.get("source_url"),
                "issue_date": item.get("issue_date"),
                "article_number": item.get("article_number"),
                "clause_number": item.get("clause_number"),
                "point_number": item.get("point_number"),
                "parent_chunk_id": item.get("parent_chunk_id"),
                "parent_context_text": item.get("parent_context_text"),
                "merged_short_chunk": item.get("merged_short_chunk"),
                "merged_chunk_ids": item.get("merged_chunk_ids"),
                "document_title": item.get("document_title"),
                "chapter": item.get("chapter"),
                "section": item.get("section"),
                "target_article": item.get("target_article"),
                "preview": item["text"][:400],
                "text": item["text"],
                "search_source": "vector",
            }
        )
    if debug_timings is not None:
        vector_queries = debug_timings.setdefault("vectorQueries", [])
        if isinstance(vector_queries, list):
            vector_queries.append(
                {
                    "ms": load_ms + embed_ms + search_ms + int((time.perf_counter() - metadata_started) * 1000),
                    "loadMs": load_ms,
                    "embedMs": embed_ms,
                    "searchMs": search_ms,
                    "metadataMs": int((time.perf_counter() - metadata_started) * 1000),
                    "chars": len(query),
                    "results": len(results),
                    "query": query[:120],
                }
            )
    return results


def query_bm25_index(index_payload: dict | SQLiteRetrievalStore, query: str, top_k: int) -> list[dict]:
    if isinstance(index_payload, SQLiteRetrievalStore):
        return index_payload.query_bm25(query, top_k)
    return query_index(index_payload, query, top_k)


def atlas_backend_search(
    query: str,
    *,
    vector_dir: Path,
    top_k: int,
    embedding_model: str,
    atlas_uri: str | None,
    atlas_db: str | None,
    atlas_collection: str | None,
    atlas_vector_index: str | None,
) -> list[dict]:
    atlas_manifest = load_atlas_manifest(vector_dir)
    collection, config = get_atlas_collection(
        uri=atlas_uri,
        database=atlas_db or atlas_manifest.get("database"),
        collection=atlas_collection or atlas_manifest.get("collection"),
        vector_index=atlas_vector_index or atlas_manifest.get("vector_index"),
    )
    provider = atlas_manifest.get("embedding_provider") or embedding_provider()
    model = atlas_manifest.get("embedding_model") or embedding_model or DEFAULT_EMBEDDING_MODEL
    query_vector = embed_query_text(query, model=model, provider=provider)
    documents = atlas_vector_search(
        collection,
        vector_index=config["vector_index"],
        query_vector=query_vector,
        top_k=top_k,
    )

    results: list[dict] = []
    for item in documents:
        results.append(
            {
                "score": float(item["score"]),
                "chunk_id": item["chunk_id"],
                "source_file": item["source_file"],
                "vbpl_id": item.get("vbpl_id"),
                "doc_number": item.get("doc_number"),
                "doc_type": item.get("doc_type"),
                "source_url": item.get("source_url"),
                "issue_date": item.get("issue_date"),
                "article_number": item.get("article_number"),
                "clause_number": item.get("clause_number"),
                "point_number": item.get("point_number"),
                "parent_chunk_id": item.get("parent_chunk_id"),
                "parent_context_text": item.get("parent_context_text"),
                "merged_short_chunk": item.get("merged_short_chunk"),
                "merged_chunk_ids": item.get("merged_chunk_ids"),
                "document_title": item.get("document_title"),
                "chapter": item.get("chapter"),
                "section": item.get("section"),
                "target_article": item.get("target_article"),
                "preview": item["text"][:400],
                "text": item["text"],
                "search_source": "vector",
            }
        )
    return results


def vector_search(
    query: str,
    *,
    vector_backend: str,
    vector_dir: Path,
    top_k: int,
    embedding_model: str,
    atlas_uri: str | None,
    atlas_db: str | None,
    atlas_collection: str | None,
    atlas_vector_index: str | None,
    debug_timings: dict[str, Any] | None = None,
) -> list[dict]:
    if vector_backend == "atlas":
        return atlas_backend_search(
            query,
            vector_dir=vector_dir,
            top_k=top_k,
            embedding_model=embedding_model,
            atlas_uri=atlas_uri,
            atlas_db=atlas_db,
            atlas_collection=atlas_collection,
            atlas_vector_index=atlas_vector_index,
        )
    return faiss_vector_search(query, vector_dir, top_k, embedding_model=embedding_model, debug_timings=debug_timings)


def safe_faiss_vector_search(query: str, vector_dir: Path, top_k: int) -> list[dict]:
    try:
        return faiss_vector_search(query, vector_dir, top_k)
    except Exception:
        return []


def reciprocal_rank_fusion(*ranked_lists: list[dict], candidate_k: int, k: int = 60) -> list[dict]:
    merged: dict[str, dict] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, start=1):
            chunk_id = item["chunk_id"]
            if chunk_id not in merged:
                merged[chunk_id] = {
                    **item,
                    "rrf_score": 0.0,
                    "sources": [item.get("search_source", "unknown")],
                }
            else:
                existing_sources = merged[chunk_id].setdefault("sources", [])
                source = item.get("search_source", "unknown")
                if source not in existing_sources:
                    existing_sources.append(source)
                if "text" in item and "text" not in merged[chunk_id]:
                    merged[chunk_id]["text"] = item["text"]
            merged[chunk_id]["rrf_score"] += 1.0 / (k + rank)

    results = sorted(merged.values(), key=lambda item: item["rrf_score"], reverse=True)
    return results[:candidate_k]


def finalize_single_source_results(results: list[dict], *, top_k: int) -> list[dict]:
    finalized: list[dict] = []
    for rank, item in enumerate(results[:top_k], start=1):
        finalized.append(
            {
                **item,
                "rrf_score": 1.0 / (60 + rank),
                "sources": [item.get("search_source", "unknown")],
            }
        )
    return finalized


def hybrid_search(
    query: str,
    *,
    retrieval_queries: list[str] | None,
    chunks_path: Path,
    bm25_index_path: Path,
    vector_dir: Path,
    retrieval_mode: str,
    vector_backend: str,
    embedding_model: str,
    atlas_uri: str | None,
    atlas_db: str | None,
    atlas_collection: str | None,
    atlas_vector_index: str | None,
    bm25_top_k: int,
    vector_top_k: int,
    final_top_k: int,
    additional_bm25_sources: list[tuple[Path, Path]] | None = None,
    additional_vector_dirs: list[Path] | None = None,
    legal_issue_labels: list[str] | None = None,
    legal_issue_matches: list[dict[str, Any]] | None = None,
    debug_timings: dict[str, Any] | None = None,
) -> list[dict]:
    retrieval_started = time.perf_counter()
    graph_plan = expand_with_neo4j_graph(issue_labels=legal_issue_labels or [], debug_timings=debug_timings)
    active_queries = limit_retrieval_queries([*(retrieval_queries or [query]), *graph_plan.get("queries", [])])
    candidate_k = max(final_top_k * 8, final_top_k, 40)
    rerank_k = max(final_top_k * 3, final_top_k, 12)
    bm25_sources = [(chunks_path, bm25_index_path), *(additional_bm25_sources or [])]
    pinned_started = time.perf_counter()
    pinned_results = [
        *graph_plan.get("pinned_results", []),
        *pinned_legal_issue_chunks(
            [source_chunks_path for source_chunks_path, _ in bm25_sources],
            legal_issue_matches,
        ),
        *pinned_document_chunks([source_chunks_path for source_chunks_path, _ in bm25_sources], active_queries),
    ]
    if debug_timings is not None:
        debug_timings["retrievalPinned"] = int((time.perf_counter() - pinned_started) * 1000)
        debug_timings["retrievalActiveQueries"] = len(active_queries)
        debug_timings["retrievalBm25Sources"] = len(bm25_sources)
        debug_timings["retrievalExtraVectorDirs"] = len(additional_vector_dirs or [])
        debug_timings["graphRetrievalEnabled"] = bool(graph_plan.get("enabled"))

    bm25_ranked_lists: list[list[dict]] = []
    bm25_started = time.perf_counter()
    if retrieval_mode in {"bm25", "hybrid"}:
        if pinned_results:
            bm25_ranked_lists.append(pinned_results)
        for source_chunks_path, source_index_path in bm25_sources:
            if not source_chunks_path.exists():
                continue
            bm25_index = ensure_bm25_index(source_chunks_path, source_index_path)
            for retrieval_query in active_queries:
                bm25_query_started = time.perf_counter()
                bm25_results = query_bm25_index(bm25_index, retrieval_query, bm25_top_k)
                if debug_timings is not None:
                    bm25_queries = debug_timings.setdefault("bm25Queries", [])
                    if isinstance(bm25_queries, list):
                        bm25_queries.append(
                            {
                                "ms": int((time.perf_counter() - bm25_query_started) * 1000),
                                "chars": len(retrieval_query),
                                "results": len(bm25_results),
                                "query": retrieval_query[:120],
                            }
                        )
                for item in bm25_results:
                    item["search_source"] = "bm25"
                bm25_ranked_lists.append(bm25_results)
    if debug_timings is not None:
        debug_timings["retrievalBm25"] = int((time.perf_counter() - bm25_started) * 1000)

    vector_ranked_lists: list[list[dict]] = []
    vector_started = time.perf_counter()
    if retrieval_mode in {"vector", "hybrid"}:
        if retrieval_mode == "vector" and pinned_results:
            vector_ranked_lists.append(pinned_results)
        for retrieval_query in active_queries:
            vector_results = vector_search(
                retrieval_query,
                vector_backend=vector_backend,
                vector_dir=vector_dir,
                top_k=vector_top_k,
                embedding_model=embedding_model,
                atlas_uri=atlas_uri,
                atlas_db=atlas_db,
                atlas_collection=atlas_collection,
                atlas_vector_index=atlas_vector_index,
                debug_timings=debug_timings,
            )
            vector_ranked_lists.append(vector_results)
            for extra_vector_dir in additional_vector_dirs or []:
                if not (extra_vector_dir / "faiss.index").exists():
                    continue
                extra_vector_results = safe_faiss_vector_search(retrieval_query, extra_vector_dir, vector_top_k)
                vector_ranked_lists.append(extra_vector_results)
    if debug_timings is not None:
        debug_timings["retrievalVector"] = int((time.perf_counter() - vector_started) * 1000)

    fusion_started = time.perf_counter()
    if retrieval_mode == "vector":
        if len(vector_ranked_lists) <= 1:
            candidates = finalize_single_source_results(vector_ranked_lists[0] if vector_ranked_lists else [], top_k=candidate_k)
        else:
            candidates = reciprocal_rank_fusion(*vector_ranked_lists, candidate_k=candidate_k)
        reranked = rerank_candidates(
            candidates,
            queries=active_queries,
            top_k=rerank_k,
            legal_issue_matches=legal_issue_matches,
            debug_timings=debug_timings,
        )
        filtered = filter_reranked_results(reranked, top_k=final_top_k, debug_timings=debug_timings)
        results = prioritize_pinned_results(filtered, pinned_results, top_k=final_top_k, debug_timings=debug_timings)
        if debug_timings is not None:
            debug_timings["retrievalFusionRerank"] = int((time.perf_counter() - fusion_started) * 1000)
            debug_timings["retrievalTotal"] = int((time.perf_counter() - retrieval_started) * 1000)
        return results
    if retrieval_mode == "bm25":
        if len(bm25_ranked_lists) <= 1:
            candidates = finalize_single_source_results(bm25_ranked_lists[0] if bm25_ranked_lists else [], top_k=candidate_k)
        else:
            candidates = reciprocal_rank_fusion(*bm25_ranked_lists, candidate_k=candidate_k)
        reranked = rerank_candidates(
            candidates,
            queries=active_queries,
            top_k=rerank_k,
            legal_issue_matches=legal_issue_matches,
            debug_timings=debug_timings,
        )
        filtered = filter_reranked_results(reranked, top_k=final_top_k, debug_timings=debug_timings)
        results = prioritize_pinned_results(filtered, pinned_results, top_k=final_top_k, debug_timings=debug_timings)
        if debug_timings is not None:
            debug_timings["retrievalFusionRerank"] = int((time.perf_counter() - fusion_started) * 1000)
            debug_timings["retrievalTotal"] = int((time.perf_counter() - retrieval_started) * 1000)
        return results
    candidates = reciprocal_rank_fusion(*bm25_ranked_lists, *vector_ranked_lists, candidate_k=candidate_k)
    reranked = rerank_candidates(
        candidates,
        queries=active_queries,
        top_k=rerank_k,
        legal_issue_matches=legal_issue_matches,
        debug_timings=debug_timings,
    )
    filtered = filter_reranked_results(reranked, top_k=final_top_k, debug_timings=debug_timings)
    results = prioritize_pinned_results(filtered, pinned_results, top_k=final_top_k, debug_timings=debug_timings)
    if debug_timings is not None:
        debug_timings["retrievalFusionRerank"] = int((time.perf_counter() - fusion_started) * 1000)
        debug_timings["retrievalTotal"] = int((time.perf_counter() - retrieval_started) * 1000)
    return results


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Retrieval: BM25, vector-only, hoac hybrid")
    parser.add_argument("query", help="Natural language legal query")
    parser.add_argument("--chunks", default="output/vbpl_laws_active_partial/all_chunks.jsonl", help="Path to all_chunks.jsonl")
    parser.add_argument("--bm25-index", default="output/vbpl_laws_active_partial/retrieval/bm25_index.json", help="Path to BM25 index JSON")
    parser.add_argument("--vector-dir", default=default_vector_dir(), help="Thu muc chua FAISS index va metadata")
    parser.add_argument("--retrieval-mode", choices=["hybrid", "vector", "bm25"], default="hybrid", help="Che do retrieval")
    parser.add_argument("--query-rewrite-mode", choices=["none", "llm"], default="none", help="Che do rewrite query truoc retrieval")
    parser.add_argument("--query-rewrite-model", default=DEFAULT_QUERY_REWRITE_MODEL, help="LLM model dung de rewrite query")
    parser.add_argument("--query-rewrite-count", type=int, default=4, help="So truy van rewrite toi da")
    parser.add_argument("--vector-backend", choices=["faiss", "atlas"], default="faiss", help="Backend vector retrieval")
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL, help="Embedding model cho vector query")
    parser.add_argument("--atlas-uri", default=None, help="MongoDB Atlas connection string")
    parser.add_argument("--atlas-db", default=None, help="Ten database tren Atlas")
    parser.add_argument("--atlas-collection", default=None, help="Ten collection tren Atlas")
    parser.add_argument("--atlas-vector-index", default=None, help="Ten Atlas Vector Search index")
    parser.add_argument("--bm25-top-k", type=int, default=10, help="So ket qua BM25 truoc khi tron")
    parser.add_argument("--vector-top-k", type=int, default=10, help="So ket qua vector truoc khi tron")
    parser.add_argument("--top-k", type=int, default=5, help="So ket qua cuoi cung")
    args = parser.parse_args()

    retrieval_plan = build_retrieval_queries(
        args.query,
        rewrite_mode=args.query_rewrite_mode,
        rewrite_model=args.query_rewrite_model,
        max_rewrites=args.query_rewrite_count,
    )

    results = hybrid_search(
        args.query,
        retrieval_queries=retrieval_plan["retrieval_queries"],
        chunks_path=Path(args.chunks),
        bm25_index_path=Path(args.bm25_index),
        vector_dir=Path(args.vector_dir),
        retrieval_mode=args.retrieval_mode,
        vector_backend=args.vector_backend,
        embedding_model=args.embedding_model,
        atlas_uri=args.atlas_uri,
        atlas_db=args.atlas_db,
        atlas_collection=args.atlas_collection,
        atlas_vector_index=args.atlas_vector_index,
        bm25_top_k=args.bm25_top_k,
        vector_top_k=args.vector_top_k,
        final_top_k=args.top_k,
        legal_issue_labels=retrieval_plan.get("legal_issue_labels", []),
        legal_issue_matches=retrieval_plan.get("legal_issue_matches", []),
    )
    print(
        json.dumps(
            {
                "query": args.query,
                "legal_intent": retrieval_plan["legal_intent"],
                "retrieval_queries": retrieval_plan["retrieval_queries"],
                "rewrite_source": retrieval_plan.get("rewrite_source"),
                "legal_issue_confidence": retrieval_plan.get("legal_issue_confidence"),
                "legal_issue_labels": retrieval_plan.get("legal_issue_labels", []),
                "legal_issue_matches": retrieval_plan.get("legal_issue_matches", []),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
