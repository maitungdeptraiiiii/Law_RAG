from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


TOKEN_RE = re.compile(r"\w+", re.UNICODE)
MAX_SEARCHABLE_METADATA_CHARS = 500
MAX_SEARCHABLE_FIELD_CHARS = 250
MAX_SEARCHABLE_LIST_ITEMS = 20


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
    parent_chunk_id: str | None
    parent_context_text: str | None
    merged_short_chunk: bool | None
    merged_chunk_ids: list[str] | None
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
        title = _limit_searchable_field(str(chunk["document_title"]))
        parts.extend(
            [
                f"Tên văn bản: {title}",
                f"Tên văn bản: {title}",
            ]
        )
    if chunk.get("doc_number"):
        parts.append(f"Số văn bản: {chunk['doc_number']}")
    if chunk.get("doc_type"):
        parts.append(f"Loại văn bản: {chunk['doc_type']}")
    if chunk.get("effective_status"):
        parts.append(f"Tình trạng hiệu lực: {chunk['effective_status']}")
    if chunk.get("agency_name"):
        parts.append(f"Cơ quan ban hành: {chunk['agency_name']}")
    if chunk.get("issue_date"):
        parts.append(f"Ngày ban hành: {chunk['issue_date']}")
    if chunk.get("effective_from"):
        parts.append(f"Ngày có hiệu lực: {chunk['effective_from']}")
    if chunk.get("effective_to"):
        parts.append(f"Ngày hết hiệu lực: {chunk['effective_to']}")
    if chunk.get("majors"):
        majors = _join_searchable_list(chunk["majors"])
        if majors:
            parts.append(f"Ngành/Lĩnh vực chính: {majors}")
    if chunk.get("fields"):
        fields = _join_searchable_list(chunk["fields"])
        if fields:
            parts.append(f"Lĩnh vực: {fields}")
    if chunk.get("chapter"):
        parts.append(f"Chương: {_limit_searchable_field(str(chunk['chapter']))}")
    if chunk.get("part"):
        parts.append(f"Phần: {_limit_searchable_field(str(chunk['part']))}")
    if chunk.get("section"):
        parts.append(f"Mục: {_limit_searchable_field(str(chunk['section']))}")
    if chunk.get("subsection"):
        parts.append(f"Tiểu mục: {_limit_searchable_field(str(chunk['subsection']))}")
    if chunk.get("article_number"):
        parts.append(f"Điều: {chunk['article_number']}")
    if chunk.get("article_title"):
        article_title = _limit_searchable_field(str(chunk["article_title"]))
        parts.extend(
            [
                f"Tên điều: {article_title}",
                f"Tên điều: {article_title}",
            ]
        )
    if chunk.get("clause_number"):
        parts.append(f"Khoản: {chunk['clause_number']}")
    if chunk.get("point_number"):
        parts.append(f"Điểm: {chunk['point_number']}")
    if chunk.get("target_law"):
        parts.append(f"Văn bản liên quan: {_limit_searchable_field(str(chunk['target_law']))}")
    if chunk.get("target_article"):
        parts.append(f"Điều liên quan: {_limit_searchable_field(str(chunk['target_article']))}")
    if chunk.get("quoted_inner_articles"):
        quoted_articles = _join_searchable_list(chunk["quoted_inner_articles"])
        if quoted_articles:
            parts.append(f"Điều được dẫn chiếu trong nội dung: {quoted_articles}")
    if chunk.get("metadata_text"):
        parts.append(f"Metadata: {_limit_searchable_metadata(str(chunk['metadata_text']))}")
    if chunk.get("parent_context_text"):
        parts.append(f"Ngữ cảnh cha: {_limit_searchable_metadata(str(chunk['parent_context_text']))}")
    if chunk.get("display_title"):
        parts.append(f"Tiêu đề hiển thị: {_limit_searchable_field(str(chunk['display_title']))}")

    parts.append("Nội dung:")
    parts.append(chunk["text"])
    return "\n".join(part for part in parts if part)


def _limit_searchable_metadata(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= MAX_SEARCHABLE_METADATA_CHARS:
        return normalized
    return normalized[:MAX_SEARCHABLE_METADATA_CHARS].rsplit(" ", 1)[0].strip()


def _limit_searchable_field(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= MAX_SEARCHABLE_FIELD_CHARS:
        return normalized
    return normalized[:MAX_SEARCHABLE_FIELD_CHARS].rsplit(" ", 1)[0].strip()


def _join_searchable_list(values: list[object]) -> str:
    return ", ".join(
        item
        for item in (
            _limit_searchable_field(str(value))
            for value in values[:MAX_SEARCHABLE_LIST_ITEMS]
        )
        if item
    )


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
                parent_chunk_id=chunk.get("parent_chunk_id"),
                parent_context_text=chunk.get("parent_context_text"),
                merged_short_chunk=chunk.get("merged_short_chunk"),
                merged_chunk_ids=chunk.get("merged_chunk_ids"),
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
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(index_payload, handle, ensure_ascii=False, separators=(",", ":"))
    temp_path.replace(output_path)


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
                "parent_chunk_id": document.get("parent_chunk_id"),
                "parent_context_text": document.get("parent_context_text"),
                "merged_short_chunk": document.get("merged_short_chunk"),
                "merged_chunk_ids": document.get("merged_chunk_ids"),
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
