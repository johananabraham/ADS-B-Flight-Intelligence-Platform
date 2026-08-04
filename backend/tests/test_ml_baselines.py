"""Interpretable ML feature, abstention, and evaluation contracts."""

from app.evaluation.kinematic_harness import (
    DatasetSplit,
    ScenarioType,
    generate_extended_dataset,
)
from app.evaluation.ml_baselines import (
    FEATURE_NAMES,
    FeatureStatus,
    build_ml_report,
    build_training_rows,
    evaluate_detector,
    extract_features,
)


def scenario_by_type(scenario_type: ScenarioType):
    return next(
        scenario
        for scenario in generate_extended_dataset(seed=42, session_count=1)
        if scenario.scenario_type is scenario_type
    )


def test_feature_schema_is_finite_and_stable() -> None:
    features = extract_features(scenario_by_type(ScenarioType.CLEAN))

    assert features.status is FeatureStatus.AVAILABLE
    assert features.abstain_reason is None
    assert tuple(features.as_mapping()) == FEATURE_NAMES
    assert all(value >= 0 for value in features.values)


def test_high_rate_control_takes_explicit_abstain_path() -> None:
    features = extract_features(scenario_by_type(ScenarioType.CLEAN_HIGH_RATE))

    assert features.status is FeatureStatus.ABSTAIN
    assert "No consecutive pair" in features.abstain_reason


def test_identity_conflict_preserves_cross_source_feature() -> None:
    features = extract_features(scenario_by_type(ScenarioType.IDENTITY_CONFLICT))

    assert features.status is FeatureStatus.AVAILABLE
    assert features.as_mapping()["unique_provenance_count"] == 2
    assert features.as_mapping()["pair_insufficient_count"] == 2


def test_training_rows_use_only_the_requested_session_split() -> None:
    scenarios = generate_extended_dataset(session_count=30)
    rows, labels = build_training_rows(scenarios, split=DatasetSplit.TRAIN)
    train_sessions = {
        scenario.source_session_id
        for scenario in scenarios
        if scenario.split is DatasetSplit.TRAIN
    }

    assert rows
    assert {row.source_session_id for row in rows} <= train_sessions
    assert set(labels) == {0, 1}


def test_ml_report_is_deterministic_and_keeps_models_offline() -> None:
    scenarios = generate_extended_dataset(session_count=30)
    first = build_ml_report(
        scenarios,
        seed=123,
        implementation_revision="test-revision",
    )
    second = build_ml_report(
        scenarios,
        seed=123,
        implementation_revision="test-revision",
    )

    assert first == second
    assert first["promotion_decision"] == "OFFLINE_EVALUATION_ONLY"
    assert first["feature_schema_version"] == "1.0"
    assert first["generator_versions"] == ["1.1"]
    assert set(first["models"]) == {
        "always_normal",
        "rules_only",
        "logistic_regression",
        "decision_tree",
        "random_forest",
    }
    assert set(first["validation_models"]) == set(first["models"])


def test_rules_baseline_reports_known_detection_boundaries() -> None:
    report = build_ml_report(
        generate_extended_dataset(session_count=30),
        seed=123,
        implementation_revision="test-revision",
    )
    metrics = report["models"]["rules_only"]["metrics_by_scenario_type"]

    assert metrics[ScenarioType.ABRUPT_POSITION.value]["detection_rate"] == 1
    assert metrics[ScenarioType.GRADUAL_POSITION_DRIFT.value]["detection_rate"] == 1
    assert metrics[ScenarioType.GHOST_TRACK.value]["detection_rate"] == 0
    assert metrics[ScenarioType.CLEAN_HIGH_RATE.value]["abstained"] > 0
    assert report["models"]["rules_only"]["field_false_alerts_per_flight_hour"] is None


def test_normal_sequence_alerts_are_counted_as_false_alerts() -> None:
    report = evaluate_detector(
        generate_extended_dataset(session_count=30),
        name="always_alert",
        predict=lambda _: True,
    )

    assert report["synthetic_control_sequence_alert_rate"] > 0
    assert report["synthetic_impairment_sequence_alert_rate"] == 1
    assert report["precision"] < 1
