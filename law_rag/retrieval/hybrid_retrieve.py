from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import faiss
import numpy as np

from ..core.embedding_client import DEFAULT_EMBEDDING_MODEL, embed_query as embed_query_text, embedding_provider
from ..core.env_loader import load_project_env
from ..core.llm_client import chat_completion_json, get_chat_client
from ..core.runtime_config import default_vector_dir, query_rewrite_model
from .atlas_vector_store import atlas_vector_search, get_atlas_collection
from .retrieve_chunks import (
    build_index_payload,
    load_index,
    query_index,
    save_index,
)


DEFAULT_QUERY_REWRITE_MODEL = query_rewrite_model()
TOKEN_RE = re.compile(r"\w+", re.UNICODE)
ARTICLE_RE = re.compile(r"\b(?:điều|dieu|article)\s+(\d+[a-z]?)\b", re.IGNORECASE)
LEGAL_NUMBER_RE = re.compile(r"\b\d{1,4}\s*[/\-]\s*\d{4}\s*[/\-]\s*[A-Za-zĐđ]+[A-Za-z0-9Đđ]*\b")

COLLOQUIAL_QUERY_EXPANSIONS: list[tuple[tuple[str, ...], list[str]]] = [
    (
        ("đánh", "thương"),
        [
            "cố ý gây thương tích hoặc gây tổn hại cho sức khỏe của người khác Điều 134 Bộ luật Hình sự",
            "tỷ lệ tổn thương cơ thể dùng hung khí côn đồ Điều 134",
        ],
    ),
    (
        ("gây thương tích",),
        [
            "cố ý gây thương tích hoặc gây tổn hại cho sức khỏe của người khác Điều 134 Bộ luật Hình sự",
        ],
    ),
    (
        ("lấy trộm",),
        [
            "trộm cắp tài sản giá trị tài sản Điều 173 Bộ luật Hình sự",
        ],
    ),
    (
        ("trộm",),
        [
            "trộm cắp tài sản giá trị tài sản Điều 173 Bộ luật Hình sự",
        ],
    ),
    (
        ("lãi", "vay"),
        [
            "lãi suất vay do các bên thỏa thuận không vượt quá 20% một năm Điều 468 Bộ luật Dân sự",
        ],
    ),
    (
        ("nghỉ việc",),
        [
            "người lao động đơn phương chấm dứt hợp đồng lao động thời hạn báo trước Điều 35 Bộ luật Lao động",
        ],
    ),
    (
        ("con nuôi", "thừa kế"),
        [
            "quan hệ thừa kế giữa con nuôi và cha nuôi mẹ nuôi Điều 653 Bộ luật Dân sự",
            "người thừa kế theo pháp luật hàng thừa kế thứ nhất Điều 651 Bộ luật Dân sự",
        ],
    ),
    (
        ("bạo lực gia đình",),
        [
            "hành vi bạo lực gia đình Điều 3 Luật Phòng chống bạo lực gia đình",
            "quyền của người bị bạo lực gia đình Điều 9 Luật Phòng chống bạo lực gia đình",
        ],
    ),
    (
        ("công chứng", "đất"),
        [
            "phạm vi công chứng giao dịch bất động sản Điều 44 Luật Công chứng",
        ],
    ),
    (
        ("mua đất", "công chứng"),
        [
            "phạm vi công chứng giao dịch bất động sản Điều 44 Luật Công chứng",
        ],
    ),
    (
        ("kiện", "tòa"),
        [
            "thẩm quyền của Tòa án theo lãnh thổ nơi bị đơn cư trú Điều 39 Bộ luật Tố tụng dân sự",
        ],
    ),
    (
        ("nộp đơn", "tòa"),
        [
            "thẩm quyền của Tòa án theo lãnh thổ nơi bị đơn cư trú Điều 39 Bộ luật Tố tụng dân sự",
        ],
    ),
    (
        ("mua hàng", "lỗi"),
        [
            "quyền của người tiêu dùng yêu cầu bồi thường sản phẩm hàng hóa dịch vụ không đúng cam kết Điều 4",
        ],
    ),
    (
        ("bảo hiểm xã hội", "15 năm"),
        [
            "điều kiện hưởng lương hưu thời gian đóng bảo hiểm xã hội từ đủ 15 năm Điều 64",
        ],
    ),
    (
        ("lương hưu", "15 năm"),
        [
            "điều kiện hưởng lương hưu thời gian đóng bảo hiểm xã hội từ đủ 15 năm Điều 64",
        ],
    ),
]


load_project_env()


QUERY_REWRITE_SYSTEM_PROMPT = """Ban la bo chuyen doi query cho he thong retrieval luat Viet Nam.
Nhiem vu: doi cau hoi doi thuong cua nguoi dung thanh mot nhom truy van retrieval mang ngon ngu phap ly.
Yeu cau:
1. Giu nguyen y nghia cau hoi.
2. Rut ra hanh vi, hau qua, toi danh hoac che dinh phap ly gan nhat.
3. Tao 3-5 truy van retrieval ngan, ro, uu tien thuat ngu phap ly.
4. Neu co the, them mot truy van co dang Dieu/Khoan neu rat kha nang lien quan.
5. Chi tra JSON hop le voi 2 khoa: legal_intent va retrieval_queries.
"""


