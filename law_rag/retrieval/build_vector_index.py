from __future__ import annotations

import argparse
import json
from pathlib import Path

import faiss
import numpy as np

from ..core.embedding_client import DEFAULT_EMBEDDING_MODEL, embed_texts, embedding_provider
from ..core.env_loader import load_project_env
from ..core.runtime_config import default_vector_dir
from .atlas_vector_store import build_atlas_document, get_atlas_collection, upsert_atlas_documents
from .retrieve_chunks import build_searchable_text, load_chunks


load_project_env()

OPENAI_EMBEDDING_MAX_CHARS = 6_000


def batched(items: list[dict], batch_size: int) -> list[list[dict]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def trim_embedding_input(text: str, *, provider: str, max_chars: int) -> tuple[str, bool]:
    if provider != "openai" or len(text) <= max_chars:
        return text, False
    trimmed = text[:max_chars].rsplit("\n", 1)[0].strip()
    if len(trimmed) < max_chars // 2:
        trimmed = text[:max_chars].strip()
    return trimmed, True


def print_build_progress(*, backend: str, batch_number: int, total_batches: int, processed_chunks: int, total_chunks: int) -> None:
    percent = (processed_chunks / total_chunks * 100.0) if total_chunks else 100.0
    print(
        f"[{backend}] batch {batch_number}/{total_batches} | "
        f"chunks {processed_chunks}/{total_chunks} | {percent:.1f}%"
    )


def build_vector_index(
    chunks_path: Path,
    output_dir: Path,
    *,
    model: str,
    batch_size: int,
    backend: str,
    atlas_uri: str | None,
    atlas_db: str | None,
    atlas_collection: str | None,
    atlas_vector_index: str | None,
) -> dict:
    provider = embedding_provider()
    chunks = load_chunks(chunks_path)
    total_chunks = len(chunks)
    batches = batched(chunks, batch_size)

    if not batches:
        raise RuntimeError("Khong co chunk nao de build vector index.")

    output_dir.mkdir(parents=True, exist_ok=True)

    metadata: list[dict] = []
    all_vectors: list[list[float]] = []
    atlas_collection_handle = None
    atlas_config: dict[str, str] | None = None

    if backend in {"atlas", "both"}:
        atlas_collection_handle, atlas_config = get_atlas_collection(
            uri=atlas_uri,
            database=atlas_db,
            collection=atlas_collection,
            vector_index=atlas_vector_index,
        )

    processed_chunks = 0
    trimmed_embedding_inputs = 0
    for batch_number, batch in enumerate(batches, start=1):
        searchable_texts = [build_searchable_text(chunk) for chunk in batch]
        embedding_texts: list[str] = []
        trimmed_flags: list[bool] = []
        for searchable_text in searchable_texts:
            embedding_text, was_trimmed = trim_embedding_input(
                searchable_text,
                provider=provider,
                max_chars=OPENAI_EMBEDDING_MAX_CHARS,
            )
            embedding_texts.append(embedding_text)
            trimmed_flags.append(was_trimmed)
        trimmed_embedding_inputs += sum(1 for flag in trimmed_flags if flag)

        vectors = embed_texts(embedding_texts, model=model, provider=provider)
        if backend in {"faiss", "both"}:
            all_vectors.extend(vectors)

            for chunk, searchable_text, embedding_text, was_trimmed in zip(batch, searchable_texts, embedding_texts, trimmed_flags):
                source_file = str(chunk.get("source_file") or chunk.get("text_file") or f"vbpl/{chunk.get('vbpl_id') or chunk.get('doc_number') or chunk['chunk_id']}")
                metadata.append(
                    {
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
                        "searchable_text": searchable_text,
                        "embedding_text": embedding_text,
                        "embedding_input_trimmed": was_trimmed,
                    }
                )

        if backend in {"atlas", "both"}:
            documents = [
                build_atlas_document(chunk, embedding_text, vector)
                for chunk, embedding_text, vector in zip(batch, embedding_texts, vectors)
            ]
            upsert_atlas_documents(atlas_collection_handle, documents)

        processed_chunks += len(batch)
        print_build_progress(
            backend=backend,
            batch_number=batch_number,
            total_batches=len(batches),
            processed_chunks=processed_chunks,
            total_chunks=total_chunks,
        )

    result = {
        "embedding_provider": provider,
        "embedding_model": model,
        "chunk_count": total_chunks,
        "backend": backend,
        "embedding_input_max_chars": OPENAI_EMBEDDING_MAX_CHARS if provider == "openai" else None,
        "trimmed_embedding_inputs": trimmed_embedding_inputs,
    }

    if backend in {"faiss", "both"} and not all_vectors:
        raise RuntimeError("Khong co vector nao duoc tao tu chunks.")

    if backend in {"faiss", "both"}:
        matrix = np.array(all_vectors, dtype="float32")
        faiss.normalize_L2(matrix)
        index = faiss.IndexFlatIP(matrix.shape[1])
        index.add(matrix)

        index_path = output_dir / "faiss.index"
        metadata_path = output_dir / "vector_metadata.json"
        manifest_path = output_dir / "vector_manifest.json"

        faiss.write_index(index, str(index_path))
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest_path.write_text(
            json.dumps(
                {
                    "embedding_provider": provider,
                    "embedding_model": model,
                    "dimension": int(matrix.shape[1]),
                    "chunk_count": len(metadata),
                    "index_path": str(index_path),
                    "metadata_path": str(metadata_path),
                    "chunks_path": str(chunks_path),
                    "embedding_input_max_chars": OPENAI_EMBEDDING_MAX_CHARS if provider == "openai" else None,
                    "trimmed_embedding_inputs": trimmed_embedding_inputs,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        result["faiss"] = {
            "dimension": int(matrix.shape[1]),
            "chunk_count": len(metadata),
            "index_path": str(index_path),
            "metadata_path": str(metadata_path),
            "manifest_path": str(manifest_path),
        }

    if backend in {"atlas", "both"} and atlas_config is not None:
        atlas_manifest_path = output_dir / "atlas_manifest.json"
        atlas_manifest_path.write_text(
            json.dumps(
                {
                    "embedding_provider": provider,
                    "embedding_model": model,
                    "chunk_count": total_chunks,
                    "chunks_path": str(chunks_path),
                    "database": atlas_config["database"],
                    "collection": atlas_config["collection"],
                    "vector_index": atlas_config["vector_index"],
                    "uri_configured": True,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        result["atlas"] = {
            "database": atlas_config["database"],
            "collection": atlas_config["collection"],
            "vector_index": atlas_config["vector_index"],
            "manifest_path": str(atlas_manifest_path),
        }

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build embedding index cho legal chunks tren FAISS hoac MongoDB Atlas.")
    parser.add_argument("--chunks", default="output/vbpl_laws_active_partial/all_chunks.jsonl", help="Path to all_chunks.jsonl")
    parser.add_argument("--output-dir", default=default_vector_dir(), help="Noi luu FAISS index va metadata")
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL, help="Embedding model")
    parser.add_argument("--batch-size", type=int, default=100, help="So chunks moi batch embedding")
    parser.add_argument("--backend", choices=["faiss", "atlas", "both"], default="faiss", help="Backend vector can build")
    parser.add_argument("--atlas-uri", default=None, help="MongoDB Atlas connection string")
    parser.add_argument("--atlas-db", default=None, help="Ten database tren Atlas")
    parser.add_argument("--atlas-collection", default=None, help="Ten collection tren Atlas")
    parser.add_argument("--atlas-vector-index", default=None, help="Ten Atlas Vector Search index")
    args = parser.parse_args()

    result = build_vector_index(
        Path(args.chunks),
        Path(args.output_dir),
        model=args.model,
        batch_size=args.batch_size,
        backend=args.backend,
        atlas_uri=args.atlas_uri,
        atlas_db=args.atlas_db,
        atlas_collection=args.atlas_collection,
        atlas_vector_index=args.atlas_vector_index,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
