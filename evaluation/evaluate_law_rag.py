from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
import unicodedata
from dataclasses import dataclass
from math import log2
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from law_rag.app.ask_law import DEFAULT_CHAT_MODEL, DEFAULT_MEMORY_MODEL, answer_question
from law_rag.core.env_loader import load_project_env
from law_rag.core.runtime_config import default_vector_dir
from law_rag.retrieval.build_vector_index import DEFAULT_EMBEDDING_MODEL
from law_rag.retrieval.hybrid_retrieve import DEFAULT_QUERY_REWRITE_MODEL


load_project_env()

DEFAULT_DATASET_PATH = ROOT_DIR / "evaluation" / "law_rag_eval_dataset.json"
DEFAULT_RESULTS_DIR = ROOT_DIR / "output" / "eval" / "runs"
CORPUS_NAME = os.getenv("CORPUS_NAME", "vbpl_business_guidance_mvp")
CORPUS_DIR = ROOT_DIR / "output" / CORPUS_NAME
CHUNKS_PATH = CORPUS_DIR / "all_chunks.jsonl"
BM25_INDEX_PATH = CORPUS_DIR / "retrieval" / "bm25_index.json"
_configured_vector_dir = Path(default_vector_dir())
VECTOR_DIR = _configured_vector_dir if _configured_vector_dir.is_absolute() else ROOT_DIR / _configured_vector_dir
SESSIONS_DIR = ROOT_DIR / "output" / "eval" / "sessions"


SAMPLE_DATASET: list[dict[str, Any]] = [
    {
        "id": "criminal_injury_001",
        "category": "hinh_su",
        "inputs": {
            "question": "Toi gay thuong tich 18% cho nguoi khac thi co the bi xu ly the nao?"
        },
        "reference_outputs": {
            "answer_points": [
                "Can xem xet toi co y gay thuong tich hoac gay ton hai cho suc khoe nguoi khac.",
                "Can doi chieu Dieu 134 Bo luat Hinh su.",
                "Can xem them tinh tiet nhu hung khi, co to chuc, tai pham hoac tinh chat hanh vi.",
            ],
            "expected_sources": [
                {
                    "document_title_contains": "hinh su",
                    "article_number": "134",
                }
            ],
            "notes": "TODO: Bo sung dap an chuan bang tieng Viet co dau va can cu chinh xac.",
        },
    },
    {
        "id": "labor_termination_001",
        "category": "lao_dong",
        "inputs": {
            "question": "Nguoi lao dong muon nghi viec thi phai bao truoc bao lau?"
        },
        "reference_outputs": {
            "answer_points": [
                "Can xac dinh loai hop dong lao dong.",
                "Thoi han bao truoc khac nhau theo hop dong khong xac dinh thoi han, xac dinh thoi han hoac cong viec dac thu.",
            ],
            "expected_sources": [
                {
                    "document_title_contains": "lao dong",
                    "article_number": "35",
                }
            ],
            "notes": "TODO: Bo sung cac moc thoi han bao truoc mong doi.",
        },
    },
    {
        "id": "civil_inheritance_001",
        "category": "dan_su",
        "inputs": {
            "question": "Con nuoi co duoc huong thua ke nhu con de khong?"
        },
        "reference_outputs": {
            "answer_points": [
                "Con nuoi va cha me nuoi co quyen thua ke cua nhau neu quan he nuoi con nuoi hop phap.",
                "Can doi chieu quy dinh ve nguoi thua ke theo phap luat trong Bo luat Dan su.",
            ],
            "expected_sources": [
                {
                    "document_title_contains": "dan su",
                    "article_number": "651",
                }
            ],
            "notes": "TODO: Bo sung can cu lien quan den quan he con nuoi neu can.",
        },
    },
]


@dataclass
class EvalConfig:
    retrieval_mode: str
    vector_backend: str
    top_k: int
    query_rewrite: bool
    chat_model: str
    memory_model: str


def ensure_sample_dataset(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(SAMPLE_DATASET, ensure_ascii=False, indent=2), encoding="utf-8")


