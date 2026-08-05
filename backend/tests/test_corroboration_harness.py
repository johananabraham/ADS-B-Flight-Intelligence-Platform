from app.evaluation.corroboration_harness import (
    passes_offline_gate,
    run_corroboration_evaluation,
)


def test_four_hour_offline_evaluation_covers_every_state_deterministically():
    report = run_corroboration_evaluation()
    results = report["results"]

    assert results["classification_mismatches"] == []
    assert results["state_counts"] == {
        "CONFLICTING": 120,
        "CORROBORATED": 120,
        "EXTERNAL_ONLY": 120,
        "LOCAL_ONLY": 120,
        "STALE": 120,
        "UNAVAILABLE": 120,
    }
    assert results["provider_availability_rate"] == 5 / 6
    assert results["both_source_coverage_rate"] == 0.5
    assert len(results["conflict_samples"]) == 10
    assert passes_offline_gate(report)


def test_offline_report_forbids_live_field_claims():
    report = run_corroboration_evaluation(hours=1)
    boundaries = report["verification_boundaries"]

    assert boundaries["live_provider_requests"] == 0
    assert boundaries["captured_rf_sessions"] == 0
    assert boundaries["human_conflict_review"] == "NOT_PERFORMED"
    assert boundaries["field_coverage_claim_permitted"] is False
    assert boundaries["field_latency_claim_permitted"] is False


def test_offline_gate_rejects_classification_mismatch():
    report = run_corroboration_evaluation(hours=1)
    report["results"]["classification_mismatches"].append(
        {"expected": "CORROBORATED", "actual": "CONFLICTING"}
    )

    assert passes_offline_gate(report) is False
