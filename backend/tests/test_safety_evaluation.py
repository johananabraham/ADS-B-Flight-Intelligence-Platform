"""Deterministic, source-bound safety retrieval evaluation tests."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.safety.evaluation import (
    DEFAULT_RETRIEVAL_CONFIGURATION,
    RetrievalCaseResult,
    RetrievalEvaluationReport,
    compare_retrieval_baseline,
    evaluate_retrieval_dataset,
    load_retrieval_dataset,
)


DATASET_PATH = Path("evaluation/safety/faa_part91_retrieval_v1.json")


def test_checked_in_dataset_has_15_exact_official_source_cases():
    dataset = load_retrieval_dataset(DATASET_PATH)

    assert dataset.evidence_class == "OFFICIAL_SOURCE_ENGINEERING_REVIEW"
    assert dataset.source_artifact.parsed_sections == 286
    assert len(dataset.cases) == 15
    assert len({case.case_id for case in dataset.cases}) == 15
    assert all(case.expected_document_ids for case in dataset.cases)
    assert all(
        document_id.endswith(":2026-07-24")
        for case in dataset.cases
        for document_id in case.expected_document_ids
    )


@pytest.mark.asyncio
async def test_retrieval_metrics_use_exact_ranked_document_ids():
    dataset = load_retrieval_dataset(DATASET_PATH)
    expected_by_question = {
        case.question: case.expected_document_ids[0] for case in dataset.cases
    }
    rank_by_question = {
        case.question: (4 if index % 2 else 1)
        for index, case in enumerate(dataset.cases)
    }

    async def fake_search(*, query_text, n_results, where):
        assert n_results == 5
        assert where == {"cfr_part": 91}
        expected = expected_by_question[query_text]
        distractors = [f"distractor-{index}" for index in range(5)]
        distractors[rank_by_question[query_text] - 1] = expected
        return {"ids": distractors, "metadatas": [], "documents": [], "distances": []}

    report = await evaluate_retrieval_dataset(dataset, search=fake_search)

    assert report.case_count == 15
    assert report.recall_at_3 == pytest.approx(8 / 15)
    assert report.recall_at_5 == 1.0
    assert report.mean_reciprocal_rank == pytest.approx((8 + 7 / 4) / 15)


def _report(
    *,
    recall_at_3: float,
    recall_at_5: float,
    dataset_id: str = "dataset",
    search_ef: int = 100,
):
    dataset = load_retrieval_dataset(DATASET_PATH)
    results = tuple(
        RetrievalCaseResult(
            case_id=f"R{index:02d}",
            expected_document_ids=(f"expected-{index}",),
            retrieved_document_ids=(f"expected-{index}",),
            recall_at_3=recall_at_3,
            recall_at_5=recall_at_5,
            reciprocal_rank=1.0,
            latency_ms=1.0,
        )
        for index in range(1, 16)
    )
    return RetrievalEvaluationReport(
        generated_at=datetime.now(timezone.utc),
        dataset_id=dataset_id,
        evidence_class=dataset.evidence_class,
        source_artifact=dataset.source_artifact,
        case_count=15,
        recall_at_3=recall_at_3,
        recall_at_5=recall_at_5,
        mean_reciprocal_rank=0.8,
        mean_latency_ms=1.0,
        retrieval_configuration=DEFAULT_RETRIEVAL_CONFIGURATION.model_copy(
            update={"embedding_backend": "test", "hnsw_search_ef": search_ef}
        ),
        limitations=("test only",),
        results=results,
    )


def test_baseline_comparison_fails_on_regression_or_dataset_change():
    baseline = _report(recall_at_3=0.8, recall_at_5=1.0)

    regression = compare_retrieval_baseline(
        _report(recall_at_3=0.7, recall_at_5=1.0),
        baseline,
    )
    mismatch = compare_retrieval_baseline(
        _report(recall_at_3=0.8, recall_at_5=1.0, dataset_id="other"),
        baseline,
    )
    configuration_mismatch = compare_retrieval_baseline(
        _report(recall_at_3=0.8, recall_at_5=1.0, search_ef=200),
        baseline,
    )

    assert regression["passed"] is False
    assert regression["regressions"] == ["recall_at_3"]
    assert mismatch["passed"] is False
    assert mismatch["same_dataset"] is False
    assert configuration_mismatch["passed"] is False
    assert configuration_mismatch["same_dataset"] is False
