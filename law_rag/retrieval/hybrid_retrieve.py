from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import faiss
import numpy as np
from openai import OpenAI

from ..core.env_loader import load_project_env
from .atlas_vector_store import atlas_vector_search, get_atlas_collection
from .build_vector_index import DEFAULT_EMBEDDING_MODEL
from .retrieve_chunks import (
    build_index_payload,
    load_index,
    query_index,
    save_index,
)


DEFAULT_QUERY_REWRITE_MODEL = "gpt-5.4-mini"


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


def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Thieu OPENAI_API_KEY trong environment.")
    return OpenAI(api_key=api_key)


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


def rewrite_query_with_llm(query: str, *, model: str, max_rewrites: int) -> dict:
    client = get_openai_client()
    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        response_format={"type": "json_object"},
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
    content = response.choices[0].message.content or "{}"
    payload = json.loads(content)
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
    if rewrite_mode == "none":
        return {
            "original_query": query,
            "legal_intent": "",
            "retrieval_queries": [query],
        }

    rewritten = rewrite_query_with_llm(query, model=rewrite_model, max_rewrites=max_rewrites)
    retrieval_queries = deduplicate_queries([query, *rewritten["retrieval_queries"]])
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


def embed_query(client: OpenAI, query: str, model: str) -> np.ndarray:
    response = client.embeddings.create(model=model, input=[query])
    return np.array(response.data[0].embedding, dtype="float32")


def normalize_query_for_faiss(vector: np.ndarray) -> np.ndarray:
    normalized = vector.reshape(1, -1)
    faiss.normalize_L2(normalized)
    return normalized


def faiss_vector_search(query: str, vector_dir: Path, top_k: int, embedding_model: str | None = None) -> list[dict]:
    client = get_openai_client()
    manifest, metadata, index = load_vector_assets(vector_dir)
    raw_query_vector = embed_query(client, query, embedding_model or manifest.get("embedding_model", DEFAULT_EMBEDDING_MODEL))
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
    client = get_openai_client()
    atlas_manifest = load_atlas_manifest(vector_dir)
    collection, config = get_atlas_collection(
        uri=atlas_uri,
        database=atlas_db or atlas_manifest.get("database"),
        collection=atlas_collection or atlas_manifest.get("collection"),
        vector_index=atlas_vector_index or atlas_manifest.get("vector_index"),
    )
    query_vector = embed_query(client, query, embedding_model).tolist()
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


def reciprocal_rank_fusion(*ranked_lists: list[dict], top_k: int, k: int = 60) -> list[dict]:
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
    return results[:top_k]


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
) -> list[dict]:
    active_queries = retrieval_queries or [query]

    bm25_ranked_lists: list[list[dict]] = []
    if retrieval_mode in {"bm25", "hybrid"}:
        bm25_index = ensure_bm25_index(chunks_path, bm25_index_path)
        for retrieval_query in active_queries:
            bm25_results = query_index(bm25_index, retrieval_query, bm25_top_k)
            for item in bm25_results:
                item["search_source"] = "bm25"
            bm25_ranked_lists.append(bm25_results)

    vector_ranked_lists: list[list[dict]] = []
    if retrieval_mode in {"vector", "hybrid"}:
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

    if retrieval_mode == "vector":
        if len(vector_ranked_lists) <= 1:
            return finalize_single_source_results(vector_ranked_lists[0] if vector_ranked_lists else [], top_k=final_top_k)
        return reciprocal_rank_fusion(*vector_ranked_lists, top_k=final_top_k)
    if retrieval_mode == "bm25":
        if len(bm25_ranked_lists) <= 1:
            return finalize_single_source_results(bm25_ranked_lists[0] if bm25_ranked_lists else [], top_k=final_top_k)
        return reciprocal_rank_fusion(*bm25_ranked_lists, top_k=final_top_k)
    return reciprocal_rank_fusion(*bm25_ranked_lists, *vector_ranked_lists, top_k=final_top_k)


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieval: BM25, vector-only, hoac hybrid")
    parser.add_argument("query", help="Natural language legal query")
    parser.add_argument("--chunks", default="output/chunks/all_chunks.jsonl", help="Path to all_chunks.jsonl")
    parser.add_argument("--bm25-index", default="output/chunks/retrieval/bm25_index.json", help="Path to BM25 index JSON")
    parser.add_argument("--vector-dir", default="output/chunks/retrieval/vector", help="Thu muc chua FAISS index va metadata")
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