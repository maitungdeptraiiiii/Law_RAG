from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable

from ..core.conversation_state import (
    append_history,
    format_case_state,
    format_recent_history,
    load_session,
    save_session,
)
from ..core.env_loader import load_project_env
from ..core.llm_client import chat_completion_json, chat_completion_text, get_chat_client
from ..core.runtime_config import chat_model, default_vector_dir, memory_model
from ..retrieval.hybrid_retrieve import build_retrieval_queries, hybrid_search


DEFAULT_CHAT_MODEL = chat_model()
DEFAULT_MEMORY_MODEL = memory_model()
SYSTEM_PROMPT = """Bạn là trợ lý pháp lý nội bộ cho dự án RAG luật Việt Nam.
Chỉ được trả lời dựa trên các đoạn luật được cung cấp.
Phải trả lời trực tiếp câu hỏi trong 1-2 câu đầu trước khi giải thích thêm.
Chỉ được viện dẫn Điều/Khoản/Văn bản xuất hiện trong context đã retrieve; không được nêu căn cứ pháp lý ngoài context, kể cả khi bạn biết từ kiến thức chung.
Nếu context có Điều nhưng không có Khoản cụ thể, chỉ nêu Khoản khi nội dung khoản đó xuất hiện rõ trong chính đoạn context.
Nếu một căn cứ có vẻ liên quan nhưng không có trong context, hãy nói ngắn gọn rằng cần đối chiếu thêm thay vì trích dẫn như căn cứ chắc chắn.
Nếu context chưa đủ để kết luận chắc chắn, vẫn phải rút ra tối đa những khả năng có thể suy ra từ context hiện có.
Không được dừng lại quá sớm chỉ với kết luận 'chưa đủ dữ kiện' nếu context vẫn cho phép nêu các trường hợp, khả năng xử lý, ngưỡng điều kiện, hoặc hướng đánh giá sơ bộ.
Khi trả lời theo nhánh điều kiện, tuyệt đối không dùng ký hiệu mơ hồ như "A", "B", "trường hợp 1", "trường hợp 2" nếu chưa giải thích ngay trong chính tiêu đề nhánh.
Mỗi nhánh phải gọi rõ điều kiện pháp lý hoặc tình tiết thực tế, ví dụ:
- Nếu người bị hại từ đủ 13 tuổi đến dưới 16 tuổi thì có thể áp dụng ...
- Nếu người bị hại từ đủ 16 tuổi trở lên và có hành vi dùng vũ lực/đe dọa dùng vũ lực thì cần xem xét ...
- Nếu chỉ có hành vi mua bán dâm hoặc dâm ô mà không đủ dấu hiệu hiếp dâm thì cần xem xét ...
- Trong context hiện có, điều có thể khẳng định được là ...
- Phần chưa rõ chỉ nêu ngắn gọn ở cuối câu trả lời.
Mỗi câu trả lời phải:
1. Tóm tắt nhận định chính, trả lời thẳng vào câu hỏi.
2. Nêu căn cứ điều/khoản/văn bản liên quan.
3. Nếu vụ việc còn thiếu dữ kiện, phải nêu các nhánh khả năng dựa trên context trước khi nói phần cần bổ sung.
4. Không được khẳng định vượt quá context.
5. Không được đặt tiêu đề nhánh là "Nếu A", "Nếu B", "Nếu trường hợp A/B"; phải viết đầy đủ điều kiện ngay sau chữ "Nếu".
6. Nếu còn thiếu dữ kiện để kết luận chi tiết hơn, phải kết thúc bằng một mục riêng tên là 'Cần bổ sung thêm:' và đặt 1 câu hỏi bổ sung cụ thể, ngắn gọn, hữu ích nhất.
7. Nếu đã đủ dữ kiện từ context hiện có thì không cần thêm mục 'Cần bổ sung thêm:'.
"""

