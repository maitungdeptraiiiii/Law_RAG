from __future__ import annotations

import argparse
import json
from pathlib import Path

import faiss

from ..core.runtime_config import embedding_model, embedding_provider


OPENAI_EMBEDDING_MAX_CHARS = 6_000


def compact_metadata(chunk: dict) -> dict:
    source_file = str(
        chunk.get("source_file")
        or chunk.get("text_file")
        or f"vbpl/{chunk.get('vbpl_id') or chunk.get('doc_number') or chunk['chunk_id']}"
    )
    return {
        "chunk_id": chunk["chunk_id"],
        "source_file": source_file,
        "vbpl_id": str(chunk.get("vbpl_id")) if chunk.get("vbpl_id") is not None else None,
        "doc_number": chunk.get("doc_number"),
        "doc_type": chunk.get("doc_type"),
        "effective_status": chunk.get("effective_status"),
        "agency_name": chunk.get("agency_name"),
        "issue_date": chunk.get("issue_date"),
        "effective_from": chunk.get("effective_from"),
        "effective_to": chunk.get("effective_to"),
        "majors": chunk.get("majors"),
        "fields": chunk.get("fields"),
        "source_url": chunk.get("source_url"),
        "mode": chunk.get("mode") or "article",
        "article_number": chunk.get("article_number"),
        "clause_number": chunk.get("clause_number"),
        "point_number": chunk.get("point_number"),
        "document_title": chunk.get("document_title"),
        "chapter": chunk.get("chapter"),
        "part": chunk.get("part"),
        "target_article": chunk.get("target_article"),
        "text": chunk["text"],
    }


def rebuild_metadata(*, chunks_path: Path, vector_dir: Path, provider: str, model: str) -> dict:
    index_path = vector_dir / "faiss.index"
    if not index_path.exists():
        raise RuntimeError(f"Khong tim thay FAISS index: {index_path}")
    if not chunks_path.exists():
        raise RuntimeError(f"Khong tim thay chunks file: {chunks_path}")

    index = faiss.read_index(str(index_path))
    metadata_path = vector_dir / "vector_metadata.json"
    manifest_path = vector_dir / "vector_manifest.json"

    count = 0
    with chunks_path.open(encoding="utf-8") as source, metadata_path.open("w", encoding="utf-8") as target:
        target.write("[")
        first = True
        for line in source:
            if not line.strip():
                continue
            chunk = json.loads(line)
            item = compact_metadata(chunk)
            if first:
                first = False
            else:
                target.write(",")
            target.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
            count += 1
            if count % 10_000 == 0:
                print(f"[metadata] {count} chunks", flush=True)
        target.write("]\n")

    if count != index.ntotal:
        raise RuntimeError(
            f"So metadata ({count}) khong khop so vector trong FAISS ({index.ntotal}). "
            "Khong nen dung index nay truoc khi kiem tra lai chunks_path."
        )

    manifest = {
        "embedding_provider": provider,
        "embedding_model": model,
        "dimension": int(index.d),
        "chunk_count": count,
        "index_path": str(index_path),
        "metadata_path": str(metadata_path),
        "chunks_path": str(chunks_path),
        "embedding_input_max_chars": OPENAI_EMBEDDING_MAX_CHARS if provider == "openai" else None,
        "metadata_compact": True,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild vector_metadata.json/manifest tu chunks va FAISS index co san.")
    parser.add_argument("--chunks", required=True, help="Path toi all_chunks.jsonl dung de build FAISS index")
    parser.add_argument("--vector-dir", required=True, help="Thu muc chua faiss.index")
    parser.add_argument("--provider", default=embedding_provider(), help="Embedding provider da dung de build index")
    parser.add_argument("--model", default=embedding_model(), help="Embedding model da dung de build index")
    args = parser.parse_args()

    manifest = rebuild_metadata(
        chunks_path=Path(args.chunks),
        vector_dir=Path(args.vector_dir),
        provider=args.provider,
        model=args.model,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
