from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


TOKEN_RE = re.compile(r"\w+", re.UNICODE)


@dataclass
class IndexedChunk:
    chunk_id: str
    source_file: str
    vbpl_id: str | None
    doc_number: str | None
    mode: str
    article_number: str | None
    article_title: str | None
    clause_number: str | None
    point_number: str | None
    text: str
    text_length: int
    document_title: str | None
    part: str | None
    chapter: str | None
    section: str | None
    subsection: str | None
    target_law: str | None
    target_article: str | None
    quoted_inner_articles: list[str]
    searchable_text: str
    term_freqs: dict[str, int]
    doc_len: int


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def tokenize(text: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(normalize_text(text)) if token]


def build_searchable_text(chunk: dict) -> str:
    parts: list[str] = []

    if chunk.get("document_title"):
        parts.extend([chunk["document_title"], chunk["document_title"]])
    if chunk.get("doc_number"):
        parts.append(chunk["doc_number"])
    if chunk.get("article_title"):
        parts.extend([chunk["article_title"], chunk["article_title"]])
    if chunk.get("target_article"):
        parts.append(chunk["target_article"])
    if chunk.get("chapter"):
        parts.append(chunk["chapter"])
    if chunk.get("part"):
        parts.append(chunk["part"])

    parts.append(chunk["text"])
    return "\n".join(part for part in parts if part)


def load_chunks(chunks_path: Path) -> list[dict]:
    records: list[dict] = []
    for line in chunks_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    return records


def build_index_payload(chunks_path: Path) -> dict:
    raw_chunks = load_chunks(chunks_path)
    docs: list[IndexedChunk] = []
    document_frequency: Counter[str] = Counter()
    total_doc_len = 0

    for chunk in raw_chunks:
        source_file = str(chunk.get("source_file") or chunk.get("text_file") or f"vbpl/{chunk.get('vbpl_id') or chunk.get('doc_number') or chunk['chunk_id']}")
        searchable_text = build_searchable_text(chunk)
        tokens = tokenize(searchable_text)
        term_freqs = Counter(tokens)
        total_doc_len += len(tokens)
        for token in term_freqs:
            document_frequency[token] += 1

        docs.append(
            IndexedChunk(
                chunk_id=chunk["chunk_id"],
                source_file=source_file,
                vbpl_id=str(chunk.get("vbpl_id")) if chunk.get("vbpl_id") is not None else None,
                doc_number=chunk.get("doc_number"),
                mode=chunk.get("mode") or "article",
                article_number=chunk.get("article_number"),
                article_title=chunk.get("article_title"),
                clause_number=chunk.get("clause_number"),
                point_number=chunk.get("point_number"),
                text=chunk["text"],
                text_length=chunk["text_length"],
                document_title=chunk.get("document_title"),
                part=chunk.get("part"),
                chapter=chunk.get("chapter"),
                section=chunk.get("section"),
                subsection=chunk.get("subsection"),
                target_law=chunk.get("target_law"),
                target_article=chunk.get("target_article"),
                quoted_inner_articles=chunk.get("quoted_inner_articles", []),
                searchable_text=searchable_text,
                term_freqs=dict(term_freqs),
                doc_len=len(tokens),
            )
        )

    avg_doc_len = total_doc_len / len(docs) if docs else 0.0
    return {
        "chunks_path": str(chunks_path),
        "doc_count": len(docs),
        "avg_doc_len": avg_doc_len,
        "document_frequency": dict(document_frequency),
        "documents": [doc.__dict__ for doc in docs],
    }


def save_index(index_payload: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_index(index_path: Path) -> dict:
    return json.loads(index_path.read_text(encoding="utf-8"))


def bm25_score(
    query_tokens: list[str],
    doc_term_freqs: dict[str, int],
    doc_len: int,
    avg_doc_len: float,
    doc_count: int,
    document_frequency: dict[str, int],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    score = 0.0
    if not query_tokens or avg_doc_len == 0:
        return score

    for token in query_tokens:
        tf = doc_term_freqs.get(token, 0)
        if tf == 0:
            continue
        df = document_frequency.get(token, 0)
        idf = math.log(1 + (doc_count - df + 0.5) / (df + 0.5))
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * (doc_len / avg_doc_len))
        score += idf * (numerator / denominator)
    return score


def query_index(index_payload: dict, query: str, top_k: int) -> list[dict]:
    query_tokens = tokenize(query)
    results: list[dict] = []
    doc_count = index_payload["doc_count"]
    avg_doc_len = index_payload["avg_doc_len"]
    document_frequency = index_payload["document_frequency"]

    for document in index_payload["documents"]:
        score = bm25_score(
            query_tokens,
            document["term_freqs"],
            document["doc_len"],
            avg_doc_len,
            doc_count,
            document_frequency,
        )
        if score <= 0:
            continue

        preview = document["text"][:400]
        results.append(
            {
                "score": round(score, 4),
                "chunk_id": document["chunk_id"],
                "source_file": document["source_file"],
                "vbpl_id": document.get("vbpl_id"),
                "doc_number": document.get("doc_number"),
                "article_number": document.get("article_number"),
                "clause_number": document.get("clause_number"),
                "point_number": document.get("point_number"),
                "document_title": document.get("document_title"),
                "chapter": document.get("chapter"),
                "target_article": document.get("target_article"),
                "preview": preview,
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


def resolve_default_index_path(chunks_path: Path) -> Path:
    return chunks_path.parent / "retrieval" / "bm25_index.json"


def main() -> None:
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build/query BM25 retrieval index for legal chunks.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build BM25 index from all_chunks.jsonl")
    build_parser.add_argument("--chunks", default="output/vbpl_laws_active_partial/all_chunks.jsonl", help="Path to all_chunks.jsonl")
    build_parser.add_argument("--output", help="Path to output BM25 index JSON")

    query_parser = subparsers.add_parser("query", help="Query BM25 index")
    query_parser.add_argument("query", help="Natural language legal query")
    query_parser.add_argument("--index", default="output/vbpl_laws_active_partial/retrieval/bm25_index.json", help="Path to BM25 index JSON")
    query_parser.add_argument("--top-k", type=int, default=5, help="Number of top results")

    args = parser.parse_args()

    if args.command == "build":
        chunks_path = Path(args.chunks)
        output_path = Path(args.output) if args.output else resolve_default_index_path(chunks_path)
        index_payload = build_index_payload(chunks_path)
        save_index(index_payload, output_path)
        print(json.dumps({"doc_count": index_payload["doc_count"], "output": str(output_path)}, ensure_ascii=False))
        return

    index_path = Path(args.index)
    index_payload = load_index(index_path)
    results = query_index(index_payload, args.query, args.top_k)
    print(json.dumps({"query": args.query, "top_k": args.top_k, "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
