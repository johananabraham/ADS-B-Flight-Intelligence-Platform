"""Deterministic retrieval evaluation over reviewed, versioned safety sources."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.vectorstore import (
    EMBEDDING_BACKEND_ID,
    HNSW_CONSTRUCTION_EF,
    HNSW_SEARCH_EF,
    HNSW_SPACE,
    search_faa_regulations,
)


SearchFunction = Callable[..., Awaitable[dict[str, Any]]]


class SourceArtifactIdentity(BaseModel):
    """Exact authoritative artifact used to review expected documents."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_uri: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    effective_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    parsed_sections: int = Field(gt=0)


class RetrievalCase(BaseModel):
    """One reviewed query with exact relevant corpus document identities."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(pattern=r"^R\d{2}$")
    question: str = Field(min_length=10)
    collection: Literal["faa_regulations"]
    cfr_part: int = Field(gt=0)
    expected_document_ids: tuple[str, ...] = Field(min_length=1)
    expected_citations: tuple[str, ...] = Field(min_length=1)
    review_note: str = Field(min_length=10)


class RetrievalDataset(BaseModel):
    """Reviewed retrieval set bound to one exact corpus artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"]
    dataset_id: str = Field(min_length=1)
    evidence_class: Literal["OFFICIAL_SOURCE_ENGINEERING_REVIEW"]
    reviewed_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    source_artifact: SourceArtifactIdentity
    cases: tuple[RetrievalCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_case_ids(self) -> "RetrievalDataset":
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("retrieval case IDs must be unique")
        return self


class RetrievalCaseResult(BaseModel):
    """Ranked retrieval evidence for one case."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    expected_document_ids: tuple[str, ...]
    retrieved_document_ids: tuple[str, ...]
    recall_at_3: float = Field(ge=0, le=1)
    recall_at_5: float = Field(ge=0, le=1)
    reciprocal_rank: float = Field(ge=0, le=1)
    latency_ms: float = Field(ge=0)


class RetrievalConfiguration(BaseModel):
    """Retrieval settings required to reproduce a baseline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    embedding_backend: str = Field(min_length=1)
    hnsw_space: Literal["cosine"]
    hnsw_construction_ef: int = Field(gt=0)
    hnsw_search_ef: int = Field(gt=0)
    top_k: Literal[5]


DEFAULT_RETRIEVAL_CONFIGURATION = RetrievalConfiguration(
    embedding_backend=EMBEDDING_BACKEND_ID,
    hnsw_space=HNSW_SPACE,
    hnsw_construction_ef=HNSW_CONSTRUCTION_EF,
    hnsw_search_ef=HNSW_SEARCH_EF,
    top_k=5,
)


class RetrievalEvaluationReport(BaseModel):
    """Aggregate deterministic retrieval metrics and itemized rankings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    report_schema_version: Literal["1.0"] = "1.0"
    generated_at: datetime
    dataset_id: str
    evidence_class: str
    source_artifact: SourceArtifactIdentity
    case_count: int = Field(gt=0)
    recall_at_3: float = Field(ge=0, le=1)
    recall_at_5: float = Field(ge=0, le=1)
    mean_reciprocal_rank: float = Field(ge=0, le=1)
    mean_latency_ms: float = Field(ge=0)
    retrieval_configuration: RetrievalConfiguration
    limitations: tuple[str, ...]
    results: tuple[RetrievalCaseResult, ...]

    @model_validator(mode="after")
    def require_itemized_result_count(self) -> "RetrievalEvaluationReport":
        if len(self.results) != self.case_count:
            raise ValueError("case_count must equal the itemized result count")
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return self


def load_retrieval_dataset(path: Path) -> RetrievalDataset:
    """Load and strictly validate a checked-in retrieval dataset."""
    return RetrievalDataset.model_validate_json(path.read_text())


def _recall(expected: set[str], retrieved: tuple[str, ...], k: int) -> float:
    return len(expected & set(retrieved[:k])) / len(expected)


def _reciprocal_rank(expected: set[str], retrieved: tuple[str, ...]) -> float:
    for rank, document_id in enumerate(retrieved, start=1):
        if document_id in expected:
            return 1 / rank
    return 0.0


async def evaluate_retrieval_dataset(
    dataset: RetrievalDataset,
    *,
    search: SearchFunction = search_faa_regulations,
    retrieval_configuration: RetrievalConfiguration = DEFAULT_RETRIEVAL_CONFIGURATION,
) -> RetrievalEvaluationReport:
    """Run exact ranked-document evaluation without invoking an LLM."""
    results: list[RetrievalCaseResult] = []
    for case in dataset.cases:
        started = perf_counter()
        response = await search(
            query_text=case.question,
            n_results=5,
            where={"cfr_part": case.cfr_part},
        )
        latency_ms = (perf_counter() - started) * 1_000
        retrieved = tuple(response.get("ids") or ())
        expected = set(case.expected_document_ids)
        results.append(
            RetrievalCaseResult(
                case_id=case.case_id,
                expected_document_ids=case.expected_document_ids,
                retrieved_document_ids=retrieved,
                recall_at_3=_recall(expected, retrieved, 3),
                recall_at_5=_recall(expected, retrieved, 5),
                reciprocal_rank=_reciprocal_rank(expected, retrieved),
                latency_ms=latency_ms,
            )
        )

    count = len(results)
    return RetrievalEvaluationReport(
        generated_at=datetime.now(timezone.utc),
        dataset_id=dataset.dataset_id,
        evidence_class=dataset.evidence_class,
        source_artifact=dataset.source_artifact,
        case_count=count,
        recall_at_3=sum(result.recall_at_3 for result in results) / count,
        recall_at_5=sum(result.recall_at_5 for result in results) / count,
        mean_reciprocal_rank=(
            sum(result.reciprocal_rank for result in results) / count
        ),
        mean_latency_ms=sum(result.latency_ms for result in results) / count,
        retrieval_configuration=retrieval_configuration,
        limitations=(
            "This set covers official eCFR Part 91 retrieval, not NTSB narratives.",
            "It does not measure structured-query exact match or answer synthesis.",
            "Engineering source review is not an independent domain-expert review.",
            "Latency is machine-specific and is not a production service-level claim.",
        ),
        results=tuple(results),
    )


def compare_retrieval_baseline(
    current: RetrievalEvaluationReport,
    baseline: RetrievalEvaluationReport,
) -> dict[str, Any]:
    """Fail closed on dataset mismatch or Recall@K regression."""
    same_dataset = (
        current.dataset_id == baseline.dataset_id
        and current.source_artifact == baseline.source_artifact
        and current.case_count == baseline.case_count
        and current.retrieval_configuration == baseline.retrieval_configuration
    )
    regressions = []
    if current.recall_at_3 < baseline.recall_at_3:
        regressions.append("recall_at_3")
    if current.recall_at_5 < baseline.recall_at_5:
        regressions.append("recall_at_5")
    return {
        "same_dataset": same_dataset,
        "regressions": regressions,
        "passed": same_dataset and not regressions,
        "baseline": {
            "recall_at_3": baseline.recall_at_3,
            "recall_at_5": baseline.recall_at_5,
        },
        "current": {
            "recall_at_3": current.recall_at_3,
            "recall_at_5": current.recall_at_5,
        },
    }


def load_retrieval_report(path: Path) -> RetrievalEvaluationReport:
    """Load one versioned baseline report."""
    return RetrievalEvaluationReport.model_validate_json(path.read_text())


def write_retrieval_report(
    report: RetrievalEvaluationReport,
    path: Path,
) -> None:
    """Write stable, reviewable evaluation evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2) + "\n")
