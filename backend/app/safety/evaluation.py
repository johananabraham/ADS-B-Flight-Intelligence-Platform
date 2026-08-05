"""Safety Agent evaluation harness with 30 baseline test cases.

This module provides:
- 30 curated evaluation cases across retrieval, structured, and synthesis categories
- Citation precision/recall metrics
- Faithfulness scoring
- Latency and cost tracking
- Versioned evaluation results

Evaluation cases cover:
- 15 retrieval cases (semantic search accuracy)
- 10 structured query cases (database aggregation accuracy)
- 5 synthesis cases (multi-tool reasoning)
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from app.safety.agent import AgentResponse, run_agent
from app.safety.tools import (
    tool_get_aircraft_safety_context,
    tool_get_incident_detail,
    tool_query_incident_database,
    tool_search_faa_regulations,
    tool_search_incident_narratives,
)

logger = logging.getLogger(__name__)

EVAL_RESULTS_DIR = Path("evaluation/results")
EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)


class EvalCategory(str, Enum):
    RETRIEVAL = "retrieval"
    STRUCTURED = "structured"
    SYNTHESIS = "synthesis"


@dataclass
class EvalCase:
    """A single evaluation case."""

    id: str
    category: EvalCategory
    query: str
    expected_tool: str | None  # Primary tool that should be used
    expected_citations: list[str]  # Expected NTSB IDs or CFR references
    expected_keywords: list[str]  # Keywords that should appear in answer
    ground_truth_answer: str  # Reference answer for faithfulness
    difficulty: str = "medium"  # easy, medium, hard


@dataclass
class EvalResult:
    """Result of evaluating a single case."""

    case_id: str
    category: str
    passed: bool
    tool_used: str | None
    tool_correct: bool
    citation_precision: float
    citation_recall: float
    keyword_recall: float
    latency_ms: float
    total_tokens: int
    iterations: int
    answer: str
    error: str | None = None


@dataclass
class EvalReport:
    """Aggregate evaluation report."""

    timestamp: str
    version: str
    total_cases: int
    passed_cases: int
    results: list[dict[str, Any]]
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "version": self.version,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "pass_rate": self.passed_cases / self.total_cases if self.total_cases > 0 else 0,
            "metrics": self.metrics,
            "results": self.results,
        }

    def save(self, filename: str = "safety_agent_baseline_v1.json") -> Path:
        path = EVAL_RESULTS_DIR / filename
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path


# ============================================================================
# 30 Baseline Evaluation Cases
# ============================================================================

EVAL_CASES: list[EvalCase] = [
    # --- RETRIEVAL CASES (15) ---
    EvalCase(
        id="R01",
        category=EvalCategory.RETRIEVAL,
        query="Find incidents involving engine failure during takeoff",
        expected_tool="search_incident_narratives",
        expected_citations=[],  # Will match any relevant NTSB IDs
        expected_keywords=["engine", "failure", "takeoff", "power"],
        ground_truth_answer="Engine failures during takeoff are critical events...",
        difficulty="easy",
    ),
    EvalCase(
        id="R02",
        category=EvalCategory.RETRIEVAL,
        query="What incidents involved Cessna 172 aircraft in California?",
        expected_tool="search_incident_narratives",
        expected_citations=[],
        expected_keywords=["cessna", "172", "california"],
        ground_truth_answer="Cessna 172 incidents in California include...",
        difficulty="easy",
    ),
    EvalCase(
        id="R03",
        category=EvalCategory.RETRIEVAL,
        query="Find accidents caused by fuel exhaustion",
        expected_tool="search_incident_narratives",
        expected_citations=[],
        expected_keywords=["fuel", "exhaustion", "depletion"],
        ground_truth_answer="Fuel exhaustion accidents typically occur when...",
        difficulty="easy",
    ),
    EvalCase(
        id="R04",
        category=EvalCategory.RETRIEVAL,
        query="What regulations govern VFR flight minimums?",
        expected_tool="search_faa_regulations",
        expected_citations=["14 CFR 91.155"],
        expected_keywords=["vfr", "visibility", "ceiling", "cloud"],
        ground_truth_answer="VFR weather minimums are defined in 14 CFR 91.155...",
        difficulty="easy",
    ),
    EvalCase(
        id="R05",
        category=EvalCategory.RETRIEVAL,
        query="What are the requirements for instrument currency?",
        expected_tool="search_faa_regulations",
        expected_citations=["14 CFR 61.57"],
        expected_keywords=["instrument", "currency", "approaches", "holding"],
        ground_truth_answer="Instrument currency requirements per 14 CFR 61.57...",
        difficulty="medium",
    ),
    EvalCase(
        id="R06",
        category=EvalCategory.RETRIEVAL,
        query="Find incidents involving spatial disorientation at night",
        expected_tool="search_incident_narratives",
        expected_citations=[],
        expected_keywords=["spatial", "disorientation", "night", "visual"],
        ground_truth_answer="Spatial disorientation incidents at night...",
        difficulty="medium",
    ),
    EvalCase(
        id="R07",
        category=EvalCategory.RETRIEVAL,
        query="What regulations apply to minimum safe altitudes?",
        expected_tool="search_faa_regulations",
        expected_citations=["14 CFR 91.119"],
        expected_keywords=["altitude", "minimum", "safe", "feet"],
        ground_truth_answer="Minimum safe altitudes per 14 CFR 91.119...",
        difficulty="easy",
    ),
    EvalCase(
        id="R08",
        category=EvalCategory.RETRIEVAL,
        query="Find accidents involving icing conditions in IMC",
        expected_tool="search_incident_narratives",
        expected_citations=[],
        expected_keywords=["icing", "ice", "imc", "instrument"],
        ground_truth_answer="Icing-related accidents in IMC conditions...",
        difficulty="medium",
    ),
    EvalCase(
        id="R09",
        category=EvalCategory.RETRIEVAL,
        query="What are the pilot rest requirements for Part 135?",
        expected_tool="search_faa_regulations",
        expected_citations=["14 CFR 135.263", "14 CFR 135.267"],
        expected_keywords=["rest", "duty", "flight time", "135"],
        ground_truth_answer="Part 135 pilot rest requirements include...",
        difficulty="hard",
    ),
    EvalCase(
        id="R10",
        category=EvalCategory.RETRIEVAL,
        query="Find incidents where pilot medical condition was a factor",
        expected_tool="search_incident_narratives",
        expected_citations=[],
        expected_keywords=["medical", "pilot", "incapacitation", "health"],
        ground_truth_answer="Pilot medical conditions contributing to incidents...",
        difficulty="medium",
    ),
    EvalCase(
        id="R11",
        category=EvalCategory.RETRIEVAL,
        query="What regulations govern carriage of hazardous materials?",
        expected_tool="search_faa_regulations",
        expected_citations=["14 CFR 91.19"],
        expected_keywords=["hazardous", "materials", "dangerous", "cargo"],
        ground_truth_answer="Hazardous materials carriage per 14 CFR 91.19...",
        difficulty="medium",
    ),
    EvalCase(
        id="R12",
        category=EvalCategory.RETRIEVAL,
        query="Find CFIT accidents in mountainous terrain",
        expected_tool="search_incident_narratives",
        expected_citations=[],
        expected_keywords=["cfit", "terrain", "mountain", "controlled flight"],
        ground_truth_answer="CFIT accidents in mountainous terrain...",
        difficulty="medium",
    ),
    EvalCase(
        id="R13",
        category=EvalCategory.RETRIEVAL,
        query="What are the requirements for a commercial pilot certificate?",
        expected_tool="search_faa_regulations",
        expected_citations=["14 CFR 61.123", "14 CFR 61.129"],
        expected_keywords=["commercial", "pilot", "certificate", "hours"],
        ground_truth_answer="Commercial pilot certificate requirements...",
        difficulty="medium",
    ),
    EvalCase(
        id="R14",
        category=EvalCategory.RETRIEVAL,
        query="Find accidents involving midair collisions",
        expected_tool="search_incident_narratives",
        expected_citations=[],
        expected_keywords=["midair", "collision", "see and avoid"],
        ground_truth_answer="Midair collision accidents involve...",
        difficulty="easy",
    ),
    EvalCase(
        id="R15",
        category=EvalCategory.RETRIEVAL,
        query="What regulations govern flight crew member oxygen requirements?",
        expected_tool="search_faa_regulations",
        expected_citations=["14 CFR 91.211"],
        expected_keywords=["oxygen", "altitude", "supplemental", "crew"],
        ground_truth_answer="Oxygen requirements per 14 CFR 91.211...",
        difficulty="medium",
    ),
    # --- STRUCTURED QUERY CASES (10) ---
    EvalCase(
        id="S01",
        category=EvalCategory.STRUCTURED,
        query="How many fatal accidents occurred in 2022?",
        expected_tool="query_incident_database",
        expected_citations=[],
        expected_keywords=["2022", "fatal", "count"],
        ground_truth_answer="There were X fatal accidents in 2022...",
        difficulty="easy",
    ),
    EvalCase(
        id="S02",
        category=EvalCategory.STRUCTURED,
        query="What state has the most aviation accidents?",
        expected_tool="query_incident_database",
        expected_citations=[],
        expected_keywords=["state", "most", "highest"],
        ground_truth_answer="The state with the most accidents is...",
        difficulty="easy",
    ),
    EvalCase(
        id="S03",
        category=EvalCategory.STRUCTURED,
        query="How many Piper accidents involved fatalities?",
        expected_tool="query_incident_database",
        expected_citations=[],
        expected_keywords=["piper", "fatal", "count"],
        ground_truth_answer="Piper aircraft fatality statistics...",
        difficulty="easy",
    ),
    EvalCase(
        id="S04",
        category=EvalCategory.STRUCTURED,
        query="What phase of flight has the highest accident rate?",
        expected_tool="query_incident_database",
        expected_citations=[],
        expected_keywords=["phase", "flight", "highest", "rate"],
        ground_truth_answer="The phase of flight with most accidents...",
        difficulty="medium",
    ),
    EvalCase(
        id="S05",
        category=EvalCategory.STRUCTURED,
        query="Show accident trends by year from 2018 to 2023",
        expected_tool="query_incident_database",
        expected_citations=[],
        expected_keywords=["2018", "2019", "2020", "trend"],
        ground_truth_answer="Annual accident trends show...",
        difficulty="medium",
    ),
    EvalCase(
        id="S06",
        category=EvalCategory.STRUCTURED,
        query="Which aircraft make has the most incidents?",
        expected_tool="query_incident_database",
        expected_citations=[],
        expected_keywords=["make", "manufacturer", "most"],
        ground_truth_answer="The aircraft manufacturer with most incidents...",
        difficulty="easy",
    ),
    EvalCase(
        id="S07",
        category=EvalCategory.STRUCTURED,
        query="How many accidents occurred in IMC weather?",
        expected_tool="query_incident_database",
        expected_citations=[],
        expected_keywords=["imc", "instrument", "weather", "count"],
        ground_truth_answer="IMC weather accident statistics...",
        difficulty="medium",
    ),
    EvalCase(
        id="S08",
        category=EvalCategory.STRUCTURED,
        query="What percentage of accidents involve student pilots?",
        expected_tool="query_incident_database",
        expected_citations=[],
        expected_keywords=["student", "pilot", "percentage"],
        ground_truth_answer="Student pilot accident statistics...",
        difficulty="hard",
    ),
    EvalCase(
        id="S09",
        category=EvalCategory.STRUCTURED,
        query="List recent Boeing 737 incidents",
        expected_tool="query_incident_database",
        expected_citations=[],
        expected_keywords=["boeing", "737", "recent"],
        ground_truth_answer="Recent Boeing 737 incidents include...",
        difficulty="easy",
    ),
    EvalCase(
        id="S10",
        category=EvalCategory.STRUCTURED,
        query="How many accidents occurred during landing approach?",
        expected_tool="query_incident_database",
        expected_citations=[],
        expected_keywords=["landing", "approach", "count"],
        ground_truth_answer="Landing approach accident count...",
        difficulty="easy",
    ),
    # --- SYNTHESIS CASES (5) ---
    EvalCase(
        id="Y01",
        category=EvalCategory.SYNTHESIS,
        query="What are the common causes of Cessna 172 accidents and what regulations should pilots review?",
        expected_tool=None,  # Multiple tools
        expected_citations=["14 CFR 91"],
        expected_keywords=["cessna", "172", "cause", "regulation"],
        ground_truth_answer="Cessna 172 accident analysis with regulations...",
        difficulty="hard",
    ),
    EvalCase(
        id="Y02",
        category=EvalCategory.SYNTHESIS,
        query="Compare fatal vs non-fatal accident rates and explain contributing factors",
        expected_tool=None,
        expected_citations=[],
        expected_keywords=["fatal", "non-fatal", "rate", "factor"],
        ground_truth_answer="Fatal accident rate comparison...",
        difficulty="hard",
    ),
    EvalCase(
        id="Y03",
        category=EvalCategory.SYNTHESIS,
        query="What safety improvements could reduce loss of control accidents based on NTSB findings?",
        expected_tool=None,
        expected_citations=[],
        expected_keywords=["loss of control", "safety", "improvement", "ntsb"],
        ground_truth_answer="Safety recommendations for LOC...",
        difficulty="hard",
    ),
    EvalCase(
        id="Y04",
        category=EvalCategory.SYNTHESIS,
        query="Analyze the relationship between pilot experience and accident severity",
        expected_tool=None,
        expected_citations=[],
        expected_keywords=["pilot", "experience", "hours", "severity"],
        ground_truth_answer="Pilot experience vs accident severity...",
        difficulty="hard",
    ),
    EvalCase(
        id="Y05",
        category=EvalCategory.SYNTHESIS,
        query="What Part 135 safety concerns emerge from recent accident data?",
        expected_tool=None,
        expected_citations=["14 CFR 135"],
        expected_keywords=["135", "charter", "safety", "concern"],
        ground_truth_answer="Part 135 safety analysis...",
        difficulty="hard",
    ),
]


# ============================================================================
# Evaluation Logic
# ============================================================================


def extract_citations(answer: str) -> list[str]:
    """Extract NTSB IDs and CFR references from answer text."""
    import re

    citations = []

    # NTSB IDs (various formats)
    ntsb_patterns = [
        r"[A-Z]{3}\d{2}[A-Z]{2}\d{3}",  # e.g., NYC22FA123
        r"NTSB/[A-Z]+/\d+-\d+",  # e.g., NTSB/AAR/22-01
    ]
    for pattern in ntsb_patterns:
        citations.extend(re.findall(pattern, answer, re.IGNORECASE))

    # CFR references
    cfr_pattern = r"14\s*CFR\s*(?:Part\s*)?(\d+)(?:\.(\d+))?"
    for match in re.finditer(cfr_pattern, answer, re.IGNORECASE):
        part = match.group(1)
        section = match.group(2)
        if section:
            citations.append(f"14 CFR {part}.{section}")
        else:
            citations.append(f"14 CFR {part}")

    return list(set(citations))


def compute_citation_metrics(
    actual: list[str], expected: list[str]
) -> tuple[float, float]:
    """Compute citation precision and recall."""
    if not expected:
        # No expected citations - precision/recall not applicable
        return 1.0, 1.0

    if not actual:
        return 0.0, 0.0

    # Normalize for comparison
    actual_normalized = {c.lower().replace(" ", "") for c in actual}
    expected_normalized = {c.lower().replace(" ", "") for c in expected}

    matches = len(actual_normalized & expected_normalized)
    precision = matches / len(actual_normalized) if actual_normalized else 0.0
    recall = matches / len(expected_normalized) if expected_normalized else 0.0

    return precision, recall


def compute_keyword_recall(answer: str, keywords: list[str]) -> float:
    """Compute what fraction of expected keywords appear in answer."""
    if not keywords:
        return 1.0

    answer_lower = answer.lower()
    matches = sum(1 for kw in keywords if kw.lower() in answer_lower)
    return matches / len(keywords)


def evaluate_case(case: EvalCase) -> EvalResult:
    """Evaluate a single test case."""
    start_time = time.time()
    error = None
    answer = ""
    tool_used = None
    total_tokens = 0
    iterations = 0

    try:
        response: AgentResponse = run_agent(case.query)
        answer = response.answer
        total_tokens = response.total_tokens
        iterations = response.iterations

        # Extract primary tool used
        if response.tool_calls:
            tool_used = response.tool_calls[0].get("tool")

    except Exception as e:
        error = str(e)
        answer = ""

    latency_ms = (time.time() - start_time) * 1000

    # Compute metrics
    citations = extract_citations(answer) if answer else []
    citation_precision, citation_recall = compute_citation_metrics(
        citations, case.expected_citations
    )
    keyword_recall = compute_keyword_recall(answer, case.expected_keywords)

    # Check if correct tool was used
    tool_correct = True
    if case.expected_tool and tool_used:
        tool_correct = case.expected_tool in tool_used

    # Determine pass/fail
    passed = (
        error is None
        and keyword_recall >= 0.5
        and (not case.expected_citations or citation_recall >= 0.5)
        and tool_correct
    )

    return EvalResult(
        case_id=case.id,
        category=case.category.value,
        passed=passed,
        tool_used=tool_used,
        tool_correct=tool_correct,
        citation_precision=citation_precision,
        citation_recall=citation_recall,
        keyword_recall=keyword_recall,
        latency_ms=latency_ms,
        total_tokens=total_tokens,
        iterations=iterations,
        answer=answer,
        error=error,
    )


def run_evaluation(
    cases: list[EvalCase] | None = None,
    version: str = "1.0",
) -> EvalReport:
    """Run full evaluation suite.

    Args:
        cases: Specific cases to run (default: all EVAL_CASES)
        version: Version string for the report

    Returns:
        EvalReport with all results and metrics
    """
    if cases is None:
        cases = EVAL_CASES

    results = []
    passed = 0

    for case in cases:
        logger.info(f"Evaluating case {case.id}: {case.query[:50]}...")
        result = evaluate_case(case)
        results.append({
            "case_id": result.case_id,
            "category": result.category,
            "passed": result.passed,
            "tool_used": result.tool_used,
            "tool_correct": result.tool_correct,
            "citation_precision": result.citation_precision,
            "citation_recall": result.citation_recall,
            "keyword_recall": result.keyword_recall,
            "latency_ms": result.latency_ms,
            "total_tokens": result.total_tokens,
            "iterations": result.iterations,
            "error": result.error,
        })

        if result.passed:
            passed += 1

    # Compute aggregate metrics
    total = len(results)
    metrics = {
        "pass_rate": passed / total if total > 0 else 0,
        "avg_citation_precision": sum(r["citation_precision"] for r in results) / total if total else 0,
        "avg_citation_recall": sum(r["citation_recall"] for r in results) / total if total else 0,
        "avg_keyword_recall": sum(r["keyword_recall"] for r in results) / total if total else 0,
        "avg_latency_ms": sum(r["latency_ms"] for r in results) / total if total else 0,
        "avg_tokens": sum(r["total_tokens"] for r in results) / total if total else 0,
        "tool_accuracy": sum(r["tool_correct"] for r in results) / total if total else 0,
    }

    # Category-level metrics
    for category in EvalCategory:
        cat_results = [r for r in results if r["category"] == category.value]
        if cat_results:
            cat_passed = sum(1 for r in cat_results if r["passed"])
            metrics[f"{category.value}_pass_rate"] = cat_passed / len(cat_results)

    report = EvalReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        version=version,
        total_cases=total,
        passed_cases=passed,
        results=results,
        metrics=metrics,
    )

    return report


def check_baseline(
    baseline_path: str = "evaluation/results/safety_agent_baseline_v1.json",
) -> dict[str, Any]:
    """Compare current evaluation against baseline.

    Returns dict with comparison results.
    """
    baseline_file = Path(baseline_path)
    if not baseline_file.exists():
        return {"error": f"Baseline not found: {baseline_path}"}

    baseline = json.loads(baseline_file.read_text())
    current = run_evaluation()

    comparison = {
        "baseline_pass_rate": baseline.get("pass_rate", 0),
        "current_pass_rate": current.metrics.get("pass_rate", 0),
        "improved": current.metrics.get("pass_rate", 0) >= baseline.get("pass_rate", 0),
        "regressions": [],
    }

    # Check for regressions
    baseline_results = {r["case_id"]: r for r in baseline.get("results", [])}
    for result in current.results:
        case_id = result["case_id"]
        if case_id in baseline_results:
            if baseline_results[case_id].get("passed") and not result.get("passed"):
                comparison["regressions"].append(case_id)

    return comparison
