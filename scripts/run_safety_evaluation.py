#!/usr/bin/env python3
"""Run safety agent evaluation and optionally compare against baseline.

Usage:
    PYTHONPATH=backend:. python scripts/run_safety_evaluation.py
    PYTHONPATH=backend:. python scripts/run_safety_evaluation.py --check
    PYTHONPATH=backend:. python scripts/run_safety_evaluation.py --baseline path/to/baseline.json
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run safety agent evaluation")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check against existing baseline and fail if regression",
    )
    parser.add_argument(
        "--baseline",
        type=str,
        default="evaluation/results/safety_agent_baseline_v1.json",
        help="Path to baseline file for comparison",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output path for evaluation results",
    )
    parser.add_argument(
        "--version",
        type=str,
        default="1.0",
        help="Version string for this evaluation",
    )
    args = parser.parse_args()

    # Import after argparse to avoid slow startup for --help
    from app.safety.evaluation import check_baseline, run_evaluation

    if args.check:
        # Check mode: compare against baseline
        print(f"Checking against baseline: {args.baseline}")
        comparison = check_baseline(args.baseline)

        if "error" in comparison:
            print(f"Error: {comparison['error']}")
            return 1

        print(f"Baseline pass rate: {comparison['baseline_pass_rate']:.2%}")
        print(f"Current pass rate:  {comparison['current_pass_rate']:.2%}")

        if comparison["regressions"]:
            print(f"\nRegressions detected in cases: {comparison['regressions']}")
            return 1

        if comparison["improved"]:
            print("\nNo regressions detected.")
            return 0
        else:
            print("\nWARNING: Performance degraded but no specific regressions.")
            return 1

    # Full evaluation mode
    print("Running safety agent evaluation...")
    print("=" * 60)

    report = run_evaluation(version=args.version)

    # Print summary
    print(f"\nEvaluation Results ({report.version})")
    print("=" * 60)
    print(f"Total cases:  {report.total_cases}")
    print(f"Passed:       {report.passed_cases}")
    print(f"Pass rate:    {report.metrics['pass_rate']:.2%}")
    print()
    print("Category Breakdown:")
    for category in ["retrieval", "structured", "synthesis"]:
        rate = report.metrics.get(f"{category}_pass_rate", 0)
        print(f"  {category:12s}: {rate:.2%}")
    print()
    print("Aggregate Metrics:")
    print(f"  Citation Precision: {report.metrics['avg_citation_precision']:.2%}")
    print(f"  Citation Recall:    {report.metrics['avg_citation_recall']:.2%}")
    print(f"  Keyword Recall:     {report.metrics['avg_keyword_recall']:.2%}")
    print(f"  Tool Accuracy:      {report.metrics['tool_accuracy']:.2%}")
    print(f"  Avg Latency:        {report.metrics['avg_latency_ms']:.0f} ms")
    print(f"  Avg Tokens:         {report.metrics['avg_tokens']:.0f}")

    # Save results
    output_path = args.output
    if output_path:
        Path(output_path).write_text(json.dumps(report.to_dict(), indent=2))
        print(f"\nResults saved to: {output_path}")
    else:
        saved_path = report.save()
        print(f"\nResults saved to: {saved_path}")

    # Print failed cases
    failed = [r for r in report.results if not r["passed"]]
    if failed:
        print(f"\nFailed Cases ({len(failed)}):")
        for r in failed:
            print(f"  {r['case_id']}: {r.get('error') or 'metrics below threshold'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