def deduplicate_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for query in queries:
        normalized = " ".join(query.split())
        if not normalized:
            continue
        lowered = normalized.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        ordered.append(normalized)
    return ordered


def build_rule_based_query_expansions(query: str) -> list[str]:
    normalized = normalize_text(query)
    expansions: list[str] = []
    for triggers, generated_queries in COLLOQUIAL_QUERY_EXPANSIONS:
        if all(normalize_text(trigger) in normalized for trigger in triggers):
            expansions.extend(generated_queries)
    return expansions


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
        for line in chunks_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            chunk = json.loads(line)
            source_file = str(chunk.get("source_file") or "")
            normalized_source = normalize_identifier(source_file)
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
                    "article_number": chunk.get("article_number"),
                    "clause_number": chunk.get("clause_number"),
                    "point_number": chunk.get("point_number"),
                    "document_title": chunk.get("document_title"),
                    "chapter": chunk.get("chapter"),
                    "target_article": chunk.get("target_article"),
                    "preview": text[:400],
                    "text": text,
                    "search_source": "document",
                }
            )
    return pinned


def rerank_results(results: list[dict], *, queries: list[str], top_k: int) -> list[dict]:
    if not results:
        return []

    max_rrf = max(float(item.get("rrf_score") or 0.0) for item in results) or 1.0
    reranked: list[dict] = []
    for item in results:
        rrf_component = float(item.get("rrf_score") or 0.0) / max_rrf
        lexical_component = lexical_overlap_score(queries, item)
        article_component = article_match_score(queries, item)
        coverage_component = source_coverage_score(item)
        pinned_component = 1.0 if "document" in set(item.get("sources") or []) else 0.0
        rerank_score = (
            0.45 * rrf_component
            + 0.22 * lexical_component
            + 0.13 * article_component
            + 0.05 * coverage_component
            + 0.15 * pinned_component
        )
        reranked.append(
            {
                **item,
                "rerank_score": round(rerank_score, 6),
                "rerank_features": {
                    "rrf": round(rrf_component, 6),
                    "lexical_overlap": round(lexical_component, 6),
                    "article_match": round(article_component, 6),
                    "source_coverage": round(coverage_component, 6),
                    "pinned_document": round(pinned_component, 6),
                },
            }
        )

    reranked.sort(key=lambda item: item["rerank_score"], reverse=True)
    return reranked[:top_k]


def prioritize_pinned_results(results: list[dict], pinned_results: list[dict], *, top_k: int, max_pinned: int = 3) -> list[dict]:
    if not pinned_results:
        return results[:top_k]

    merged: list[dict] = []
    seen: set[str] = set()
    ranked_by_id = {str(item.get("chunk_id")): item for item in results}
    for pinned in pinned_results[:max_pinned]:
        chunk_id = str(pinned.get("chunk_id"))
        item = ranked_by_id.get(chunk_id, pinned)
        sources = list(dict.fromkeys([*(item.get("sources") or []), "document"]))
        merged.append({**item, "sources": sources})
        seen.add(chunk_id)

    for item in results:
        chunk_id = str(item.get("chunk_id"))
        if chunk_id in seen:
            continue
        merged.append(item)
        seen.add(chunk_id)
        if len(merged) >= top_k:
            break

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
    return {
        "legal_intent": str(payload.get("legal_intent", "")).strip(),
        "retrieval_queries": deduplicate_queries([str(item) for item in retrieval_queries][:max_rewrites]),
    }


def build_retrieval_queries(
    query: str,
    *,
    rewrite_mode: str,
    rewrite_model: str,
    max_rewrites: int,
) -> dict:
    rule_based_queries = build_rule_based_query_expansions(query)
    if rewrite_mode == "none":
        return {
            "original_query": query,
            "legal_intent": "",
            "retrieval_queries": deduplicate_queries([query, *rule_based_queries]),
        }

    rewritten = rewrite_query_with_llm(query, model=rewrite_model, max_rewrites=max_rewrites)
    retrieval_queries = deduplicate_queries([query, *rule_based_queries, *rewritten["retrieval_queries"]])
    return {
        "original_query": query,
        "legal_intent": rewritten["legal_intent"],
        "retrieval_queries": retrieval_queries or [query],
    }


def ensure_bm25_index(chunks_path: Path, bm25_index_path: Path) -> dict:
    if bm25_index_path.exists():
        return load_index(bm25_index_path)

    payload = build_index_payload(chunks_path)
    save_index(payload, bm25_index_path)
    return payload


def load_vector_assets(vector_dir: Path) -> tuple[dict, list[dict], faiss.Index]:
    manifest = json.loads((vector_dir / "vector_manifest.json").read_text(encoding="utf-8"))
    metadata = json.loads((vector_dir / "vector_metadata.json").read_text(encoding="utf-8"))
    index = faiss.read_index(str(vector_dir / "faiss.index"))
    return manifest, metadata, index


