from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import faiss
import numpy as np


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_metadata(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path)
    if not isinstance(payload, list):
        raise RuntimeError(f"Metadata must be a list: {path}")
    return payload


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as target:
        for record in records:
            target.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line in source:
            if line.strip():
                records.append(json.loads(line))
    return records


def reconstruct_matrix(index: faiss.Index) -> np.ndarray:
    vectors = np.empty((index.ntotal, index.d), dtype="float32")
    for start in range(0, index.ntotal, 100_000):
        count = min(100_000, index.ntotal - start)
        vectors[start : start + count] = index.reconstruct_n(start, count)
    return vectors


def validate_manifests(manifests: list[dict[str, Any]]) -> dict[str, Any]:
    first = manifests[0]
    provider = first.get("embedding_provider")
    model = first.get("embedding_model")
    dimension = first.get("dimension")
    for manifest in manifests[1:]:
        if manifest.get("embedding_provider") != provider:
            raise RuntimeError("Embedding providers differ; refusing to merge.")
        if manifest.get("embedding_model") != model:
            raise RuntimeError("Embedding models differ; refusing to merge.")
        if manifest.get("dimension") != dimension:
            raise RuntimeError("Embedding dimensions differ; refusing to merge.")
    return {"embedding_provider": provider, "embedding_model": model, "dimension": dimension}


def prefixed_if_duplicate(record: dict[str, Any], *, corpus_name: str, seen: set[str]) -> dict[str, Any]:
    chunk_id = str(record.get("chunk_id") or "")
    if chunk_id and chunk_id not in seen:
        seen.add(chunk_id)
        return record
    updated = dict(record)
    updated["chunk_id"] = f"{corpus_name}:{chunk_id or len(seen) + 1}"
    seen.add(updated["chunk_id"])
    return updated


def merge_corpora(corpus_dirs: list[Path], output_dir: Path) -> dict[str, Any]:
    manifests: list[dict[str, Any]] = []
    indexes: list[faiss.Index] = []
    all_metadata: list[dict[str, Any]] = []
    all_chunks: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()

    for corpus_dir in corpus_dirs:
        vector_dir = corpus_dir / "retrieval" / "vector-openai"
        manifest_path = vector_dir / "vector_manifest.json"
        index_path = vector_dir / "faiss.index"
        metadata_path = vector_dir / "vector_metadata.json"
        chunks_path = corpus_dir / "all_chunks.jsonl"

        for path in [manifest_path, index_path, metadata_path, chunks_path]:
            if not path.exists():
                raise RuntimeError(f"Missing required file: {path}")

        manifest = read_json(manifest_path)
        metadata = load_metadata(metadata_path)
        index = faiss.read_index(str(index_path))
        chunks = load_jsonl(chunks_path)

        if index.ntotal != len(metadata):
            raise RuntimeError(f"Index/metadata count mismatch in {corpus_dir}: {index.ntotal} != {len(metadata)}")

        corpus_name = corpus_dir.name
        manifests.append(manifest)
        indexes.append(index)
        all_metadata.extend(prefixed_if_duplicate(item, corpus_name=corpus_name, seen=seen_chunk_ids) for item in metadata)
        all_chunks.extend(chunks)

    config = validate_manifests(manifests)
    output_vector_dir = output_dir / "retrieval" / "vector-openai"
    output_vector_dir.mkdir(parents=True, exist_ok=True)

    merged_matrix = np.vstack([reconstruct_matrix(index) for index in indexes])
    faiss.normalize_L2(merged_matrix)
    merged_index = faiss.IndexFlatIP(int(config["dimension"]))
    merged_index.add(merged_matrix)

    index_path = output_vector_dir / "faiss.index"
    metadata_path = output_vector_dir / "vector_metadata.json"
    manifest_path = output_vector_dir / "vector_manifest.json"
    chunks_path = output_dir / "all_chunks.jsonl"

    faiss.write_index(merged_index, str(index_path))
    metadata_path.write_text(json.dumps(all_metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    write_jsonl(chunks_path, all_chunks)

    documents_jsonl_sources = [corpus_dir / "documents.jsonl" for corpus_dir in corpus_dirs if (corpus_dir / "documents.jsonl").exists()]
    if documents_jsonl_sources:
        with (output_dir / "documents.jsonl").open("w", encoding="utf-8") as target:
            for source in documents_jsonl_sources:
                target.write(source.read_text(encoding="utf-8"))

    for name in ["documents.json", "manifest.json", "documents.csv"]:
        first_existing = next((corpus_dir / name for corpus_dir in corpus_dirs if (corpus_dir / name).exists()), None)
        if first_existing is not None and not (output_dir / name).exists():
            shutil.copy2(first_existing, output_dir / name)

    manifest = {
        **config,
        "chunk_count": int(merged_index.ntotal),
        "index_path": str(index_path),
        "metadata_path": str(metadata_path),
        "chunks_path": str(chunks_path),
        "merged_from": [str(path) for path in corpus_dirs],
        "embedding_reused": True,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge OpenAI FAISS vector corpora without re-embedding.")
    parser.add_argument("--output", required=True, help="Output corpus directory")
    parser.add_argument("corpus_dirs", nargs="+", help="Corpus directories to merge")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = merge_corpora([Path(path) for path in args.corpus_dirs], Path(args.output))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
