from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from law_rag.legal_chunking import DEFAULT_MAX_CHUNK_CHARS, DEFAULT_OVERLAP_CHARS, split_legal_chunk
from law_rag.retrieval.retrieve_chunks import build_searchable_text


DEFAULT_MAX_SEARCHABLE_CHARS = 5_500
PART_SUFFIX_RE = re.compile(r":part:(\d+)$")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as target:
        for record in records:
            target.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    temp_path.replace(path)


def base_chunk_id(chunk_id: str) -> str:
    return PART_SUFFIX_RE.sub("", chunk_id)


def merge_existing_parts(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    index_by_key: dict[tuple[Any, ...], int] = {}

    for record in records:
        chunk_id = str(record.get("chunk_id") or "")
        match = PART_SUFFIX_RE.search(chunk_id)
        if not match:
            merged.append(record)
            continue

        key = (
            record.get("source_file") or record.get("text_file"),
            record.get("vbpl_id"),
            base_chunk_id(chunk_id),
        )
        if key not in index_by_key:
            combined = dict(record)
            combined["chunk_id"] = base_chunk_id(chunk_id)
            combined.pop("subchunk_number", None)
            combined.pop("subchunk_count", None)
            combined.pop("part_index", None)
            combined.pop("part_count", None)
            combined.pop("parent_chunk_id", None)
            combined["text"] = str(record.get("text") or "").strip()
            combined["text_length"] = len(combined["text"])
            index_by_key[key] = len(merged)
            merged.append(combined)
            continue

        combined = merged[index_by_key[key]]
        current_text = str(combined.get("text") or "").strip()
        next_text = str(record.get("text") or "").strip()
        combined["text"] = "\n".join(part for part in [current_text, next_text] if part)
        combined["text_length"] = len(combined["text"])

    return merged


def unique_chunk_id(chunk: dict[str, Any], seen: set[str]) -> dict[str, Any]:
    chunk_id = str(chunk["chunk_id"])
    if chunk_id not in seen:
        seen.add(chunk_id)
        return chunk

    suffix = 2
    while f"{chunk_id}:dup:{suffix}" in seen:
        suffix += 1
    updated = dict(chunk)
    updated["chunk_id"] = f"{chunk_id}:dup:{suffix}"
    seen.add(updated["chunk_id"])
    return updated


def rechunk_records(
    records: list[dict[str, Any]],
    *,
    max_chars: int,
    max_searchable_chars: int,
    overlap_chars: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    merged_records = merge_existing_parts(records)
    output: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    changed_records = 0
    fallback_splits = 0
    oversize_searchable = 0
    max_text_length = 0
    max_searchable_length = 0

    def searchable_len(candidate: dict[str, Any]) -> int:
        return len(build_searchable_text(candidate))

    for record in merged_records:
        split_records = split_legal_chunk(
            record,
            max_chars=max_chars,
            overlap_chars=overlap_chars,
            length_fn=searchable_len,
        )
        if len(split_records) != 1 or split_records[0].get("chunk_id") != record.get("chunk_id"):
            changed_records += 1

        for split_record in split_records:
            split_record["text_length"] = len(str(split_record.get("text") or ""))
            searchable_length = searchable_len(split_record)
            split_record["searchable_text_length"] = searchable_length
            max_text_length = max(max_text_length, int(split_record["text_length"]))
            max_searchable_length = max(max_searchable_length, searchable_length)
            fallback_splits += 1 if split_record.get("fallback_split") else 0
            oversize_searchable += 1 if searchable_length > max_searchable_chars else 0
            output.append(unique_chunk_id(split_record, seen_ids))

    stats = {
        "input_chunks": len(records),
        "merged_input_chunks": len(merged_records),
        "output_chunks": len(output),
        "changed_records": changed_records,
        "fallback_splits": fallback_splits,
        "oversize_searchable_chunks": oversize_searchable,
        "max_text_length": max_text_length,
        "max_searchable_text_length": max_searchable_length,
        "max_chars": max_chars,
        "max_searchable_chars": max_searchable_chars,
        "overlap_chars": overlap_chars,
    }
    return output, stats


def write_chunk_files(output_root: Path, records: list[dict[str, Any]], *, backup: bool) -> int:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        chunks_file = record.get("chunks_file")
        if isinstance(chunks_file, str) and chunks_file.strip():
            grouped[chunks_file].append(record)

    written = 0
    for relative_path, chunks in grouped.items():
        path = output_root / relative_path
        if not path.exists():
            continue
        if backup:
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        path.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
        written += 1
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-off rechunking for existing Law RAG all_chunks.jsonl.")
    parser.add_argument("--input", default="output/vbpl_combined/all_chunks.jsonl", help="Existing all_chunks.jsonl")
    parser.add_argument("--output", help="Output jsonl. Defaults to <input>.rechunked unless --in-place is set.")
    parser.add_argument("--output-root", help="Root used to update per-document chunks_file paths. Defaults to input parent.")
    parser.add_argument("--in-place", action="store_true", help="Replace --input after creating a .bak backup.")
    parser.add_argument("--no-backup", action="store_true", help="Do not create .bak files.")
    parser.add_argument("--no-chunk-files", action="store_true", help="Do not update per-document .chunks.json files.")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHUNK_CHARS, help="Max chunk/searchable chars target.")
    parser.add_argument("--max-searchable-chars", type=int, default=DEFAULT_MAX_SEARCHABLE_CHARS, help="Report threshold for embedding input.")
    parser.add_argument("--overlap-chars", type=int, default=DEFAULT_OVERLAP_CHARS, help="Overlap for fallback size splits.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    output_path = input_path if args.in_place else Path(args.output or f"{input_path}.rechunked")
    output_root = Path(args.output_root) if args.output_root else input_path.parent
    backup = not args.no_backup

    records = load_jsonl(input_path)
    rechunked, stats = rechunk_records(
        records,
        max_chars=args.max_chars,
        max_searchable_chars=args.max_searchable_chars,
        overlap_chars=args.overlap_chars,
    )

    if args.in_place and backup:
        shutil.copy2(input_path, input_path.with_suffix(input_path.suffix + ".bak"))
    write_jsonl(output_path, rechunked)

    chunk_files_written = 0
    if not args.no_chunk_files:
        chunk_files_written = write_chunk_files(output_root, rechunked, backup=backup)

    stats["output_path"] = str(output_path)
    stats["chunk_files_written"] = chunk_files_written
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
