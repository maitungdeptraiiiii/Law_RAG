from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from openai import OpenAI

from hybrid_retrieve import build_retrieval_queries, hybrid_search


DEFAULT_CHAT_MODEL = "gpt-5.4-mini"


SYSTEM_PROMPT = """Ban la tro ly phap ly noi bo cho du an RAG luat Viet Nam.
Chi duoc tra loi dua tren cac doan luat duoc cung cap.
Neu context chua du de ket luan chac chan, phai noi ro chua du du kien va neu cac thong tin can bo sung.
Moi cau tra loi phai:
1. Tom tat nhan dinh chinh.
2. Neu can cu dieu/khoan/van ban lien quan.
3. Khong duoc khang dinh vuot qua context.
"""


def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Thieu OPENAI_API_KEY trong environment.")
    return OpenAI(api_key=api_key)


def build_context(results: list[dict]) -> str:
    blocks: list[str] = []
    for index, item in enumerate(results, start=1):
        reference = [item["source_file"]]
        if item.get("article_number"):
            reference.append(f"Điều {item['article_number']}")
        if item.get("clause_number"):
            reference.append(f"khoản {item['clause_number']}")
        if item.get("target_article"):
            reference.append(f"sửa {item['target_article']}")

        if "rrf_score" in item:
            score_label = f"RRF score: {item['rrf_score']:.6f}"
        else:
            score_label = f"Score: {item.get('score', 0.0):.6f}"

        blocks.append(
            f"[Nguon {index}] {' | '.join(reference)}\n"
            f"{score_label}\n"
            f"Noi dung: {item.get('text', item['preview'])}"
        )
    return "\n\n".join(blocks)


def answer_question(
    question: str,
    *,
    chunks_path: Path,
    bm25_index_path: Path,
    vector_dir: Path,
    query_rewrite_mode: str,
    query_rewrite_model: str,
    query_rewrite_count: int,
    retrieval_mode: str,
    vector_backend: str,
    embedding_model: str,
    atlas_uri: str | None,
    atlas_db: str | None,
    atlas_collection: str | None,
    atlas_vector_index: str | None,
    model: str,
    top_k: int,
) -> dict:
    retrieval_plan = build_retrieval_queries(
        question,
        rewrite_mode=query_rewrite_mode,
        rewrite_model=query_rewrite_model,
        max_rewrites=query_rewrite_count,
    )
    retrieved = hybrid_search(
        question,
        retrieval_queries=retrieval_plan["retrieval_queries"],
        chunks_path=chunks_path,
        bm25_index_path=bm25_index_path,
        vector_dir=vector_dir,
        retrieval_mode=retrieval_mode,
        vector_backend=vector_backend,
        embedding_model=embedding_model,
        atlas_uri=atlas_uri,
        atlas_db=atlas_db,
        atlas_collection=atlas_collection,
        atlas_vector_index=atlas_vector_index,
        bm25_top_k=max(top_k * 2, 8),
        vector_top_k=max(top_k * 2, 8),
        final_top_k=top_k,
    )

    client = get_openai_client()
    context = build_context(retrieved)
    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Cau hoi cua nguoi dung:\n{question}\n\n"
                    f"Context luat da retrieve:\n{context}\n\n"
                    "Hay tra loi bang tieng Viet, ngan gon, co can cu, va neu thieu du kien thi noi ro can bo sung gi."
                ),
            },
        ],
    )

    answer = response.choices[0].message.content or ""
    return {
        "question": question,
        "legal_intent": retrieval_plan["legal_intent"],
        "retrieval_queries": retrieval_plan["retrieval_queries"],
        "answer": answer,
        "retrieved": [
            {
                "chunk_id": item["chunk_id"],
                "source_file": item["source_file"],
                "article_number": item.get("article_number"),
                "clause_number": item.get("clause_number"),
                "target_article": item.get("target_article"),
                "rrf_score": item["rrf_score"],
                "sources": item.get("sources", []),
                "preview": item["preview"],
            }
            for item in retrieved
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="One-shot legal QA: hybrid retrieval + OpenAI chat")
    parser.add_argument("question", help="Cau hoi tinh huong phap ly")
    parser.add_argument("--chunks", default="output/chunks/all_chunks.jsonl", help="Path to all_chunks.jsonl")
    parser.add_argument("--bm25-index", default="output/chunks/retrieval/bm25_index.json", help="Path to BM25 index JSON")
    parser.add_argument("--vector-dir", default="output/chunks/retrieval/vector", help="Thu muc chua FAISS index")
    parser.add_argument("--query-rewrite-mode", choices=["none", "llm"], default="none", help="Che do rewrite query truoc retrieval")
    parser.add_argument("--query-rewrite-model", default="gpt-5.4-mini", help="LLM model dung de rewrite query")
    parser.add_argument("--query-rewrite-count", type=int, default=4, help="So truy van rewrite toi da")
    parser.add_argument("--retrieval-mode", choices=["hybrid", "vector", "bm25"], default="hybrid", help="Che do retrieval")
    parser.add_argument("--vector-backend", choices=["faiss", "atlas"], default="faiss", help="Backend vector retrieval")
    parser.add_argument("--embedding-model", default="text-embedding-3-small", help="Embedding model cho vector query")
    parser.add_argument("--atlas-uri", default=None, help="MongoDB Atlas connection string")
    parser.add_argument("--atlas-db", default=None, help="Ten database tren Atlas")
    parser.add_argument("--atlas-collection", default=None, help="Ten collection tren Atlas")
    parser.add_argument("--atlas-vector-index", default=None, help="Ten Atlas Vector Search index")
    parser.add_argument("--model", default=DEFAULT_CHAT_MODEL, help="OpenAI chat model")
    parser.add_argument("--top-k", type=int, default=5, help="So chunk dua vao answer stage")
    parser.add_argument("--json", action="store_true", help="In JSON day du")
    args = parser.parse_args()

    payload = answer_question(
        args.question,
        chunks_path=Path(args.chunks),
        bm25_index_path=Path(args.bm25_index),
        vector_dir=Path(args.vector_dir),
        query_rewrite_mode=args.query_rewrite_mode,
        query_rewrite_model=args.query_rewrite_model,
        query_rewrite_count=args.query_rewrite_count,
        retrieval_mode=args.retrieval_mode,
        vector_backend=args.vector_backend,
        embedding_model=args.embedding_model,
        atlas_uri=args.atlas_uri,
        atlas_db=args.atlas_db,
        atlas_collection=args.atlas_collection,
        atlas_vector_index=args.atlas_vector_index,
        model=args.model,
        top_k=args.top_k,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(payload["answer"])


if __name__ == "__main__":
    main()