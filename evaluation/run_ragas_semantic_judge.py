from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from law_rag.core.env_loader import load_project_env


load_project_env()
if os.getenv("OPENAI_BASE_URL") and not os.getenv("OPENAI_API_BASE"):
    os.environ["OPENAI_API_BASE"] = os.environ["OPENAI_BASE_URL"]


DEFAULT_METRICS = [
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "answer_correctness",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def reference_text(case: dict[str, Any]) -> str:
    reference_outputs = case.get("reference_outputs") or {}
    answer_points = reference_outputs.get("answer_points") or []
    if answer_points:
        return "\n".join(str(item).strip() for item in answer_points if str(item).strip())
    required_terms = reference_outputs.get("required_terms") or []
    return "\n".join(str(item).strip() for item in required_terms if str(item).strip())


def build_rows(report: dict[str, Any], dataset: list[dict[str, Any]], *, max_contexts: int, max_context_chars: int) -> list[dict[str, Any]]:
    reference_by_id = {str(item.get("id")): reference_text(item) for item in dataset}
    rows: list[dict[str, Any]] = []

    for item in report.get("results", []):
        contexts: list[str] = []
        for source in (item.get("sources") or [])[:max_contexts]:
            text = str(source.get("text") or source.get("preview") or "").strip()
            if not text:
                continue
            contexts.append(text[:max_context_chars])

        rows.append(
            {
                "question": str(item.get("question") or "").strip(),
                "answer": str(item.get("answer") or "").strip(),
                "contexts": contexts,
                "ground_truth": reference_by_id.get(str(item.get("case_id")), ""),
                "case_id": item.get("case_id"),
            }
        )
    return rows


def selected_metrics(names: list[str]) -> list[Any]:
    try:
        from ragas.metrics import answer_correctness, answer_relevancy, context_precision, context_recall, faithfulness
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing dependency: ragas. Install semantic judge dependencies with:\n"
            "  pip install ragas datasets\n"
        ) from exc

    registry = {
        "faithfulness": faithfulness,
        "answer_relevancy": answer_relevancy,
        "context_precision": context_precision,
        "context_recall": context_recall,
        "answer_correctness": answer_correctness,
    }
    unknown = [name for name in names if name not in registry]
    if unknown:
        raise SystemExit(f"Unknown RAGAS metrics: {', '.join(unknown)}")
    return [registry[name] for name in names]


def result_summary(rows: list[dict[str, Any]]) -> dict[str, float]:
    summary: dict[str, float] = {}
    ignored = {"question", "answer", "contexts", "ground_truth", "case_id"}
    keys = sorted({key for row in rows for key in row if key not in ignored})
    for key in keys:
        values = [row.get(key) for row in rows if isinstance(row.get(key), int | float)]
        if values:
            summary[key] = round(statistics.mean(values), 4)
    return summary


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if hasattr(value, "item"):
        try:
            return json_safe(value.item())
        except Exception:
            pass
    if hasattr(value, "tolist"):
        try:
            return json_safe(value.tolist())
        except Exception:
            pass
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [json_safe(item) for item in value]
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run RAGAS semantic judge on an existing Law-RAG eval report.")
    parser.add_argument("--report", required=True, help="Path to output/eval/runs/*.json from evaluate_law_rag.py")
    parser.add_argument("--dataset", default="evaluation/law_rag_eval_dataset.json", help="Path to eval dataset with answer_points")
    parser.add_argument("--output-json", help="Path to write RAGAS JSON result")
    parser.add_argument("--output-csv", help="Path to write per-case RAGAS CSV result")
    parser.add_argument("--metrics", nargs="+", default=DEFAULT_METRICS, help=f"RAGAS metrics. Defaults: {' '.join(DEFAULT_METRICS)}")
    parser.add_argument("--max-contexts", type=int, default=5, help="Use at most this many retrieved contexts per case")
    parser.add_argument("--max-context-chars", type=int, default=3500, help="Trim each context to this many characters")
    args = parser.parse_args()

    report_path = Path(args.report)
    dataset_path = Path(args.dataset)
    output_json = Path(args.output_json) if args.output_json else report_path.with_suffix(".ragas.json")
    output_csv = Path(args.output_csv) if args.output_csv else report_path.with_suffix(".ragas.csv")

    try:
        from datasets import Dataset
        from ragas import evaluate
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing dependency for RAGAS semantic judge. Install with:\n"
            "  pip install ragas datasets\n"
        ) from exc

    rows = build_rows(
        load_json(report_path),
        load_json(dataset_path),
        max_contexts=args.max_contexts,
        max_context_chars=args.max_context_chars,
    )
    if not rows:
        raise SystemExit(f"No eval results found in report: {report_path}")

    dataset = Dataset.from_list(
        [
            {
                "question": row["question"],
                "answer": row["answer"],
                "contexts": row["contexts"],
                "ground_truth": row["ground_truth"],
            }
            for row in rows
        ]
    )

    result = evaluate(dataset, metrics=selected_metrics(args.metrics))
    frame = result.to_pandas()
    frame.insert(0, "case_id", [row["case_id"] for row in rows])

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_csv, index=False, encoding="utf-8-sig")

    records = json_safe(frame.to_dict(orient="records"))
    payload = {
        "report": str(report_path),
        "dataset": str(dataset_path),
        "case_count": len(records),
        "metrics": args.metrics,
        "summary": result_summary(records),
        "results": records,
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"case_count": len(records), "summary": payload["summary"], "output_json": str(output_json), "output_csv": str(output_csv)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
