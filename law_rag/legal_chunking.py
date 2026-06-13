from __future__ import annotations

import re
from typing import Any, Callable


DEFAULT_MAX_CHUNK_CHARS = 3_500
DEFAULT_OVERLAP_CHARS = 350

CLAUSE_RE = re.compile(r"^\s*(\d+[a-z]?)\s*[.)]\s+", re.IGNORECASE)
POINT_RE = re.compile(r"^\s*([a-z\u0111])\s*[.)]\s+", re.IGNORECASE)
ARTICLE_RE = re.compile(r"^\s*\u0110i\u1ec1u\s+(\d+[a-z]?)\s*[.:]?", re.IGNORECASE)
PART_SUFFIX_RE = re.compile(r":part:\d+$")


def chunk_blocks_by_articles(
    blocks: list[dict[str, Any]],
    metadata: dict[str, Any],
    *,
    max_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[dict[str, Any]]:
    blocks = _preprocess_blocks(blocks)
    chunks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    context: dict[str, str | None] = {"part": None, "chapter": None, "section": None}
    heading_classes = {
        "prov-part": "part",
        "prov-chapter": "chapter",
        "prov-section": "section",
    }

    for block in blocks:
        block_class = str(block.get("class") or "")
        text = str(block.get("text") or "")
        for class_name, key in heading_classes.items():
            if class_name in block_class:
                context[key] = text

        if is_article_heading(text):
            if current:
                chunks.extend(split_legal_chunk(_finalize_article_chunk(current), max_chars=max_chars, overlap_chars=overlap_chars))
            article_number = extract_article_number(text)
            current = {
                "chunk_id": f"{metadata['vbpl_id']}:article:{article_number or len(chunks) + 1}",
                "vbpl_id": metadata["vbpl_id"],
                "doc_number": metadata.get("doc_number"),
                "document_title": metadata.get("title"),
                "article_number": article_number,
                "article_title": text,
                "part": context["part"],
                "chapter": context["chapter"],
                "section": context["section"],
                "texts": [text],
            }
            continue

        if current:
            current["texts"].append(text)

    if current:
        chunks.extend(split_legal_chunk(_finalize_article_chunk(current), max_chars=max_chars, overlap_chars=overlap_chars))

    if chunks:
        return ensure_unique_chunk_ids([chunk for chunk in chunks if chunk.get("text")])

    full_text = "\n".join(str(block.get("text") or "") for block in blocks).strip()
    fallback = {
        "chunk_id": f"{metadata['vbpl_id']}:full",
        "vbpl_id": metadata["vbpl_id"],
        "doc_number": metadata.get("doc_number"),
        "document_title": metadata.get("title"),
        "article_number": None,
        "article_title": None,
        "text": full_text,
        "text_length": len(full_text),
    }
    return split_legal_chunk(fallback, max_chars=max_chars, overlap_chars=overlap_chars) if full_text else []


def build_chunk_quality_report(chunks: list[dict[str, Any]], *, max_chars: int = DEFAULT_MAX_CHUNK_CHARS) -> dict[str, Any]:
    ids = [chunk.get("chunk_id") for chunk in chunks]
    lengths = [int(chunk.get("text_length") or len(str(chunk.get("text") or ""))) for chunk in chunks]
    return {
        "chunk_count": len(chunks),
        "duplicate_chunk_ids": len(ids) - len(set(ids)),
        "empty_chunks": sum(1 for chunk in chunks if not str(chunk.get("text") or "").strip()),
        "short_chunks_lt_50_chars": sum(1 for length in lengths if length < 50),
        "long_chunks_gt_max_chars": sum(1 for length in lengths if length > max_chars),
        "max_chunk_chars": max(lengths) if lengths else 0,
    }


def is_article_heading(text: str) -> bool:
    return bool(ARTICLE_RE.match(text))


def extract_article_number(text: str) -> str | None:
    match = ARTICLE_RE.match(text)
    return match.group(1).lower() if match else None


def ensure_unique_chunk_ids(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, int] = {}
    for chunk in chunks:
        chunk_id = str(chunk["chunk_id"])
        count = seen.get(chunk_id, 0)
        if count:
            chunk["chunk_id"] = f"{chunk_id}:dup:{count + 1}"
        seen[chunk_id] = count + 1
    return chunks


def split_legal_chunk(
    chunk: dict[str, Any],
    *,
    max_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    length_fn: Callable[[dict[str, Any]], int] | None = None,
) -> list[dict[str, Any]]:
    """Split a legal chunk by article structure, falling back to overlapped size chunks."""
    text = normalize_text_block(str(chunk.get("text") or ""))
    if not text:
        return []

    normalized = dict(chunk)
    normalized["text"] = text
    normalized["text_length"] = len(text)
    if _fits(normalized, max_chars, length_fn):
        return [normalized]

    semantic_parts = _split_by_clause(text)
    if len(semantic_parts) > 1:
        chunks = _chunks_from_semantic_parts(
            chunk,
            semantic_parts,
            level="clause",
            max_chars=max_chars,
            overlap_chars=overlap_chars,
            length_fn=length_fn,
        )
        if chunks:
            return chunks

    fallback_texts = split_text_with_overlap(text, max_chars=max_chars, overlap_chars=overlap_chars)
    return _fallback_chunks(
        chunk,
        fallback_texts,
        max_chars=max_chars,
        overlap_chars=overlap_chars,
        length_fn=length_fn,
    )


def normalize_text_block(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _preprocess_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    last_text = ""
    for block in blocks:
        text = re.sub(r"\s+", " ", str(block.get("text") or "")).strip()
        if not text or text == last_text:
            continue
        cleaned.append(
            {
                "id": block.get("id"),
                "class": re.sub(r"\s+", " ", str(block.get("class") or "")).strip(),
                "text": text,
            }
        )
        last_text = text
    return cleaned


def _finalize_article_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    texts = chunk.pop("texts")
    text = normalize_text_block("\n".join(str(line) for line in texts))
    chunk["text"] = text
    chunk["text_length"] = len(text)
    return chunk


def split_text_with_overlap(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in text.splitlines() if paragraph.strip()]
    pieces: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(_split_long_paragraph(paragraph, max_chars=max_chars, overlap_chars=overlap_chars))
            continue

        candidate = f"{current}\n{paragraph}".strip() if current else paragraph
        if current and len(candidate) > max_chars:
            pieces.append(current)
            current = _overlap_prefix(current, overlap_chars)
            current = f"{current}\n{paragraph}".strip() if current else paragraph
            if len(current) > max_chars:
                pieces.extend(_split_long_paragraph(current, max_chars=max_chars, overlap_chars=overlap_chars))
                current = ""
        else:
            current = candidate

    if current:
        pieces.append(current)
    return pieces or ([text[:max_chars].strip()] if text else [])


def _split_by_clause(text: str) -> list[dict[str, Any]]:
    lines = [line for line in text.splitlines() if line.strip()]
    heading = lines[0] if lines and ARTICLE_RE.match(lines[0]) else None
    body = lines[1:] if heading else lines
    parts: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line in body:
        match = CLAUSE_RE.match(line)
        if match:
            current = {"number": match.group(1), "lines": []}
            if heading:
                current["lines"].append(heading)
            current["lines"].append(line)
            parts.append(current)
            continue
        if current is None:
            current = {"number": None, "lines": []}
            if heading:
                current["lines"].append(heading)
            parts.append(current)
        current["lines"].append(line)

    for part in parts:
        part["text"] = "\n".join(part.pop("lines")).strip()
    return [part for part in parts if part.get("text")]


def _split_by_point(text: str) -> list[dict[str, Any]]:
    lines = [line for line in text.splitlines() if line.strip()]
    prefix: list[str] = []
    parts: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line in lines:
        match = POINT_RE.match(line)
        if match:
            current = {"number": match.group(1), "lines": [*prefix, line]}
            parts.append(current)
            continue
        if current is None:
            prefix.append(line)
        else:
            current["lines"].append(line)

    for part in parts:
        part["text"] = "\n".join(part.pop("lines")).strip()
    return [part for part in parts if part.get("text")]


def _chunks_from_semantic_parts(
    source: dict[str, Any],
    parts: list[dict[str, Any]],
    *,
    level: str,
    max_chars: int,
    overlap_chars: int,
    length_fn: Callable[[dict[str, Any]], int] | None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    parent_id = str(source.get("parent_chunk_id") or source.get("chunk_id"))
    seen_suffixes: dict[str, int] = {}

    for index, part in enumerate(parts, start=1):
        suffix = str(part.get("number")) if part.get("number") is not None else str(index)
        seen_suffixes[suffix] = seen_suffixes.get(suffix, 0) + 1
        id_suffix = suffix if seen_suffixes[suffix] == 1 else f"{suffix}:repeat:{seen_suffixes[suffix]}"
        candidate = _make_child_chunk(
            source,
            part["text"],
            child_id=_semantic_child_id(source, level, id_suffix),
            parent_id=parent_id,
            part_index=index,
            part_count=len(parts),
        )
        if level == "clause" and part.get("number") is not None:
            candidate["clause_number"] = part["number"]
        if level == "point" and part.get("number") is not None:
            candidate["point_number"] = part["number"]

        if _fits(candidate, max_chars, length_fn):
            results.append(candidate)
            continue

        if level == "clause":
            point_parts = _split_by_point(part["text"])
            if len(point_parts) > 1:
                point_chunks = _chunks_from_semantic_parts(
                    candidate,
                    point_parts,
                    level="point",
                    max_chars=max_chars,
                    overlap_chars=overlap_chars,
                    length_fn=length_fn,
                )
                if point_chunks:
                    results.extend(point_chunks)
                    continue

        fallback_texts = split_text_with_overlap(part["text"], max_chars=max_chars, overlap_chars=overlap_chars)
        results.extend(
            _fallback_chunks(
                candidate,
                fallback_texts,
                max_chars=max_chars,
                overlap_chars=overlap_chars,
                length_fn=length_fn,
            )
        )

    return results


def _fallback_chunks(
    source: dict[str, Any],
    texts: list[str],
    *,
    max_chars: int,
    overlap_chars: int,
    length_fn: Callable[[dict[str, Any]], int] | None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    parent_id = str(source.get("parent_chunk_id") or source.get("chunk_id"))
    total = len(texts)
    for index, text in enumerate(texts, start=1):
        child = _make_child_chunk(
            source,
            text,
            child_id=f"{_base_chunk_id(source)}:part:{index}",
            parent_id=parent_id,
            part_index=index,
            part_count=total,
        )
        child["fallback_split"] = True
        child["overlap_chars"] = overlap_chars if index > 1 else 0
        child["display_title"] = _display_title(source, index)

        if _fits(child, max_chars, length_fn):
            results.append(child)
        elif len(text) > max_chars:
            smaller = split_text_with_overlap(text, max_chars=max_chars, overlap_chars=max(0, overlap_chars // 2))
            if len(smaller) == 1 and len(smaller[0]) >= len(text):
                results.append(child)
            else:
                results.extend(
                    _fallback_chunks(
                        child,
                        smaller,
                        max_chars=max_chars,
                        overlap_chars=max(0, overlap_chars // 2),
                        length_fn=length_fn,
                    )
                )
        else:
            results.append(child)
    return results


def _make_child_chunk(
    source: dict[str, Any],
    text: str,
    *,
    child_id: str,
    parent_id: str,
    part_index: int,
    part_count: int,
) -> dict[str, Any]:
    child = dict(source)
    child["chunk_id"] = child_id
    child["parent_chunk_id"] = parent_id
    child["part_index"] = part_index
    child["part_count"] = part_count
    child["subchunk_number"] = part_index
    child["subchunk_count"] = part_count
    child["text"] = normalize_text_block(text)
    child["text_length"] = len(child["text"])
    return child


def _semantic_child_id(source: dict[str, Any], level: str, suffix: str) -> str:
    return f"{_base_chunk_id(source)}:{level}:{suffix}"


def _base_chunk_id(source: dict[str, Any]) -> str:
    chunk_id = str(source.get("parent_chunk_id") or source.get("chunk_id") or "chunk")
    return PART_SUFFIX_RE.sub("", chunk_id)


def _display_title(source: dict[str, Any], index: int) -> str:
    article_number = source.get("article_number")
    if article_number:
        return f"\u0110i\u1ec1u {article_number} - ph\u1ea7n {index}"
    article_title = source.get("article_title")
    if article_title:
        return f"{article_title} - ph\u1ea7n {index}"
    return f"{source.get('chunk_id', 'chunk')} - ph\u1ea7n {index}"


def _fits(chunk: dict[str, Any], max_chars: int, length_fn: Callable[[dict[str, Any]], int] | None) -> bool:
    if len(str(chunk.get("text") or "")) > max_chars:
        return False
    if length_fn is None:
        return True
    return length_fn(chunk) <= max_chars


def _split_long_paragraph(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    sentences = re.split(r"(?<=[.;:!?])\s+", text)
    parts: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if current and len(candidate) > max_chars:
            parts.append(current)
            prefix = _overlap_prefix(current, overlap_chars)
            current = f"{prefix} {sentence}".strip() if prefix else sentence
        elif len(sentence) > max_chars:
            if current:
                parts.append(current)
                current = ""
            parts.extend(_sliding_windows(sentence, max_chars=max_chars, overlap_chars=overlap_chars))
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def _sliding_windows(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    step = max(1, max_chars - max(0, overlap_chars))
    parts = []
    for start in range(0, len(text), step):
        part = text[start : start + max_chars].strip()
        if part:
            parts.append(part)
        if start + max_chars >= len(text):
            break
    return parts


def _overlap_prefix(text: str, overlap_chars: int) -> str:
    if overlap_chars <= 0:
        return ""
    tail = text[-overlap_chars:].strip()
    if not tail:
        return ""
    if "\n" in tail:
        return tail.split("\n", 1)[-1].strip()
    return tail
