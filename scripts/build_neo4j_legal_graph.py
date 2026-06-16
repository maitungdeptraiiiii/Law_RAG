from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from law_rag.core.env_loader import load_project_env
from law_rag.retrieval.neo4j_store import Neo4jLegalGraphStore


ARTICLE_REF_RE = re.compile(r"\bĐiều\s+(\d+[a-z]?)\b", re.IGNORECASE)


def batched(items: Iterable[dict[str, Any]], batch_size: int) -> Iterable[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for item in items:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def article_id(chunk: dict[str, Any]) -> str:
    vbpl_id = str(chunk.get("vbpl_id") or chunk.get("doc_number") or chunk.get("source_file") or "doc")
    article_number = str(chunk.get("article_number") or "")
    return f"{vbpl_id}:article:{article_number}"


def document_id(chunk: dict[str, Any]) -> str:
    return str(chunk.get("vbpl_id") or chunk.get("doc_number") or chunk.get("source_file") or "doc")


def iter_article_rows(chunks_path: Path) -> Iterable[dict[str, Any]]:
    with chunks_path.open(encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            chunk = json.loads(line)
            if not chunk.get("article_number"):
                continue
            text = str(chunk.get("text") or "")
            yield {
                "article_id": article_id(chunk),
                "document_id": document_id(chunk),
                "chunk_id": chunk.get("chunk_id"),
                "parent_chunk_id": chunk.get("parent_chunk_id"),
                "source_file": chunk.get("source_file"),
                "vbpl_id": str(chunk.get("vbpl_id")) if chunk.get("vbpl_id") is not None else None,
                "doc_number": chunk.get("doc_number"),
                "doc_type": chunk.get("doc_type"),
                "document_title": chunk.get("document_title"),
                "source_url": chunk.get("source_url"),
                "issue_date": chunk.get("issue_date"),
                "article_number": str(chunk.get("article_number")),
                "article_title": chunk.get("article_title"),
                "clause_number": str(chunk.get("clause_number")) if chunk.get("clause_number") is not None else None,
                "point_number": str(chunk.get("point_number")) if chunk.get("point_number") is not None else None,
                "part_index": chunk.get("part_index"),
                "part_count": chunk.get("part_count"),
                "subchunk_number": chunk.get("subchunk_number"),
                "subchunk_count": chunk.get("subchunk_count"),
                "fallback_split": bool(chunk.get("fallback_split")),
                "display_title": chunk.get("display_title"),
                "chapter": chunk.get("chapter"),
                "section": chunk.get("section"),
                "text": text,
            }


def iter_article_references(chunks_path: Path) -> Iterable[dict[str, str]]:
    with chunks_path.open(encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            chunk = json.loads(line)
            source_article = chunk.get("article_number")
            if not source_article:
                continue
            source_article_id = article_id(chunk)
            seen: set[str] = set()
            for match in ARTICLE_REF_RE.finditer(str(chunk.get("text") or "")):
                target_article = match.group(1)
                if target_article == str(source_article) or target_article in seen:
                    continue
                seen.add(target_article)
                yield {
                    "source_article_id": source_article_id,
                    "target_article_number": target_article,
                }


def document_title_hints(rule: dict[str, Any]) -> list[str]:
    hints = rule.get("document_title_hints")
    if isinstance(hints, list) and hints:
        return [str(item) for item in hints if str(item).strip()]

    preferred = {str(item) for item in rule.get("preferred_articles", [])}
    issue_type = str(rule.get("issue_type") or "")
    if preferred and all(item.isdigit() and int(item) < 300 for item in preferred) and issue_type.startswith(("chiem_doat", "xam_pham")):
        return ["Bộ luật Hình sự"]
    if issue_type == "nghia_vu_dan_su":
        return ["Bộ luật Dân sự"]
    if issue_type == "bao_hiem_y_te":
        return ["Luật Bảo hiểm y tế"]
    if issue_type == "bao_hiem_xa_hoi":
        return ["Luật Bảo hiểm xã hội"]
    return ["Bộ luật", "Luật"]


def load_issue_rows(rules_path: Path) -> list[dict[str, Any]]:
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        retrieval_queries = rule.get("retrieval_queries", [])
        semantic_queries = rule.get("semantic_queries", [])
        rows.append(
            {
                "label": str(rule.get("label") or ""),
                "issue_type": str(rule.get("issue_type") or ""),
                "confidence": float(rule.get("confidence") or 0.0),
                "retrieval_queries": [str(item) for item in retrieval_queries] if isinstance(retrieval_queries, list) else [],
                "semantic_queries": [str(item) for item in semantic_queries] if isinstance(semantic_queries, list) else [],
                "preferred_articles": [str(item) for item in rule.get("preferred_articles", [])],
                "distinguish_from_articles": [str(item) for item in rule.get("distinguish_from_articles", [])],
                "document_title_hints": document_title_hints(rule),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Neo4j legal graph from Law-RAG corpus metadata.")
    parser.add_argument("--chunks", default="output/vbpl_merged_reuse_openai/all_chunks.jsonl")
    parser.add_argument("--issue-rules", default="law_rag/retrieval/legal_issues_full_all_added.json")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--skip-references", action="store_true")
    parser.add_argument("--wait-seconds", type=int, default=120, help="Wait this long for Neo4j Bolt to become ready.")
    args = parser.parse_args()

    load_project_env()
    chunks_path = Path(args.chunks)
    rules_path = Path(args.issue_rules)
    store = Neo4jLegalGraphStore()
    try:
        deadline = time.monotonic() + max(0, args.wait_seconds)
        while True:
            try:
                store.verify_connectivity()
                break
            except Exception as exc:
                if time.monotonic() >= deadline:
                    raise
                print(f"Waiting for Neo4j Bolt to become ready: {exc}")
                time.sleep(3)

        store.ensure_schema()
        print("Ensured Neo4j constraints/indexes.")

        article_count = 0
        for batch in batched(iter_article_rows(chunks_path), args.batch_size):
            store.upsert_articles(batch)
            article_count += len(batch)
            print(f"Upserted articles: {article_count}")

        issue_rows = load_issue_rows(rules_path)
        store.upsert_legal_issues(issue_rows)
        print(f"Upserted legal issues: {len(issue_rows)}")

        reference_count = 0
        if not args.skip_references:
            for batch in batched(iter_article_references(chunks_path), args.batch_size):
                store.upsert_references(batch)
                reference_count += len(batch)
                print(f"Upserted references: {reference_count}")

        print(json.dumps({"articles": article_count, "issues": len(issue_rows), "references": reference_count}, ensure_ascii=False, indent=2))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