MEMORY_UPDATE_SYSTEM_PROMPT = """Bạn đang quản lý bộ nhớ hội thoại cho trợ lý pháp lý Việt Nam.
Nhiệm vụ:
1. Đọc tình tiết vụ việc đã biết và câu hỏi mới của người dùng.
2. Cập nhật tóm tắt vụ việc và facts có cấu trúc.
3. Chỉ đánh dấu need_clarification=true nếu thiếu dữ kiện đến mức không thể đưa ra bất kỳ hướng đánh giá pháp lý hữu ích nào dựa trên context hiện có.
4. Nếu vẫn có thể đưa ra nhận định theo các trường hợp/ngưỡng điều kiện/khung pháp lý, thì đặt need_clarification=false và vẫn tạo retrieval_query tốt nhất.
5. Tạo một retrieval_query ngôn ngữ pháp lý dựa trên toàn bộ tình tiết đã biết, không chỉ dựa vào câu hỏi mới nhất.

Trả về JSON hợp lệ với các khóa:
- case_summary: string
- facts: object
- need_clarification: boolean
- missing_fields: array[string]
- follow_up_question: string
- retrieval_query: string

Nguyên tắc:
- Không bịa facts.
- Nếu người dùng vừa cung cấp thêm thông tin, phải hợp nhất vào facts hiện có.
- Không đặt follow_up_question nếu vẫn có thể trả lời hữu ích dựa trên context hiện có.
- follow_up_question phải cụ thể, tối đa 1 câu.
"""


load_project_env()


def get_openai_client() -> Any:
    return get_chat_client()


def build_context(results: list[dict]) -> str:
    blocks: list[str] = []
    for index, item in enumerate(results, start=1):
        reference = [str(item.get("document_title") or item.get("doc_number") or item["source_file"])]
        if item.get("doc_number"):
            reference.append(str(item["doc_number"]))
        if item.get("article_number"):
            reference.append(f"Điều {item['article_number']}")
        if item.get("clause_number"):
            reference.append(f"khoản {item['clause_number']}")
        if item.get("target_article"):
            reference.append(f"sửa {item['target_article']}")

        if "rerank_score" in item:
            score_label = f"Rerank score: {item['rerank_score']:.6f}"
        elif "rrf_score" in item:
            score_label = f"RRF score: {item['rrf_score']:.6f}"
        else:
            score_label = f"Score: {item.get('score', 0.0):.6f}"

        blocks.append(
            f"[Nguồn {index}] {' | '.join(reference)}\n"
            f"{score_label}\n"
            f"Nội dung: {item.get('text', item['preview'])}"
        )
    return "\n\n".join(blocks)



