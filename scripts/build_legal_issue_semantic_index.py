from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import faiss

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from law_rag.core.embedding_client import DEFAULT_EMBEDDING_MODEL, embed_texts, embedding_provider
from law_rag.core.env_loader import load_project_env


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def rule_text(value: Any) -> str:
    return str(value or "").strip()


def build_embedding_text(rule: dict[str, Any], semantic_query: str) -> str:
    display_name = rule_text(rule.get("display_name") or rule.get("label"))
    issue_type_name = rule_text(rule.get("issue_type_name") or rule.get("issue_type"))
    description = rule_text(rule.get("description"))
    parts = [
        f"Vấn đề pháp lý: {display_name}." if display_name else "",
        f"Loại: {issue_type_name}." if issue_type_name else "",
        f"Tình huống: {semantic_query}.",
        f"Mô tả: {description}" if description else "",
    ]
    return "\n".join(part for part in parts if part)


def semantic_entries(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        retrieval_queries = as_str_list(rule.get("retrieval_queries", []))
        for semantic_query in as_str_list(rule.get("semantic_queries", [])):
            entries.append(
                {
                    "label": str(rule.get("label") or rule.get("issue_type") or "").strip(),
                    "issue_type": str(rule.get("issue_type") or "").strip(),
                    "display_name": rule_text(rule.get("display_name")),
                    "issue_type_name": rule_text(rule.get("issue_type_name")),
                    "description": rule_text(rule.get("description")),
                    "confidence": float(rule.get("confidence") or 0.0),
                    "semantic_query": semantic_query,
                    "embedding_text": build_embedding_text(rule, semantic_query),
                    "retrieval_queries": retrieval_queries,
                    "preferred_articles": as_str_list(rule.get("preferred_articles", [])),
                    "distinguish_from_articles": as_str_list(
                        rule.get("distinguish_from_articles", rule.get("avoid_articles", []))
                    ),
                    "document_title_hints": as_str_list(rule.get("document_title_hints", [])),
                }
            )
    return entries


def normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def main() -> int:
    parser = argparse.ArgumentParser(description="Build persistent embeddings for legal issue semantic queries.")
    parser.add_argument("--rules", default="law_rag/retrieval/legal_issues_full_all_added.json")
    parser.add_argument("--output-dir", default="output/legal_issue_semantic_index")
    parser.add_argument("--batch-size", type=int, default=96)
    args = parser.parse_args()

    load_project_env()
    rules_path = Path(args.rules)
    output_dir = Path(args.output_dir)
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    if not isinstance(rules, list):
        raise ValueError(f"Legal issue rules must be a JSON array: {rules_path}")

    entries = semantic_entries(rules)
    texts = [entry["embedding_text"] for entry in entries]
    if not texts:
        raise ValueError(f"No semantic_queries found in {rules_path}")

    vectors: list[list[float]] = []
    batch_size = max(1, args.batch_size)
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        vectors.extend(embed_texts(batch))
        print(f"Embedded semantic queries: {min(start + len(batch), len(texts))}/{len(texts)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    vector_array = np.asarray(vectors, dtype="float32")
    normalized_vectors = normalize_vectors(vector_array).astype("float32")
    faiss_index = faiss.IndexFlatIP(normalized_vectors.shape[1])
    faiss_index.add(normalized_vectors)
    faiss.write_index(faiss_index, str(output_dir / "faiss.index"))
    np.save(output_dir / "vectors.npy", normalized_vectors)
    metadata = {
        "version": 2,
        "rules_path": str(rules_path),
        "rules_sha256": file_sha256(rules_path),
        "embedding_provider": embedding_provider(),
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "embedding_text_strategy": "issue_context_plus_semantic_query",
        "index_backend": "faiss",
        "faiss_metric": "inner_product_on_l2_normalized_vectors",
        "vector_shape": list(normalized_vectors.shape),
        "entries": entries,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"entries": len(entries), "output_dir": str(output_dir)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
