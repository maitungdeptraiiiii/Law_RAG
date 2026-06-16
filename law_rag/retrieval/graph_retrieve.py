from __future__ import annotations

import os
import time
from typing import Any

from .neo4j_store import Neo4jLegalGraphStore, graph_retrieval_enabled


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _article_query(row: dict[str, Any]) -> str:
    article_number = str(row.get("article_number") or "").strip()
    document_title = str(row.get("document_title") or "").strip()
    if article_number and document_title:
        return f"Điều {article_number} {document_title}"
    if article_number:
        return f"Điều {article_number}"
    return document_title


def _row_to_pinned_result(row: dict[str, Any]) -> dict[str, Any] | None:
    chunk_id = row.get("chunk_id")
    text = str(row.get("text") or "")
    if not chunk_id or not text:
        return None

    relation = str(row.get("relation") or "")
    if relation != "PREFERRED_ARTICLE" and not _env_enabled("GRAPH_PIN_DISTINGUISH", default=False):
        return None

    score = 1.0 if relation == "PREFERRED_ARTICLE" else 0.72
    return {
        "score": score,
        "chunk_id": chunk_id,
        "source_file": row.get("source_file") or "",
        "doc_number": row.get("doc_number"),
        "document_title": row.get("document_title"),
        "source_url": row.get("source_url"),
        "article_number": row.get("article_number"),
        "clause_number": row.get("clause_number"),
        "point_number": row.get("point_number"),
        "target_article": None,
        "preview": text[:400],
        "text": text,
        "search_source": "graph",
        "graph_relation": relation,
        "graph_issue_label": row.get("issue_label"),
    }


def expand_with_neo4j_graph(
    *,
    issue_labels: list[str],
    debug_timings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not graph_retrieval_enabled() or not issue_labels:
        return {"queries": [], "pinned_results": [], "rows": [], "enabled": graph_retrieval_enabled()}

    started = time.perf_counter()
    try:
        store = Neo4jLegalGraphStore()
        try:
            rows = store.issue_expansion(issue_labels)
        finally:
            store.close()
    except Exception as exc:
        if debug_timings is not None:
            debug_timings["graphRetrievalError"] = str(exc)
            debug_timings["graphRetrievalMs"] = int((time.perf_counter() - started) * 1000)
        return {"queries": [], "pinned_results": [], "rows": [], "enabled": True, "error": str(exc)}

    queries: list[str] = []
    pinned_results: list[dict[str, Any]] = []
    seen_pinned: set[str] = set()
    max_pinned = max(0, _env_int("GRAPH_MAX_PINNED", 1))
    for row in rows:
        issue_queries = row.get("issue_queries")
        if isinstance(issue_queries, list):
            queries.extend(str(item) for item in issue_queries if str(item).strip())
        article_query = _article_query(row)
        if article_query:
            relation = str(row.get("relation") or "").lower()
            if relation == "distinguish_from":
                article_query = f"{article_query} phân biệt với vấn đề pháp lý chính"
            queries.append(article_query)

        pinned = _row_to_pinned_result(row)
        if pinned is None:
            continue
        chunk_id = str(pinned["chunk_id"])
        if chunk_id in seen_pinned:
            continue
        if len(pinned_results) >= max_pinned:
            continue
        seen_pinned.add(chunk_id)
        pinned_results.append(pinned)

    if debug_timings is not None:
        debug_timings["graphRetrievalMs"] = int((time.perf_counter() - started) * 1000)
        debug_timings["graphRetrievalRows"] = len(rows)
        debug_timings["graphRetrievalPinned"] = len(pinned_results)
        debug_timings["graphRetrievalQueries"] = len(queries)

    return {
        "queries": queries,
        "pinned_results": pinned_results,
        "rows": rows,
        "enabled": True,
    }
