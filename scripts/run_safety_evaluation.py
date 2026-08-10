#!/usr/bin/env python3
"""Run deterministic safety retrieval evaluation and optional regression checks."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.safety.evaluation import (
    DEFAULT_RETRIEVAL_CONFIGURATION,
    compare_retrieval_baseline,
    evaluate_retrieval_dataset,
    load_retrieval_dataset,
    load_retrieval_report,
    write_retrieval_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evaluation/safety/faa_part91_retrieval_v1.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument(
        "--embedding-backend",
        default="chromadb-onnx-all-MiniLM-L6-v2-cpu",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset = load_retrieval_dataset(args.dataset)
    report = asyncio.run(
        evaluate_retrieval_dataset(
            dataset,
            retrieval_configuration=DEFAULT_RETRIEVAL_CONFIGURATION.model_copy(
                update={"embedding_backend": args.embedding_backend}
            ),
        )
    )
    write_retrieval_report(report, args.output)
    summary = {
        "dataset_id": report.dataset_id,
        "case_count": report.case_count,
        "recall_at_3": report.recall_at_3,
        "recall_at_5": report.recall_at_5,
        "mean_reciprocal_rank": report.mean_reciprocal_rank,
        "mean_latency_ms": report.mean_latency_ms,
        "output": str(args.output),
    }
    if args.baseline is not None:
        comparison = compare_retrieval_baseline(
            report,
            load_retrieval_report(args.baseline),
        )
        summary["baseline_comparison"] = comparison
        print(json.dumps(summary, indent=2))
        return 0 if comparison["passed"] else 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
