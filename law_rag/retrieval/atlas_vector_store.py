from __future__ import annotations

import os

from pymongo import MongoClient, ReplaceOne
from pymongo.collection import Collection

from ..core.env_loader import load_project_env


DEFAULT_ATLAS_DB = "law_rag"
DEFAULT_ATLAS_COLLECTION = "legal_chunks"
DEFAULT_ATLAS_VECTOR_INDEX = "legal_chunks_vector_index"


load_project_env()


def get_atlas_config(
    *,
    uri: str | None = None,
    database: str | None = None,
    collection: str | None = None,
    vector_index: str | None = None,
) -> dict[str, str]:
    config = {
        "uri": uri or os.getenv("MONGODB_ATLAS_URI", ""),
        "database": database or os.getenv("MONGODB_ATLAS_DB", DEFAULT_ATLAS_DB),
        "collection": collection or os.getenv("MONGODB_ATLAS_COLLECTION", DEFAULT_ATLAS_COLLECTION),
        "vector_index": vector_index or os.getenv("MONGODB_ATLAS_VECTOR_INDEX", DEFAULT_ATLAS_VECTOR_INDEX),
    }
    if not config["uri"]:
        raise RuntimeError("Thieu MONGODB_ATLAS_URI trong environment hoac CLI.")
    return config


def get_atlas_collection(
    *,
    uri: str | None = None,
    database: str | None = None,
    collection: str | None = None,
    vector_index: str | None = None,
) -> tuple[Collection, dict[str, str]]:
    config = get_atlas_config(uri=uri, database=database, collection=collection, vector_index=vector_index)
    client = MongoClient(config["uri"])
    return client[config["database"]][config["collection"]], config


def build_atlas_document(chunk: dict, searchable_text: str, embedding: list[float]) -> dict:
    return {
        "_id": chunk["chunk_id"],
        "chunk_id": chunk["chunk_id"],
        "source_file": chunk["source_file"],
        "mode": chunk["mode"],
        "article_number": chunk.get("article_number"),
        "clause_number": chunk.get("clause_number"),
        "point_number": chunk.get("point_number"),
        "document_title": chunk.get("document_title"),
        "chapter": chunk.get("chapter"),
        "part": chunk.get("part"),
        "target_article": chunk.get("target_article"),
        "text": chunk["text"],
        "searchable_text": searchable_text,
        "embedding": embedding,
    }


def upsert_atlas_documents(collection: Collection, documents: list[dict]) -> dict[str, int]:
    if not documents:
        return {"matched": 0, "modified": 0, "upserted": 0}

    operations = [ReplaceOne({"_id": document["_id"]}, document, upsert=True) for document in documents]
    result = collection.bulk_write(operations, ordered=False)
    return {
        "matched": int(result.matched_count),
        "modified": int(result.modified_count),
        "upserted": int(len(result.upserted_ids)),
    }


def atlas_vector_search(
    collection: Collection,
    *,
    vector_index: str,
    query_vector: list[float],
    top_k: int,
    num_candidates: int | None = None,
) -> list[dict]:
    pipeline = [
        {
            "$vectorSearch": {
                "index": vector_index,
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": num_candidates or max(top_k * 20, 100),
                "limit": top_k,
            }
        },
        {
            "$project": {
                "_id": 0,
                "chunk_id": 1,
                "source_file": 1,
                "article_number": 1,
                "clause_number": 1,
                "point_number": 1,
                "document_title": 1,
                "chapter": 1,
                "part": 1,
                "target_article": 1,
                "text": 1,
                "searchable_text": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    return list(collection.aggregate(pipeline))