def update_case_memory(
    client: Any,
    *,
    question: str,
    session: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    payload = chat_completion_json(
        client,
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": MEMORY_UPDATE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Hội thoại gần đây:\n{format_recent_history(session)}\n\n"
                    f"Tình tiết đã biết:\n{format_case_state(session)}\n\n"
                    f"Câu hỏi mới nhất của người dùng:\n{question}\n"
                ),
            },
        ],
    )
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
    additional_bm25_sources: list[tuple[Path, Path]] | None = None,
    additional_vector_dirs: list[Path] | None = None,
    session_id: str | None = None,
    session_dir: Path | None = None,
    answer_stream_callback: Callable[[str], None] | None = None,
) -> dict:
    total_started = time.perf_counter()
    timings: dict[str, Any] = {}
    client = get_openai_client()
    session: dict[str, Any] | None = None
    memory_update: dict[str, Any] | None = None

    if session_id:
        memory_started = time.perf_counter()
        session = load_session(session_id, session_dir)
        append_history(session, "user", question)
        memory_update = update_case_memory(client, question=question, session=session, model=memory_model)
        timings["memoryUpdate"] = int((time.perf_counter() - memory_started) * 1000)
        session["case_summary"] = memory_update["case_summary"]
        session["facts"] = memory_update["facts"]
        session["pending_follow_up"] = memory_update["follow_up_question"] if memory_update["need_clarification"] else None
        session["last_retrieval_query"] = memory_update["retrieval_query"]
    else:
        timings["memoryUpdate"] = 0

    retrieval_input = question
    if memory_update and memory_update["retrieval_query"]:
        retrieval_input = memory_update["retrieval_query"]

    rewrite_started = time.perf_counter()
    retrieval_plan = build_retrieval_queries(
        retrieval_input,
        rewrite_mode=query_rewrite_mode,
        rewrite_model=query_rewrite_model,
        max_rewrites=query_rewrite_count,
    )
    timings["queryRewrite"] = int((time.perf_counter() - rewrite_started) * 1000)
    retrieval_debug_timings: dict[str, Any] = {}
    retrieval_started = time.perf_counter()
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
        bm25_top_k=max(top_k * 6, 30),
        vector_top_k=max(top_k * 6, 30),
        final_top_k=top_k,
        additional_bm25_sources=additional_bm25_sources,
        additional_vector_dirs=additional_vector_dirs,
        legal_issue_labels=retrieval_plan.get("legal_issue_labels", []),
        legal_issue_matches=retrieval_plan.get("legal_issue_matches", []),
        debug_timings=retrieval_debug_timings,
    )
    timings["retrieval"] = int((time.perf_counter() - retrieval_started) * 1000)
    timings.update(retrieval_debug_timings)

    context_started = time.perf_counter()
    context = build_context(retrieved)
    case_state_text = format_case_state(session) if session else "Không có bộ nhớ hội thoại."
    history_text = format_recent_history(session) if session else "Không có hội thoại trước đó."
    missing_fields_text = (
        ", ".join(memory_update["missing_fields"]) if memory_update and memory_update.get("missing_fields") else "Không có."
    )
    pending_follow_up_text = (
        memory_update["follow_up_question"] if memory_update and memory_update.get("follow_up_question") else "Không có."
    )
    timings["contextBuild"] = int((time.perf_counter() - context_started) * 1000)
    final_llm_started = time.perf_counter()
    answer = chat_completion_text(
        client,
        model=model,
        temperature=0.1,
        stream_callback=answer_stream_callback,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Câu hỏi của người dùng:\n{question}\n\n"
                    f"Hội thoại gần đây:\n{history_text}\n\n"
                    f"Tình tiết vụ việc đã biết:\n{case_state_text}\n\n"
                    f"Context luật đã retrieve:\n{context}\n\n"
                    f"Thông tin còn thiếu nếu có:\n{missing_fields_text}\n\n"
                    f"Câu hỏi bổ sung nếu thật sự cần:\n{pending_follow_up_text}\n\n"
                    "Hãy trả lời bằng tiếng Việt, ngắn gọn, có căn cứ. Nếu context chưa trọn vẹn thì vẫn phải nêu được các trường hợp, ngưỡng điều kiện, hướng đánh giá hoặc khả năng xử lý có thể rút ra từ context hiện có. Khi chia nhánh, không được viết 'Nếu A', 'Nếu B' hoặc ký hiệu tương tự; phải nêu rõ điều kiện cụ thể trong từng nhánh, ví dụ độ tuổi, hành vi, dấu hiệu cấu thành hoặc điều luật liên quan. Chỉ nêu ngắn gọn phần cần bổ sung ở cuối câu trả lời, không được biến toàn bộ câu trả lời thành một thông báo thiếu dữ kiện. Nếu vẫn cần thêm dữ liệu để kết luận chặt hơn, hãy thêm một mục cuối cùng theo đúng nhãn 'Cần bổ sung thêm:' và đặt một câu hỏi bổ sung cụ thể nhất."
                ),
            },
        ],
    )
    timings["finalLlm"] = int((time.perf_counter() - final_llm_started) * 1000)
    timings["totalInner"] = int((time.perf_counter() - total_started) * 1000)
    payload = {
        "question": question,
        "legal_intent": retrieval_plan["legal_intent"],
        "retrieval_queries": retrieval_plan["retrieval_queries"],
        "rewrite_source": retrieval_plan.get("rewrite_source"),
        "legal_issue_confidence": retrieval_plan.get("legal_issue_confidence"),
        "legal_issue_labels": retrieval_plan.get("legal_issue_labels", []),
        "legal_issue_matches": retrieval_plan.get("legal_issue_matches", []),
        "retrieval_input": retrieval_input,
        "retrieval_query_count": len(retrieval_plan["retrieval_queries"]),
        "retrieval_input_chars": len(retrieval_input),
        "context_chars": len(context),
        "timings": timings,
        "answer": answer,
        "answer_type": "final",
        "retrieved": [
            {
                "chunk_id": item["chunk_id"],
                "source_file": item["source_file"],
                "vbpl_id": item.get("vbpl_id"),
                "doc_number": item.get("doc_number"),
                "doc_type": item.get("doc_type"),
                "document_title": item.get("document_title"),
                "source_url": item.get("source_url"),
                "issue_date": item.get("issue_date"),
                "article_number": item.get("article_number"),
                "clause_number": item.get("clause_number"),
                "point_number": item.get("point_number"),
                "parent_chunk_id": item.get("parent_chunk_id"),
                "target_article": item.get("target_article"),
                "rrf_score": item.get("rrf_score", 0.0),
                "rerank_score": item.get("rerank_score"),
                "rerank_features": item.get("rerank_features"),
                "sources": item.get("sources", []),
                "text": item.get("text", item["preview"]),
                "preview": item["preview"],
            }
            for item in retrieved
        ],
    }

    if session is not None:
        append_history(session, "assistant", answer)
        session["pending_follow_up"] = memory_update["follow_up_question"] if memory_update and memory_update["need_clarification"] else None
        session_path = save_session(session, session_dir)
        payload["session_id"] = session_id
        payload["session_path"] = str(session_path)
        payload["case_summary"] = session.get("case_summary", "")
        payload["facts"] = session.get("facts", {})
        payload["missing_fields"] = memory_update["missing_fields"] if memory_update else []

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="One-shot legal QA: hybrid retrieval + OpenAI chat")
    parser.add_argument("question", help="Câu hỏi tình huống pháp lý")
    parser.add_argument("--chunks", default="output/vbpl_laws_active_partial/all_chunks.jsonl", help="Path to all_chunks.jsonl")
    parser.add_argument("--bm25-index", default="output/vbpl_laws_active_partial/retrieval/bm25_index.json", help="Path to BM25 index JSON")
    parser.add_argument("--vector-dir", default=default_vector_dir(), help="Thư mục chứa FAISS index")
    parser.add_argument("--query-rewrite-mode", choices=["none", "llm"], default="none", help="Chế độ rewrite query trước retrieval")
    parser.add_argument("--query-rewrite-model", default="gpt-5.4-mini", help="LLM model dùng để rewrite query")
    parser.add_argument("--query-rewrite-count", type=int, default=4, help="Số truy vấn rewrite tối đa")
    parser.add_argument("--retrieval-mode", choices=["hybrid", "vector", "bm25"], default="hybrid", help="Chế độ retrieval")
    parser.add_argument("--vector-backend", choices=["faiss", "atlas"], default="faiss", help="Backend vector retrieval")
    parser.add_argument("--embedding-model", default="text-embedding-3-small", help="Embedding model cho vector query")
    parser.add_argument("--atlas-uri", default=None, help="MongoDB Atlas connection string")
    parser.add_argument("--atlas-db", default=None, help="Tên database trên Atlas")
    parser.add_argument("--atlas-collection", default=None, help="Tên collection trên Atlas")
    parser.add_argument("--atlas-vector-index", default=None, help="Tên Atlas Vector Search index")
    parser.add_argument("--model", default=DEFAULT_CHAT_MODEL, help="Chat model dùng để sinh câu trả lời")
    parser.add_argument("--memory-model", default=DEFAULT_MEMORY_MODEL, help="LLM model dùng để cập nhật bộ nhớ hội thoại")
    parser.add_argument("--top-k", type=int, default=5, help="Số chunk đưa vào answer stage")
    parser.add_argument("--session-id", default=None, help="ID để giữ nhớ hội thoại qua nhiều lượt")
    parser.add_argument("--session-dir", default="output/sessions", help="Nơi lưu session JSON")
    parser.add_argument("--json", action="store_true", help="In JSON đầy đủ")
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
