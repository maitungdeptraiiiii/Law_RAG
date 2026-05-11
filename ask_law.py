from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from openai import OpenAI

from conversation_state import (
    append_history,
    format_case_state,
    format_recent_history,
    load_session,
    save_session,
)
from env_loader import load_project_env
from hybrid_retrieve import build_retrieval_queries, hybrid_search


DEFAULT_CHAT_MODEL = "gpt-5.4-mini"
DEFAULT_MEMORY_MODEL = "gpt-5.4-mini"


SYSTEM_PROMPT = """Ban la tro ly phap ly noi bo cho du an RAG luat Viet Nam.
Chi duoc tra loi dua tren cac doan luat duoc cung cap.
Neu context chua du de ket luan chac chan, phai noi ro chua du du kien va neu cac thong tin can bo sung.
Moi cau tra loi phai:
1. Tom tat nhan dinh chinh.
2. Neu can cu dieu/khoan/van ban lien quan.
3. Khong duoc khang dinh vuot qua context.
"""

MEMORY_UPDATE_SYSTEM_PROMPT = """Ban dang quan ly bo nho hoi thoai cho tro ly phap ly Viet Nam.
Nhiem vu:
1. Doc tinh tiet vu viec da biet va cau hoi moi cua nguoi dung.
2. Cap nhat tom tat vu viec va facts co cau truc.
3. Neu chua du du kien de ket luan so bo, xac dinh thong tin con thieu va dat 1 cau hoi bo sung ngan gon nhat.
4. Tao mot retrieval_query ngon ngu phap ly dua tren toan bo tinh tiet da biet, khong chi dua vao cau hoi moi nhat.

Tra ve JSON hop le voi cac khoa:
- case_summary: string
- facts: object
- need_clarification: boolean
- missing_fields: array[string]
- follow_up_question: string
- retrieval_query: string

Nguyen tac:
- Khong bịa facts.
- Neu nguoi dung vua cung cap them thong tin, phai hop nhat vao facts hien co.
- follow_up_question phai cu the, toi da 1 cau.
"""


load_project_env()


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


def update_case_memory(
    client: OpenAI,
    *,
    question: str,
    session: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": MEMORY_UPDATE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Hoi thoai gan day:\n{format_recent_history(session)}\n\n"
                    f"Tinh tiet da biet:\n{format_case_state(session)}\n\n"
                    f"Cau hoi moi nhat cua nguoi dung:\n{question}\n"
                ),
            },
        ],
    )
    payload = json.loads(response.choices[0].message.content or "{}")
    return {
        "case_summary": str(payload.get("case_summary", "")).strip(),
        "facts": payload.get("facts", {}) if isinstance(payload.get("facts", {}), dict) else {},
        "need_clarification": bool(payload.get("need_clarification", False)),
        "missing_fields": [str(item) for item in payload.get("missing_fields", []) if str(item).strip()],
        "follow_up_question": str(payload.get("follow_up_question", "")).strip(),
        "retrieval_query": str(payload.get("retrieval_query", "")).strip(),
    }


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
    memory_model: str,
    top_k: int,
    session_id: str | None = None,
    session_dir: Path | None = None,
) -> dict:
    client = get_openai_client()
    session: dict[str, Any] | None = None
    memory_update: dict[str, Any] | None = None

    if session_id:
        session = load_session(session_id, session_dir)
        append_history(session, "user", question)
        memory_update = update_case_memory(client, question=question, session=session, model=memory_model)
        session["case_summary"] = memory_update["case_summary"]
        session["facts"] = memory_update["facts"]
        session["pending_follow_up"] = memory_update["follow_up_question"] if memory_update["need_clarification"] else None
        session["last_retrieval_query"] = memory_update["retrieval_query"]

        if memory_update["need_clarification"] and memory_update["follow_up_question"]:
            answer = memory_update["follow_up_question"]
            append_history(session, "assistant", answer)
            session_path = save_session(session, session_dir)
            return {
                "question": question,
                "legal_intent": "",
                "retrieval_queries": [],
                "answer": answer,
                "answer_type": "clarification",
                "session_id": session_id,
                "session_path": str(session_path),
                "case_summary": session.get("case_summary", ""),
                "facts": session.get("facts", {}),
                "missing_fields": memory_update["missing_fields"],
                "retrieved": [],
            }

    retrieval_input = question
    if memory_update and memory_update["retrieval_query"]:
        retrieval_input = memory_update["retrieval_query"]

    retrieval_plan = build_retrieval_queries(
        retrieval_input,
        rewrite_mode=query_rewrite_mode,
        rewrite_model=query_rewrite_model,
        max_rewrites=query_rewrite_count,
    )
    retrieved = hybrid_search(
        retrieval_input,
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

    context = build_context(retrieved)
    case_state_text = format_case_state(session) if session else "Khong co bo nho hoi thoai."
    history_text = format_recent_history(session) if session else "Khong co hoi thoai truoc do."
    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Cau hoi cua nguoi dung:\n{question}\n\n"
                    f"Hoi thoai gan day:\n{history_text}\n\n"
                    f"Tinh tiet vu viec da biet:\n{case_state_text}\n\n"
                    f"Context luat da retrieve:\n{context}\n\n"
                    "Hay tra loi bang tieng Viet, ngan gon, co can cu, va neu thieu du kien thi noi ro can bo sung gi."
                ),
            },
        ],
    )

    answer = response.choices[0].message.content or ""
    payload = {
        "question": question,
        "legal_intent": retrieval_plan["legal_intent"],
        "retrieval_queries": retrieval_plan["retrieval_queries"],
        "retrieval_input": retrieval_input,
        "answer": answer,
        "answer_type": "final",
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

    if session is not None:
        append_history(session, "assistant", answer)
        session["pending_follow_up"] = None
        session_path = save_session(session, session_dir)
        payload["session_id"] = session_id
        payload["session_path"] = str(session_path)
        payload["case_summary"] = session.get("case_summary", "")
        payload["facts"] = session.get("facts", {})

    return payload


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
    parser.add_argument("--memory-model", default=DEFAULT_MEMORY_MODEL, help="LLM model dung de cap nhat bo nho hoi thoai")
    parser.add_argument("--top-k", type=int, default=5, help="So chunk dua vao answer stage")
    parser.add_argument("--session-id", default=None, help="ID de giu nho hoi thoai qua nhieu luot")
    parser.add_argument("--session-dir", default="output/sessions", help="Noi luu session JSON")
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
        memory_model=args.memory_model,
        top_k=args.top_k,
        session_id=args.session_id,
        session_dir=Path(args.session_dir),
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(payload["answer"])


if __name__ == "__main__":
    main()