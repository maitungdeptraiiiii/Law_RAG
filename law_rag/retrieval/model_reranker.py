from __future__ import annotations

import os
import threading
import time
from typing import Any


DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
_RERANKER_LOCK = threading.RLock()
_RERANKER_CACHE: dict[tuple[str, bool, str | None], Any] = {}


def _env_enabled(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def reranker_provider() -> str:
    return os.getenv("RERANKER_PROVIDER", "none").strip().casefold()


def reranker_model() -> str:
    return os.getenv("RERANKER_MODEL", DEFAULT_RERANKER_MODEL).strip() or DEFAULT_RERANKER_MODEL


def reranker_enabled() -> bool:
    return reranker_provider() in {"bge", "flagembedding", "model"}


def reranker_text_limit() -> int:
    try:
        return max(200, int(os.getenv("RERANKER_TEXT_LIMIT", "1800")))
    except ValueError:
        return 1800


def reranker_use_fp16() -> bool:
    requested = _env_enabled(os.getenv("RERANKER_USE_FP16"), default=True)
    if not requested:
        return False
    if (os.getenv("RERANKER_DEVICE", "auto").strip().casefold()) == "cpu":
        return False
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def reranker_device() -> str:
    configured_device = os.getenv("RERANKER_DEVICE", "auto").strip().casefold()
    if configured_device and configured_device != "auto":
        return configured_device
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "unknown"


def reranker_device_arg() -> str | None:
    configured_device = os.getenv("RERANKER_DEVICE", "auto").strip()
    if not configured_device or configured_device.casefold() == "auto":
        return None
    return configured_device


def _candidate_text(item: dict[str, Any], *, limit: int) -> str:
    parts = [
        item.get("document_title"),
        item.get("doc_number"),
        item.get("article_number"),
        item.get("clause_number"),
        item.get("target_article"),
        item.get("chapter"),
        item.get("preview"),
        item.get("text"),
    ]
    text = "\n".join(str(part).strip() for part in parts if part)
    return text[:limit]


def _get_flag_reranker(model: str, *, use_fp16: bool) -> Any:
    device_arg = reranker_device_arg()
    cache_key = (model, use_fp16, device_arg)
    with _RERANKER_LOCK:
        cached = _RERANKER_CACHE.get(cache_key)
        if cached is not None:
            return cached
        try:
            from FlagEmbedding import FlagReranker
        except ImportError as exc:
            raise RuntimeError(
                "Missing FlagEmbedding. Install local rerank dependencies with: "
                "pip install -r requirements-local.txt"
            ) from exc

        kwargs = {"devices": device_arg} if device_arg else {}
        reranker = FlagReranker(model, use_fp16=use_fp16, **kwargs)
        _RERANKER_CACHE[cache_key] = reranker
        return reranker


def warmup_model_reranker(debug_timings: dict[str, Any] | None = None) -> None:
    if not reranker_enabled():
        return
    started = time.perf_counter()
    model = reranker_model()
    use_fp16 = reranker_use_fp16()
    reranker = _get_flag_reranker(model, use_fp16=use_fp16)
    reranker.compute_score([("warmup", "warmup")])
    if debug_timings is not None:
        debug_timings["modelRerankWarmupMs"] = int((time.perf_counter() - started) * 1000)


def rerank_candidates_with_model(
    candidates: list[dict[str, Any]],
    *,
    queries: list[str],
    top_k: int,
    debug_timings: dict[str, Any] | None = None,
) -> list[dict[str, Any]] | None:
    if not candidates or not reranker_enabled():
        return None

    started = time.perf_counter()
    model = reranker_model()
    use_fp16 = reranker_use_fp16()
    query_text = "\n".join(str(query).strip() for query in queries if str(query).strip())
    text_limit = reranker_text_limit()

    if debug_timings is not None:
        debug_timings["modelRerankProvider"] = reranker_provider()
        debug_timings["modelRerankModel"] = model
        debug_timings["modelRerankCandidates"] = len(candidates)
        debug_timings["modelRerankDevice"] = reranker_device()

    try:
        reranker = _get_flag_reranker(model, use_fp16=use_fp16)
        pairs = [(query_text, _candidate_text(item, limit=text_limit)) for item in candidates]
        raw_scores = reranker.compute_score(pairs)
    except Exception as exc:
        if debug_timings is not None:
            debug_timings["modelRerankError"] = str(exc)
            debug_timings["modelRerankMs"] = int((time.perf_counter() - started) * 1000)
        return None

    if not isinstance(raw_scores, list):
        raw_scores = [raw_scores]
    scores = [float(score) for score in raw_scores]
    min_score = min(scores) if scores else 0.0
    max_score = max(scores) if scores else 0.0
    score_range = max_score - min_score

    reranked: list[dict[str, Any]] = []
    for item, raw_score in zip(candidates, scores):
        normalized_score = 1.0 if score_range == 0 else (raw_score - min_score) / score_range
        existing_features = item.get("rerank_features") if isinstance(item.get("rerank_features"), dict) else {}
        reranked.append(
            {
                **item,
                "rerank_score": round(normalized_score, 6),
                "model_rerank_score": round(raw_score, 6),
                "rerank_provider": "bge",
                "rerank_model": model,
                "rerank_features": {
                    **existing_features,
                    "model_raw": round(raw_score, 6),
                    "model_normalized": round(normalized_score, 6),
                },
            }
        )

    reranked.sort(key=lambda item: float(item.get("model_rerank_score") or 0.0), reverse=True)
    if debug_timings is not None:
        debug_timings["modelRerankMs"] = int((time.perf_counter() - started) * 1000)
    return reranked[:top_k]
