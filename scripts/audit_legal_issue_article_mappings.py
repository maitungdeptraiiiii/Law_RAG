from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def normalize_text(value: Any) -> str:
    text = str(value or "").casefold().replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def document_matches_hints(chunk: dict[str, Any], hints: list[str]) -> bool:
    if not hints:
        return True
    haystack = normalize_text(
        " ".join(
            str(chunk.get(key) or "")
            for key in ("document_title", "doc_type", "doc_number", "source_file")
        )
    )
    return any(normalize_text(hint) in haystack for hint in hints if normalize_text(hint))


def compact_match(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": chunk.get("chunk_id"),
        "article_number": str(chunk.get("article_number") or ""),
        "document_title": chunk.get("document_title"),
        "doc_number": chunk.get("doc_number"),
        "doc_type": chunk.get("doc_type"),
        "source_file": chunk.get("source_file"),
    }


def load_article_index(chunks_path: Path) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with chunks_path.open(encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            chunk = json.loads(line)
            article_number = str(chunk.get("article_number") or "").strip()
            if not article_number:
                continue
            index[article_number].append(compact_match(chunk))
    return index


def audit_article(
    *,
    article_number: str,
    relation: str,
    article_index: dict[str, list[dict[str, Any]]],
    document_title_hints: list[str],
    max_examples: int,
) -> dict[str, Any]:
    candidates = article_index.get(str(article_number), [])
    matched = [chunk for chunk in candidates if document_matches_hints(chunk, document_title_hints)]
    return {
        "article_number": str(article_number),
        "relation": relation,
        "found": bool(matched),
        "candidate_count": len(candidates),
        "matched_count": len(matched),
        "examples": [compact_match(chunk) for chunk in matched[:max_examples]],
    }


def audit_rules(
    *,
    rules: list[dict[str, Any]],
    article_index: dict[str, list[dict[str, Any]]],
    max_examples: int,
) -> dict[str, Any]:
    issue_reports: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for rule in rules:
        label = str(rule.get("label") or "")
        hints = as_str_list(rule.get("document_title_hints", []))
        checks: list[dict[str, Any]] = []
        for article_number in as_str_list(rule.get("preferred_articles", [])):
            checks.append(
                audit_article(
                    article_number=article_number,
                    relation="preferred",
                    article_index=article_index,
                    document_title_hints=hints,
                    max_examples=max_examples,
                )
            )
        for article_number in as_str_list(rule.get("distinguish_from_articles", [])):
            checks.append(
                audit_article(
                    article_number=article_number,
                    relation="distinguish_from",
                    article_index=article_index,
                    document_title_hints=hints,
                    max_examples=max_examples,
                )
            )
        issue_missing = [item for item in checks if not item["found"]]
        issue_reports.append(
            {
                "label": label,
                "display_name": rule.get("display_name"),
                "document_title_hints": hints,
                "checks": checks,
                "missing_count": len(issue_missing),
            }
        )
        for item in issue_missing:
            missing.append(
                {
                    "label": label,
                    "display_name": rule.get("display_name"),
                    "relation": item["relation"],
                    "article_number": item["article_number"],
                    "candidate_count_without_hints": item["candidate_count"],
                    "document_title_hints": hints,
                }
            )

    total_checks = sum(len(report["checks"]) for report in issue_reports)
    found_checks = sum(1 for report in issue_reports for item in report["checks"] if item["found"])
    return {
        "summary": {
            "issues": len(issue_reports),
            "total_article_checks": total_checks,
            "found": found_checks,
            "missing": len(missing),
        },
        "missing": missing,
        "issues": issue_reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit legal issue article mappings against corpus chunks.")
    parser.add_argument("--rules", default="law_rag/retrieval/legal_issues_full_all_added.json")
    parser.add_argument("--chunks", default="output/vbpl_merged_reuse_openai/all_chunks.jsonl")
    parser.add_argument("--output", default="")
    parser.add_argument("--max-examples", type=int, default=3)
    args = parser.parse_args()

    rules_path = Path(args.rules)
    chunks_path = Path(args.chunks)
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    if not isinstance(rules, list):
        raise ValueError(f"Rules file must be a JSON array: {rules_path}")
    if not chunks_path.exists():
        raise FileNotFoundError(f"Chunks file not found: {chunks_path}")

    article_index = load_article_index(chunks_path)
    report = audit_rules(rules=rules, article_index=article_index, max_examples=max(0, args.max_examples))
    report["rules_path"] = str(rules_path)
    report["chunks_path"] = str(chunks_path)

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
        print(json.dumps({"summary": report["summary"], "output": str(output_path)}, ensure_ascii=False, indent=2))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