def load_dataset(path: Path) -> list[dict[str, Any]]:
    ensure_sample_dataset(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Dataset phai la JSON array.")
    return payload


def normalize_text(value: Any) -> str:
    text = str(value or "").casefold()
    text = unicodedata.normalize("NFD", text)
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    text = text.replace("đ", "d")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def tokenize(value: Any) -> list[str]:
    return [token for token in normalize_text(value).split() if len(token) >= 2]


def token_set(value: Any) -> set[str]:
    return set(tokenize(value))


def source_text(source: dict[str, Any]) -> str:
    return str(source.get("text") or source.get("preview") or source.get("chunkText") or "")


def source_eval_text(source: dict[str, Any]) -> str:
    metadata = " ".join(
        str(source.get(key) or "")
        for key in (
            "source_file",
            "document_title",
            "documentTitle",
            "documentId",
            "article_number",
            "clause_number",
        )
    )
    article = f" Dieu {source.get('article_number')}" if source.get("article_number") else ""
    clause = f" Khoan {source.get('clause_number')}" if source.get("clause_number") else ""
    return f"{metadata}{article}{clause} {source_text(source)}"


def source_matches_expected(source: dict[str, Any], expected: dict[str, Any]) -> bool:
    source_identity = normalize_text(
        " ".join(
            str(source.get(key) or "")
            for key in ("source_file", "document_title", "documentTitle", "documentId")
        )
    )
    for expected_key in ("source_file_contains", "document_title_contains"):
        expected_part = normalize_text(expected.get(expected_key))
        if expected_part and expected_part not in source_identity:
            return False

    expected_article = normalize_text(expected.get("article_number"))
    actual_article = normalize_text(source.get("article_number"))
    if expected_article and expected_article != actual_article:
        return False

    expected_clause = normalize_text(expected.get("clause_number"))
    actual_clause = normalize_text(source.get("clause_number"))
    if expected_clause and expected_clause != actual_clause:
        return False

    return True


def source_relevance_grade_for_expected(source: dict[str, Any], expected: dict[str, Any]) -> int:
    expected_identity_parts = [
        normalize_text(expected.get("source_file_contains")),
        normalize_text(expected.get("document_title_contains")),
    ]
    source_identity = normalize_text(
        " ".join(
            str(source.get(key) or "")
            for key in ("source_file", "document_title", "documentTitle", "documentId")
        )
    )
    document_matches = not any(expected_identity_parts) or any(
        expected_part and expected_part in source_identity for expected_part in expected_identity_parts
    )
    expected_article = normalize_text(expected.get("article_number"))
    actual_article = normalize_text(source.get("article_number"))
    expected_clause = normalize_text(expected.get("clause_number"))
    actual_clause = normalize_text(source.get("clause_number"))

    if source_matches_expected(source, expected):
        return 3
    if document_matches and expected_article and expected_article == actual_article:
        return 2
    if document_matches and (not expected_clause or expected_clause == actual_clause):
        return 1
    return 0


def source_relevance_grade(source: dict[str, Any], expected_sources: list[dict[str, Any]]) -> int:
    best_grade = 0
    for expected in expected_sources:
        best_grade = max(best_grade, source_relevance_grade_for_expected(source, expected))

    return best_grade


def precision_at_k(retrieved: list[dict[str, Any]], expected_sources: list[dict[str, Any]], k: int) -> float | None:
    if not expected_sources:
        return None
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    relevant_count = sum(
        1 for source in top_k if any(source_matches_expected(source, expected) for expected in expected_sources)
    )
    return round(relevant_count / len(top_k), 3)


def recall_at_k(retrieved: list[dict[str, Any]], expected_sources: list[dict[str, Any]], k: int) -> float | None:
    if not expected_sources:
        return None
    matched_count = 0
    for expected in expected_sources:
        if any(source_matches_expected(source, expected) for source in retrieved[:k]):
            matched_count += 1
    return round(matched_count / len(expected_sources), 3)


def reciprocal_rank(retrieved: list[dict[str, Any]], expected_sources: list[dict[str, Any]]) -> float | None:
    if not expected_sources:
        return None
    for rank, source in enumerate(retrieved, start=1):
        if any(source_matches_expected(source, expected) for expected in expected_sources):
            return round(1 / rank, 3)
    return 0.0


def ndcg_at_k(retrieved: list[dict[str, Any]], expected_sources: list[dict[str, Any]], k: int) -> float | None:
    if not expected_sources:
        return None
    matched_expected_indexes: set[int] = set()
    gains: list[int] = []
    for source in retrieved[:k]:
        best_index = None
        best_grade = 0
        for expected_index, expected in enumerate(expected_sources):
            if expected_index in matched_expected_indexes:
                continue
            grade = source_relevance_grade_for_expected(source, expected)
            if grade > best_grade:
                best_index = expected_index
                best_grade = grade
        if best_index is not None and best_grade > 0:
            matched_expected_indexes.add(best_index)
        gains.append(best_grade)

    dcg = sum((2**gain - 1) / log2(index + 2) for index, gain in enumerate(gains))
    ideal_gains = [3] * min(len(expected_sources), k)
    ideal_dcg = sum((2**gain - 1) / log2(index + 2) for index, gain in enumerate(ideal_gains))
    if ideal_dcg == 0:
        return 0.0
    return round(min(dcg / ideal_dcg, 1.0), 3)


def token_iou(left: Any, right: Any) -> float:
    left_tokens = token_set(left)
    right_tokens = token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return round(len(left_tokens & right_tokens) / len(left_tokens | right_tokens), 3)


def best_reference_token_iou(retrieved: list[dict[str, Any]], reference_texts: list[str]) -> float | None:
    if not reference_texts:
        return None
    best = 0.0
    for source in retrieved:
        text = source_text(source)
        for reference in reference_texts:
            best = max(best, token_iou(text, reference))
    return round(best, 3)


def duplicate_rate(retrieved: list[dict[str, Any]]) -> float:
    if len(retrieved) <= 1:
        return 0.0
    identities = [
        normalize_text(
            " ".join(
                str(source.get(key) or "")
                for key in ("source_file", "document_title", "documentTitle", "article_number", "clause_number")
            )
        )
        for source in retrieved
    ]
    duplicate_count = len(identities) - len(set(identities))
    return round(duplicate_count / len(identities), 3)


def score_expected_sources(retrieved: list[dict[str, Any]], expected_sources: list[dict[str, Any]]) -> dict[str, Any]:
    if not expected_sources:
        return {
            "top_1_correct": None,
            "top_3_contains_expected": None,
            "top_5_contains_expected": None,
            "precision_at_3": None,
            "precision_at_5": None,
            "recall_at_3": None,
            "recall_at_5": None,
            "mrr": None,
            "ndcg_at_5": None,
            "matched_expected_sources": 0,
            "expected_source_count": 0,
            "citation_accuracy": None,
        }

    matched_count = 0
    for expected in expected_sources:
        if any(source_matches_expected(source, expected) for source in retrieved):
            matched_count += 1

    top_1_correct = any(source_matches_expected(retrieved[0], expected) for expected in expected_sources) if retrieved else False
    top_3_contains = any(
        source_matches_expected(source, expected)
        for source in retrieved[:3]
        for expected in expected_sources
    )
    top_5_contains = any(
        source_matches_expected(source, expected)
        for source in retrieved[:5]
        for expected in expected_sources
    )

    if matched_count == len(expected_sources):
        citation_accuracy = 5
    elif matched_count > 0:
        citation_accuracy = 3
    else:
        citation_accuracy = 1

    return {
        "top_1_correct": top_1_correct,
        "top_3_contains_expected": top_3_contains,
        "top_5_contains_expected": top_5_contains,
        "precision_at_3": precision_at_k(retrieved, expected_sources, 3),
        "precision_at_5": precision_at_k(retrieved, expected_sources, 5),
        "recall_at_3": recall_at_k(retrieved, expected_sources, 3),
        "recall_at_5": recall_at_k(retrieved, expected_sources, 5),
        "mrr": reciprocal_rank(retrieved, expected_sources),
        "ndcg_at_5": ndcg_at_k(retrieved, expected_sources, 5),
        "matched_expected_sources": matched_count,
        "expected_source_count": len(expected_sources),
        "citation_accuracy": citation_accuracy,
    }


def score_answer_points(answer: str, answer_points: list[str]) -> dict[str, Any]:
    if not answer_points:
        return {
            "matched_answer_points": 0,
            "answer_point_count": 0,
            "answer_correctness_heuristic": None,
        }

    answer_norm = normalize_text(answer)
    matched = 0
    missing: list[str] = []
    for point in answer_points:
        point_norm = normalize_text(point)
        keywords = [token for token in point_norm.split() if len(token) >= 4]
        keyword_hits = sum(1 for token in keywords if token in answer_norm)
        if keywords and keyword_hits / len(keywords) >= 0.35:
            matched += 1
        else:
            missing.append(point)

    ratio = matched / len(answer_points)
    if ratio >= 0.9:
        score = 5
    elif ratio >= 0.7:
        score = 4
    elif ratio >= 0.45:
        score = 3
    elif ratio > 0:
        score = 2
    else:
        score = 1

    return {
        "matched_answer_points": matched,
        "answer_point_count": len(answer_points),
        "missing_answer_points": missing,
        "answer_correctness_heuristic": score,
    }


def has_any_citation(retrieved: list[dict[str, Any]]) -> bool:
    return any(source.get("article_number") or source.get("clause_number") for source in retrieved)


def score_required_terms(answer: str, required_terms: list[str]) -> dict[str, Any]:
    if not required_terms:
        return {
            "matched_required_terms": 0,
            "required_term_count": 0,
            "missing_required_terms": [],
            "required_term_coverage": None,
        }

    answer_norm = normalize_text(answer)
    missing = [term for term in required_terms if normalize_text(term) not in answer_norm]
    matched = len(required_terms) - len(missing)
    return {
        "matched_required_terms": matched,
        "required_term_count": len(required_terms),
        "missing_required_terms": missing,
        "required_term_coverage": round(matched / len(required_terms), 3),
    }


def score_forbidden_claims(answer: str, forbidden_claims: list[str]) -> dict[str, Any]:
    if not forbidden_claims:
        return {
            "forbidden_claim_hits": [],
            "forbidden_claim_count": 0,
            "no_forbidden_claims": None,
        }

    answer_norm = normalize_text(answer)
    hits = [claim for claim in forbidden_claims if normalize_text(claim) in answer_norm]
    return {
        "forbidden_claim_hits": hits,
        "forbidden_claim_count": len(hits),
        "no_forbidden_claims": len(hits) == 0,
    }


def extract_citation_keys(text: str) -> set[str]:
    normalized = normalize_text(text)
    keys: set[str] = set()
    for match in re.finditer(r"\bdieu\s+(\d+[a-z]?)\b", normalized):
        keys.add(f"article:{match.group(1)}")
    for match in re.finditer(r"\bkhoan\s+(\d+[a-z]?)\b", normalized):
        keys.add(f"clause:{match.group(1)}")
    return keys


def source_supports_clause(source: dict[str, Any], clause_number: str) -> bool:
    expected_clause = normalize_text(clause_number)
    if not expected_clause:
        return False

    actual_clause = normalize_text(source.get("clause_number"))
    if actual_clause and actual_clause == expected_clause:
        return True

    text = source_text(source)
    if not text:
        return False

    escaped_clause = re.escape(expected_clause)
    normalized_text = normalize_text(text)
    if re.search(rf"\bkhoan\s+{escaped_clause}\b", normalized_text):
        return True

    # Current article-level chunks often contain clause text as numbered blocks:
    # "1. ...", "2) ...", or "1 - ...", while clause_number metadata is empty.
    return bool(re.search(rf"(?m)(?:^|\n)\s*{escaped_clause}\s*(?:[\.\)]|\s+-)\s+", text))


def citation_key_supported(key: str, retrieved: list[dict[str, Any]], retrieved_keys: set[str]) -> bool:
    if key in retrieved_keys:
        return True
    kind, _, value = key.partition(":")
    if kind != "clause":
        return False
    return any(source_supports_clause(source, value) for source in retrieved)


def canonical_number(value: str) -> str:
    normalized = value.replace(",", ".").rstrip(".")
    suffix = "%" if normalized.endswith("%") else ""
    numeric = normalized[:-1] if suffix else normalized
    if "." in numeric:
        numeric = numeric.rstrip("0").rstrip(".")
    numeric = numeric.lstrip("0") or "0"
    return f"{numeric}{suffix}"


def extract_numbers(text: str) -> set[str]:
    return {
        canonical_number(match.group(0))
        for match in re.finditer(r"\d+(?:[.,]\d+)?%?", normalize_text(text))
    }


def score_groundedness(answer: str, retrieved: list[dict[str, Any]], required_terms: list[str]) -> dict[str, Any]:
    retrieved_text = " ".join(source_eval_text(source) for source in retrieved)
    retrieved_keys = {
        key
        for source in retrieved
        for key in (
            f"article:{normalize_text(source.get('article_number'))}" if source.get("article_number") else "",
            f"clause:{normalize_text(source.get('clause_number'))}" if source.get("clause_number") else "",
        )
        if key and not key.endswith(":")
    }
    answer_keys = extract_citation_keys(answer)
    unsupported_citations = sorted(
        key for key in answer_keys if not citation_key_supported(key, retrieved, retrieved_keys)
    )

    required_term_scores = score_required_terms(retrieved_text, required_terms)
    answer_numbers = extract_numbers(answer)
    retrieved_numbers = extract_numbers(retrieved_text)
    citation_numbers = {key.split(":", 1)[1] for key in answer_keys}
    unsupported_numbers = sorted(answer_numbers - retrieved_numbers)
    unsupported_numbers = [number for number in unsupported_numbers if number not in citation_numbers]

    if not retrieved:
        groundedness = 1
    elif unsupported_citations:
        groundedness = 2
    elif required_term_scores["required_term_coverage"] == 0:
        groundedness = 2
    elif unsupported_numbers:
        groundedness = 3
    elif answer_keys or required_terms:
        groundedness = 5
    else:
        groundedness = 4 if has_any_citation(retrieved) else 3

    return {
        "groundedness": groundedness,
        "unsupported_citations": unsupported_citations,
        "unsupported_numbers": unsupported_numbers,
        "retrieved_required_term_coverage": required_term_scores["required_term_coverage"],
    }


def heuristic_scores(
    *,
    answer: str,
    retrieved: list[dict[str, Any]],
    reference_outputs: dict[str, Any],
) -> dict[str, Any]:
    expected_sources = reference_outputs.get("expected_sources") or []
    answer_points = reference_outputs.get("answer_points") or []
    required_terms = reference_outputs.get("required_terms") or []
    forbidden_claims = reference_outputs.get("forbidden_claims") or []

    source_scores = score_expected_sources(retrieved, expected_sources)
    point_scores = score_answer_points(answer, answer_points)
    term_scores = score_required_terms(answer, required_terms)
    forbidden_scores = score_forbidden_claims(answer, forbidden_claims)
    groundedness_scores = score_groundedness(answer, retrieved, required_terms)
    token_iou_score = best_reference_token_iou(retrieved, [*answer_points, *required_terms])

    recall_5 = source_scores["recall_at_5"]
    mrr = source_scores["mrr"]
    if recall_5 == 1 and mrr == 1:
        retrieval_relevance = 5
    elif recall_5 and recall_5 >= 0.8:
        retrieval_relevance = 4
    elif source_scores["top_5_contains_expected"]:
        retrieval_relevance = 3
    elif retrieved:
        retrieval_relevance = 2
    else:
        retrieval_relevance = 1

    answer_relevance = 5 if len(answer.strip()) >= 80 else 3 if answer.strip() else 1
    citation_accuracy = source_scores["citation_accuracy"]
    groundedness = groundedness_scores["groundedness"]
    completeness = point_scores["answer_correctness_heuristic"]
    no_overclaiming = 1 if forbidden_scores["forbidden_claim_hits"] else 4

    weighted_parts = [
        (retrieval_relevance, 0.20),
        (citation_accuracy, 0.15),
        (groundedness, 0.20),
        (point_scores["answer_correctness_heuristic"], 0.20),
        (answer_relevance, 0.10),
        (completeness, 0.10),
        (no_overclaiming, 0.05),
    ]
    active_parts = [(score, weight) for score, weight in weighted_parts if score is not None]
    overall = sum(score * weight for score, weight in active_parts) / sum(weight for _, weight in active_parts)

    return {
        **source_scores,
        **point_scores,
        **term_scores,
        **forbidden_scores,
        **groundedness_scores,
        "best_reference_token_iou": token_iou_score,
        "duplicate_rate": duplicate_rate(retrieved),
        "retrieval_relevance": retrieval_relevance,
        "citation_accuracy": citation_accuracy,
        "answer_correctness": point_scores["answer_correctness_heuristic"],
        "answer_relevance": answer_relevance,
        "completeness": completeness,
        "no_overclaiming": no_overclaiming,
        "overall": round(overall, 2),
        "judge": "deterministic",
        "judge_notes": (
            "Cham deterministic: expected_sources cho retrieval/citation, answer_points cho coverage, "
            "required_terms/forbidden_claims neu dataset co khai bao."
        ),
    }


def run_case(case: dict[str, Any], config: EvalConfig) -> dict[str, Any]:
    question = str(case["inputs"]["question"]).strip()
    started = time.perf_counter()
    result = answer_question(
        question,
        chunks_path=CHUNKS_PATH,
        bm25_index_path=BM25_INDEX_PATH,
        vector_dir=VECTOR_DIR,
        query_rewrite_mode="llm" if config.query_rewrite else "none",
        query_rewrite_model=DEFAULT_QUERY_REWRITE_MODEL,
        query_rewrite_count=4,
        retrieval_mode=config.retrieval_mode,
        vector_backend=config.vector_backend,
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        atlas_uri=None,
        atlas_db=None,
        atlas_collection=None,
        atlas_vector_index=None,
        model=config.chat_model,
        memory_model=config.memory_model,
        top_k=config.top_k,
        session_id=f"eval-{case['id']}-{int(time.time())}",
        session_dir=SESSIONS_DIR,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    reference_outputs = case.get("reference_outputs") or {}
    retrieved = result.get("retrieved", [])
    answer = result.get("answer", "")
    timings = result.get("timings") if isinstance(result.get("timings"), dict) else {}

    scores = heuristic_scores(
        answer=answer,
        retrieved=retrieved,
        reference_outputs=reference_outputs,
    )

    return {
        "case_id": case.get("id"),
        "category": case.get("category"),
        "question": question,
        "answer": answer,
        "retrieval_input": result.get("retrieval_input"),
        "legal_intent": result.get("legal_intent"),
        "retrieval_queries": result.get("retrieval_queries"),
        "legal_issue_labels": result.get("legal_issue_labels", []),
        "legal_issue_matches": result.get("legal_issue_matches", []),
        "rewrite_source": result.get("rewrite_source"),
        "legal_issue_confidence": result.get("legal_issue_confidence"),
        "sources": retrieved,
        "scores": scores,
        "metadata": {
            "retrieval_mode": config.retrieval_mode,
            "vector_backend": config.vector_backend,
            "top_k": config.top_k,
            "query_rewrite": config.query_rewrite,
            "chat_model": config.chat_model,
            "memory_model": config.memory_model,
            "embedding_model": DEFAULT_EMBEDDING_MODEL,
            "latency_ms": latency_ms,
            "graph_retrieval_enabled": bool(timings.get("graphRetrievalEnabled")),
            "graph_retrieval_rows": timings.get("graphRetrievalRows", 0),
            "graph_retrieval_pinned": timings.get("graphRetrievalPinned", 0),
            "graph_retrieval_queries": timings.get("graphRetrievalQueries", 0),
            "graph_retrieval_ms": timings.get("graphRetrievalMs", 0),
            "graph_retrieval_error": timings.get("graphRetrievalError"),
            "retrieval_active_queries": timings.get("retrievalActiveQueries"),
            "timings": timings,
        },
        "todo": case.get("reference_outputs", {}).get("notes"),
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    score_keys = [
        "precision_at_3",
        "precision_at_5",
        "recall_at_3",
        "recall_at_5",
        "mrr",
        "ndcg_at_5",
        "best_reference_token_iou",
        "duplicate_rate",
        "retrieval_relevance",
        "citation_accuracy",
        "groundedness",
        "answer_correctness",
        "answer_relevance",
        "completeness",
        "no_overclaiming",
        "overall",
    ]
    summary: dict[str, Any] = {"case_count": len(results), "scores": {}}
    for key in score_keys:
        values = [
            item["scores"].get(key)
            for item in results
            if isinstance(item.get("scores", {}).get(key), int | float)
        ]
        if values:
            summary["scores"][key] = round(statistics.mean(values), 2)

    latencies = [
        item.get("metadata", {}).get("latency_ms")
        for item in results
        if isinstance(item.get("metadata", {}).get("latency_ms"), int | float)
    ]
    if latencies:
        summary["latency_ms_avg"] = round(statistics.mean(latencies), 2)
        summary["latency_ms_max"] = max(latencies)

    top_3_values = [
        item["scores"].get("top_3_contains_expected")
        for item in results
        if item["scores"].get("top_3_contains_expected") is not None
    ]
    if top_3_values:
        summary["top_3_contains_expected_rate"] = round(sum(bool(value) for value in top_3_values) / len(top_3_values), 3)

    metadata_items = [item.get("metadata", {}) for item in results if isinstance(item.get("metadata"), dict)]
    if metadata_items:
        graph_enabled_count = sum(bool(item.get("graph_retrieval_enabled")) for item in metadata_items)
        graph_used_count = sum(
            int(item.get("graph_retrieval_rows") or 0) > 0
            or int(item.get("graph_retrieval_pinned") or 0) > 0
            or int(item.get("graph_retrieval_queries") or 0) > 0
            for item in metadata_items
        )
        graph_error_count = sum(bool(item.get("graph_retrieval_error")) for item in metadata_items)
        summary["graph_debug"] = {
            "enabled_case_count": graph_enabled_count,
            "used_case_count": graph_used_count,
            "error_case_count": graph_error_count,
            "rows_avg": round(
                statistics.mean(float(item.get("graph_retrieval_rows") or 0) for item in metadata_items),
                2,
            ),
            "pinned_avg": round(
                statistics.mean(float(item.get("graph_retrieval_pinned") or 0) for item in metadata_items),
                2,
            ),
            "queries_avg": round(
                statistics.mean(float(item.get("graph_retrieval_queries") or 0) for item in metadata_items),
                2,
            ),
        }

    return summary


def write_results(results: list[dict[str, Any]], summary: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local evaluation for Law RAG.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH), help="Path to eval dataset JSON.")
    parser.add_argument("--output", default=None, help="Path to write eval results JSON.")
    parser.add_argument("--retrieval-mode", choices=["hybrid", "vector", "bm25"], default="hybrid")
    parser.add_argument("--vector-backend", choices=["faiss", "atlas"], default="faiss")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--query-rewrite", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--chat-model", default=DEFAULT_CHAT_MODEL)
    parser.add_argument("--memory-model", default=DEFAULT_MEMORY_MODEL)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_path = Path(args.dataset)
    dataset = load_dataset(dataset_path)
    if args.limit is not None:
        dataset = dataset[: args.limit]

    config = EvalConfig(
        retrieval_mode=args.retrieval_mode,
        vector_backend=args.vector_backend,
        top_k=args.top_k,
        query_rewrite=args.query_rewrite,
        chat_model=args.chat_model,
        memory_model=args.memory_model,
    )

    output_path = Path(args.output) if args.output else DEFAULT_RESULTS_DIR / f"eval-{int(time.time())}.json"
    results: list[dict[str, Any]] = []
    for index, case in enumerate(dataset, start=1):
        print(f"[{index}/{len(dataset)}] Running {case.get('id')}: {case['inputs']['question']}")
        try:
            results.append(run_case(case, config))
        except Exception as exc:
            results.append(
                {
                    "case_id": case.get("id"),
                    "category": case.get("category"),
                    "question": case.get("inputs", {}).get("question"),
                    "error": str(exc),
                    "scores": {"overall": 1, "judge_notes": "Evaluation case failed."},
                    "metadata": {
                        "retrieval_mode": config.retrieval_mode,
                        "vector_backend": config.vector_backend,
                        "top_k": config.top_k,
                        "query_rewrite": config.query_rewrite,
                        "latency_ms": None,
                    },
                    "todo": "TODO: Kiem tra loi case nay, co the do thieu OPENAI_API_KEY, index hoac expected data.",
                }
            )

    summary = summarize(results)
    write_results(results, summary, output_path)

    print()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nWrote results: {output_path}")
    print(f"Dataset used: {dataset_path}")
    if any("TODO:" in str((case.get("reference_outputs") or {}).get("notes") or "") for case in dataset):
        print("TODO: Thay sample dataset bang bo cau hoi chuan cua ban va bo sung expected_sources/answer_points.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
