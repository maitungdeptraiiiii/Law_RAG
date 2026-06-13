import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from law_rag.retrieval.sqlite_retrieval_store import SQLiteRetrievalStore

sqlite_path = Path("output/vbpl_merged_reuse_openai/retrieval/retrieval_store.sqlite")
print(f"Opening SQLite store: {sqlite_path} ({sqlite_path.stat().st_size // 1024 // 1024} MB)")
idx = SQLiteRetrievalStore(sqlite_path)

def query_index(idx, query, top_k):
    return idx.query_bm25(query, top_k)

queries = [
    "đánh người bị tội gì",
    "cố ý gây thương tích Điều 134 Bộ luật Hình sự",
    "tội cố ý gây thương tích",
]

for q in queries:
    results = query_index(idx, q, 8)
    print(f"\n=== BM25: {q} ===")
    for r in results:
        title = (r.get("document_title") or "?")[:55]
        art = r.get("article_number") or "-"
        preview = (r.get("preview") or "")[:90]
        print(f"  [{r['score']:.3f}] {title} | Điều {art} | {preview}")
