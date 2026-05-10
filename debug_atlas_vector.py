from __future__ import annotations

import argparse
import json
from pathlib import Path

from atlas_vector_store import atlas_vector_search, get_atlas_collection
from build_vector_index import DEFAULT_EMBEDDING_MODEL, get_openai_client
from hybrid_retrieve import embed_query, load_atlas_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug MongoDB Atlas vector retrieval state")
    parser.add_argument("query", help="Query de test vector search")
    parser.add_argument("--vector-dir", default="output/chunks/retrieval/vector", help="Thu muc chua atlas_manifest.json")
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL, help="Embedding model cho query")
    parser.add_argument("--atlas-uri", default=None, help="MongoDB Atlas connection string")
    parser.add_argument("--atlas-db", default=None, help="Ten database tren Atlas")
    parser.add_argument("--atlas-collection", default=None, help="Ten collection tren Atlas")
    parser.add_argument("--atlas-vector-index", default=None, help="Ten Atlas Vector Search index")
    parser.add_argument("--top-k", type=int, default=3, help="So ket qua vector can xem")
    args = parser.parse_args()

    atlas_manifest = load_atlas_manifest(Path(args.vector_dir))
    collection, config = get_atlas_collection(
        uri=args.atlas_uri,
        database=args.atlas_db or atlas_manifest.get("database"),
        collection=args.atlas_collection or atlas_manifest.get("collection"),
        vector_index=args.atlas_vector_index or atlas_manifest.get("vector_index"),
    )

    client = get_openai_client()
    query_vector = embed_query(client, args.query, args.embedding_model).tolist()

    total_documents = collection.count_documents({})
    sample_document = collection.find_one({}, {"chunk_id": 1, "embedding": 1, "source_file": 1})
    sample_payload = None
    if sample_document:
        sample_payload = {
            "chunk_id": sample_document.get("chunk_id"),
            "source_file": sample_document.get("source_file"),
            "embedding_length": len(sample_document.get("embedding", [])),
        }

    vector_results = atlas_vector_search(
        collection,
        vector_index=config["vector_index"],
        query_vector=query_vector,
        top_k=args.top_k,
    )

    payload = {
        "atlas_config": config,
        "atlas_manifest": atlas_manifest,
        "document_count": total_documents,
        "sample_document": sample_payload,
        "vector_result_count": len(vector_results),
        "vector_results_preview": [
            {
                "chunk_id": item.get("chunk_id"),
                "source_file": item.get("source_file"),
                "score": item.get("score"),
            }
            for item in vector_results
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()