import sys
import os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from law_rag.core.env_loader import load_project_env
load_project_env()

from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL"))
model = os.getenv("CHAT_MODEL", "gpt-5.4-mini")
print("Model:", model)

# Test 1: json_object
print("\n--- Test json_object ---")
try:
    r = client.chat.completions.create(
        model=model,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": "Tra ve JSON: {\"ok\": true}"}],
    )
    print("OK:", r.choices[0].message.content[:200])
except Exception as e:
    print("ERROR:", type(e).__name__, str(e)[:400])

# Test 2: embedding
print("\n--- Test embedding ---")
emb_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
print("Embedding model:", emb_model)
try:
    from openai import OpenAI as OAI
    emb_client = OAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL"))
    r2 = emb_client.embeddings.create(model=emb_model, input="test query")
    print("OK, dim:", len(r2.data[0].embedding))
except Exception as e:
    print("ERROR:", type(e).__name__, str(e)[:400])

# Test 3: full answer_question (short)
print("\n--- Test full pipeline ---")
try:
    from law_rag.app.ask_law import answer_question
    from pathlib import Path
    result = answer_question(
        "đánh người bị tội gì",
        chunks_path=Path("output/vbpl_merged_reuse_openai/all_chunks.jsonl"),
        bm25_index_path=Path("output/vbpl_merged_reuse_openai/retrieval/bm25_index.json"),
        vector_dir=Path("output/vbpl_merged_reuse_openai/retrieval/vector-openai"),
        query_rewrite_mode="llm",
        query_rewrite_model=model,
        query_rewrite_count=2,
        retrieval_mode="bm25",
        vector_backend="faiss",
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        atlas_uri=None,
        atlas_db=None,
        atlas_collection=None,
        atlas_vector_index=None,
        model=model,
        memory_model=model,
        top_k=5,
        session_id=None,
    )
    print("Retrieved docs:")
    for item in result["retrieved"]:
        print(f"  - {(item.get('document_title') or '?')[:60]} | Dieu {item.get('article_number')}")
    print("\nAnswer snippet:", result["answer"][:300])
except Exception as e:
    import traceback
    print("ERROR:", type(e).__name__, str(e)[:600])
    traceback.print_exc()