def load_atlas_manifest(vector_dir: Path) -> dict:
    manifest_path = vector_dir / "atlas_manifest.json"
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def normalize_query_for_faiss(vector: np.ndarray) -> np.ndarray:
    normalized = vector.reshape(1, -1)
    faiss.normalize_L2(normalized)
    return normalized


def faiss_vector_search(query: str, vector_dir: Path, top_k: int, embedding_model: str | None = None) -> list[dict]:
    manifest, metadata, index = load_vector_assets(vector_dir)
    model = manifest.get("embedding_model") or embedding_model or DEFAULT_EMBEDDING_MODEL
    provider = manifest.get("embedding_provider") or embedding_provider()
    raw_query_vector = np.array(embed_query_text(query, model=model, provider=provider), dtype="float32")
    query_vector = normalize_query_for_faiss(raw_query_vector)
    scores, indices = index.search(query_vector, top_k)

    results: list[dict] = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        item = metadata[idx]
        results.append(
            {
                "score": float(score),
                "chunk_id": item["chunk_id"],
                "source_file": item["source_file"],
                "article_number": item.get("article_number"),
                "clause_number": item.get("clause_number"),
                "point_number": item.get("point_number"),
                "document_title": item.get("document_title"),
                "chapter": item.get("chapter"),
                "target_article": item.get("target_article"),
                "preview": item["text"][:400],
                "text": item["text"],
                "search_source": "vector",
            }
        )
    return results


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
                "article_number": item.get("article_number"),
                "clause_number": item.get("clause_number"),
                "point_number": item.get("point_number"),
                "document_title": item.get("document_title"),
                "chapter": item.get("chapter"),
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
    return faiss_vector_search(query, vector_dir, top_k, embedding_model=embedding_model)


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
) -> list[dict]:
    active_queries = retrieval_queries or [query]
    candidate_k = max(final_top_k * 4, final_top_k, 20)
    bm25_sources = [(chunks_path, bm25_index_path), *(additional_bm25_sources or [])]
    pinned_results = pinned_document_chunks([source_chunks_path for source_chunks_path, _ in bm25_sources], active_queries)

    bm25_ranked_lists: list[list[dict]] = []
    if retrieval_mode in {"bm25", "hybrid"}:
        if pinned_results:
            bm25_ranked_lists.append(pinned_results)
        for source_chunks_path, source_index_path in bm25_sources:
            if not source_chunks_path.exists():
                continue
            bm25_index = ensure_bm25_index(source_chunks_path, source_index_path)
            for retrieval_query in active_queries:
                bm25_results = query_index(bm25_index, retrieval_query, bm25_top_k)
                for item in bm25_results:
                    item["search_source"] = "bm25"
                bm25_ranked_lists.append(bm25_results)

    vector_ranked_lists: list[list[dict]] = []
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
            )
            vector_ranked_lists.append(vector_results)
            for extra_vector_dir in additional_vector_dirs or []:
                if not (extra_vector_dir / "faiss.index").exists():
                    continue
                extra_vector_results = safe_faiss_vector_search(retrieval_query, extra_vector_dir, vector_top_k)
                vector_ranked_lists.append(extra_vector_results)

    if retrieval_mode == "vector":
        if len(vector_ranked_lists) <= 1:
            candidates = finalize_single_source_results(vector_ranked_lists[0] if vector_ranked_lists else [], top_k=candidate_k)
        else:
            candidates = reciprocal_rank_fusion(*vector_ranked_lists, candidate_k=candidate_k)
        reranked = rerank_results(candidates, queries=active_queries, top_k=final_top_k)
        return prioritize_pinned_results(reranked, pinned_results, top_k=final_top_k)
    if retrieval_mode == "bm25":
        if len(bm25_ranked_lists) <= 1:
            candidates = finalize_single_source_results(bm25_ranked_lists[0] if bm25_ranked_lists else [], top_k=candidate_k)
        else:
            candidates = reciprocal_rank_fusion(*bm25_ranked_lists, candidate_k=candidate_k)
        reranked = rerank_results(candidates, queries=active_queries, top_k=final_top_k)
        return prioritize_pinned_results(reranked, pinned_results, top_k=final_top_k)
    candidates = reciprocal_rank_fusion(*bm25_ranked_lists, *vector_ranked_lists, candidate_k=candidate_k)
    reranked = rerank_results(candidates, queries=active_queries, top_k=final_top_k)
    return prioritize_pinned_results(reranked, pinned_results, top_k=final_top_k)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Retrieval: BM25, vector-only, hoac hybrid")
    parser.add_argument("query", help="Natural language legal query")
    parser.add_argument("--chunks", default="output/chunks/all_chunks.jsonl", help="Path to all_chunks.jsonl")
    parser.add_argument("--bm25-index", default="output/chunks/retrieval/bm25_index.json", help="Path to BM25 index JSON")
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
    )
    print(
        json.dumps(
            {
                "query": args.query,
                "legal_intent": retrieval_plan["legal_intent"],
                "retrieval_queries": retrieval_plan["retrieval_queries"],
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
