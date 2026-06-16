from __future__ import annotations

import argparse
import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Iterable

from .retrieve_chunks import build_searchable_text, tokenize


SCHEMA_VERSION = 1
BM25_OR_FALLBACK_MAX_TOKENS = 5
LEGAL_IDENTIFIER_RE = re.compile(
    r"\b\d{1,4}\s*[/\-]\s*\d{4}\s*[/\-]\s*[A-Za-zÀ-ỹĐđ]+(?:\s*[-/]\s*[A-Za-zÀ-ỹĐđ0-9]+)*\b",
    re.IGNORECASE,
)


def default_store_path_for_chunks(chunks_path: Path) -> Path:
    return chunks_path.parent / "retrieval" / "retrieval_store.sqlite"


def default_store_path_for_bm25_index(bm25_index_path: Path) -> Path:
    return bm25_index_path.parent / "retrieval_store.sqlite"


def normalize_fts_token(token: str) -> str:
    normalized = unicodedata.normalize("NFD", token.casefold())
    return "".join(character for character in normalized if unicodedata.category(character) != "Mn")


def normalize_identifier(text: str) -> str:
    normalized = normalize_fts_token(str(text or "")).replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", "", normalized)


def query_legal_identifiers(query: str) -> set[str]:
    return {normalize_identifier(match.group(0)) for match in LEGAL_IDENTIFIER_RE.finditer(query)}


def item_matches_identifier(item: dict, identifiers: set[str]) -> bool:
    if not identifiers:
        return False
    searchable = " ".join(
        str(item.get(key) or "")
        for key in ("doc_number", "document_title", "source_file")
    )
    normalized = normalize_identifier(searchable)
    return any(identifier and identifier in normalized for identifier in identifiers)


def query_content_tokens(query: str) -> set[str]:
    query_without_identifiers = LEGAL_IDENTIFIER_RE.sub(" ", query)
    stopwords = {
        "nghi",
        "dinh",
        "nd",
        "cp",
        "so",
        "ve",
        "cua",
        "theo",
        "tai",
        "trong",
        "quy",
        "dieu",
        "khoan",
    }
    tokens: set[str] = set()
    for token in tokenize(query_without_identifiers):
        normalized = normalize_fts_token(token).replace("đ", "d")
        if len(normalized) < 2 or normalized.isdigit() or normalized in stopwords:
            continue
        tokens.add(normalized)
    return tokens


def content_overlap_score(item: dict, tokens: set[str]) -> float:
    if not tokens:
        return 0.0
    text = str(item.get("text") or "")
    heading = text.splitlines()[0] if text.splitlines() else ""
    early_text = text[:700]
    normalized_heading = normalize_fts_token(heading).replace("đ", "d")
    normalized_early_text = normalize_fts_token(early_text).replace("đ", "d")
    normalized_text = normalize_fts_token(text).replace("đ", "d")
    weighted_hits = 0.0
    for token in tokens:
        if token in normalized_heading:
            weighted_hits += 3.0
        elif token in normalized_early_text:
            weighted_hits += 2.0
        elif token in normalized_text:
            weighted_hits += 1.0
    return weighted_hits / (len(tokens) * 3.0)


def fts_match_query(query: str, *, operator: str = "AND") -> str:
    tokens = fts_query_tokens(query)
    return f" {operator} ".join(tokens)


def fts_query_tokens(query: str) -> list[str]:
    tokens = []
    seen: set[str] = set()
    for token in tokenize(query):
        normalized = normalize_fts_token(token)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        tokens.append(f'"{normalized.replace(chr(34), chr(34) + chr(34))}"')
    return tokens


def compact_chunk_metadata(chunk: dict) -> dict:
    source_file = str(
        chunk.get("source_file")
        or chunk.get("text_file")
        or f"vbpl/{chunk.get('vbpl_id') or chunk.get('doc_number') or chunk['chunk_id']}"
    )
    text = str(chunk.get("text") or "")
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
        "section": chunk.get("section"),
        "part": chunk.get("part"),
        "parent_chunk_id": chunk.get("parent_chunk_id"),
        "parent_context_text": chunk.get("parent_context_text"),
        "merged_short_chunk": chunk.get("merged_short_chunk"),
        "merged_chunk_ids": chunk.get("merged_chunk_ids"),
        "merged_clause_numbers": chunk.get("merged_clause_numbers"),
        "merged_point_numbers": chunk.get("merged_point_numbers"),
        "target_article": chunk.get("target_article"),
        "text": text,
    }


class SQLiteRetrievalStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def get_metadata_by_vector_indices(self, indices: Iterable[int]) -> dict[int, dict]:
        valid_indices = [int(index) for index in indices if int(index) >= 0]
        if not valid_indices:
            return {}

        rowids = [index + 1 for index in valid_indices]
        placeholders = ",".join("?" for _ in rowids)
        rows = self.connection.execute(
            f"SELECT rowid, metadata FROM chunks WHERE rowid IN ({placeholders})",
            rowids,
        ).fetchall()
        return {int(row["rowid"]) - 1: json.loads(row["metadata"]) for row in rows}

    def query_bm25(self, query: str, top_k: int) -> list[dict]:
        query_tokens = fts_query_tokens(query)
        legal_identifiers = query_legal_identifiers(query)
        fetch_k = max(top_k * 40, 100) if legal_identifiers else top_k
        match_query = fts_match_query(query, operator="AND")
        if not match_query:
            return []

        rows = self._query_bm25_match(match_query, fetch_k)
        if not rows and len(query_tokens) <= BM25_OR_FALLBACK_MAX_TOKENS:
            fallback_query = fts_match_query(query, operator="OR")
            if fallback_query != match_query:
                rows = self._query_bm25_match(fallback_query, fetch_k)

        results: list[dict] = []
        for row in rows:
            item = json.loads(row["metadata"])
            score = -float(row["raw_score"] or 0.0)
            text = str(item.get("text") or "")
            results.append(
                {
                    "score": round(score, 4),
                    "chunk_id": item["chunk_id"],
                    "source_file": item["source_file"],
                    "vbpl_id": item.get("vbpl_id"),
                    "doc_number": item.get("doc_number"),
                    "doc_type": item.get("doc_type"),
                    "source_url": item.get("source_url"),
                    "issue_date": item.get("issue_date"),
                    "article_number": item.get("article_number"),
                    "clause_number": item.get("clause_number"),
                    "point_number": item.get("point_number"),
                    "document_title": item.get("document_title"),
                    "chapter": item.get("chapter"),
                    "section": item.get("section"),
                    "parent_chunk_id": item.get("parent_chunk_id"),
                    "parent_context_text": item.get("parent_context_text"),
                    "merged_short_chunk": item.get("merged_short_chunk"),
                    "merged_chunk_ids": item.get("merged_chunk_ids"),
                    "merged_clause_numbers": item.get("merged_clause_numbers"),
                    "merged_point_numbers": item.get("merged_point_numbers"),
                    "target_article": item.get("target_article"),
                    "preview": text[:400],
                    "text": text,
                }
            )
        if legal_identifiers:
            exact_document_results = [
                item for item in results if item_matches_identifier(item, legal_identifiers)
            ]
            if exact_document_results:
                results = exact_document_results
                content_tokens = query_content_tokens(query)
                if content_tokens:
                    results.sort(
                        key=lambda item: (
                            content_overlap_score(item, content_tokens),
                            item["score"],
                        ),
                        reverse=True,
                    )
        return results[:top_k]

    def _query_bm25_match(self, match_query: str, top_k: int) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT c.metadata, bm25(chunks_fts) AS raw_score
            FROM chunks_fts
            JOIN chunks c ON c.rowid = chunks_fts.rowid
            WHERE chunks_fts MATCH ?
            ORDER BY raw_score
            LIMIT ?
            """,
            (match_query, top_k),
        ).fetchall()


def open_store_if_exists(path: Path) -> SQLiteRetrievalStore | None:
    if not path.exists():
        return None
    return SQLiteRetrievalStore(path)


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE chunks (
            rowid INTEGER PRIMARY KEY,
            chunk_id TEXT NOT NULL UNIQUE,
            source_file TEXT NOT NULL,
            metadata TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            searchable_text,
            content='',
            tokenize='unicode61 remove_diacritics 2'
        );
        """
    )


def build_sqlite_retrieval_store(*, chunks_path: Path, output_path: Path, commit_every: int = 5_000) -> dict:
    if not chunks_path.exists():
        raise RuntimeError(f"Khong tim thay chunks file: {chunks_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    if temp_path.exists():
        temp_path.unlink()

    connection = sqlite3.connect(temp_path)
    try:
        connection.execute("PRAGMA journal_mode = OFF")
        connection.execute("PRAGMA synchronous = OFF")
        connection.execute("PRAGMA temp_store = MEMORY")
        initialize_schema(connection)
        connection.execute(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        connection.execute(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            ("chunks_path", str(chunks_path)),
        )

        count = 0
        with chunks_path.open(encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                metadata = compact_chunk_metadata(chunk)
                searchable_text = build_searchable_text(chunk)
                count += 1
                connection.execute(
                    "INSERT INTO chunks(rowid, chunk_id, source_file, metadata) VALUES (?, ?, ?, ?)",
                    (
                        count,
                        metadata["chunk_id"],
                        metadata["source_file"],
                        json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
                    ),
                )
                connection.execute(
                    "INSERT INTO chunks_fts(rowid, searchable_text) VALUES (?, ?)",
                    (count, searchable_text),
                )
                if count % commit_every == 0:
                    connection.commit()
                    print(f"[sqlite-store] {count} chunks", flush=True)

        connection.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
            ("chunk_count", str(count)),
        )
        connection.commit()
        connection.execute("INSERT INTO chunks_fts(chunks_fts) VALUES ('optimize')")
        connection.commit()
    finally:
        connection.close()

    temp_path.replace(output_path)
    return {
        "schema_version": SCHEMA_VERSION,
        "chunk_count": count,
        "chunks_path": str(chunks_path),
        "store_path": str(output_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SQLite/FTS5 retrieval store tu all_chunks.jsonl.")
    parser.add_argument("--chunks", required=True, help="Path toi all_chunks.jsonl")
    parser.add_argument("--output", help="Path toi retrieval_store.sqlite")
    args = parser.parse_args()

    chunks_path = Path(args.chunks)
    output_path = Path(args.output) if args.output else default_store_path_for_chunks(chunks_path)
    result = build_sqlite_retrieval_store(chunks_path=chunks_path, output_path=output_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
