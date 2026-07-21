"""Contracts for the leakage-safe synthetic kinematic evaluation laboratory."""

from dataclasses import replace

import pytest

from app.evaluation.kinematic_harness import (
    DatasetSplit,
    ScenarioType,
    build_report,
    generate_dataset,
    validate_no_split_leakage,
)


def test_dataset_generation_is_deterministic_from_seed() -> None:
    first = generate_dataset(seed=42, session_count=5)
    second = generate_dataset(seed=42, session_count=5)

    assert first == second
    assert {scenario.generator_version for scenario in first} == {"1.0"}
    assert all(len(scenario.source_sha256) == 64 for scenario in first)


def test_variants_from_one_source_session_never_cross_splits() -> None:
    scenarios = generate_dataset(session_count=90)

    validate_no_split_leakage(scenarios)
    source_splits: dict[str, set[DatasetSplit]] = {}
    for scenario in scenarios:
        source_splits.setdefault(scenario.source_session_id, set()).add(scenario.split)

    assert set.union(*source_splits.values()) == set(DatasetSplit)
    assert all(len(splits) == 1 for splits in source_splits.values())


def test_split_leakage_validator_rejects_a_crossed_variant() -> None:
    scenarios = list(generate_dataset(session_count=1))
    crossed_split = (
        DatasetSplit.TEST
        if scenarios[-1].split is not DatasetSplit.TEST
        else DatasetSplit.TRAIN
    )
    scenarios[-1] = replace(scenarios[-1], split=crossed_split)

    with pytest.raises(ValueError, match="crosses dataset splits"):
        validate_no_split_leakage(scenarios)


def test_rules_only_baseline_reports_strengths_and_known_gaps() -> None:
    report = build_report(generate_dataset(session_count=30), split=DatasetSplit.TEST)
    metrics = report["metrics_by_scenario_type"]

    assert report["scope"] == "synthetic_scenarios_only"
    assert report["synthetic_clean_sequence_alert_rate"] == 0
    for scenario_type in (
        ScenarioType.ABRUPT_POSITION,
        ScenarioType.ABRUPT_ALTITUDE,
        ScenarioType.ABRUPT_VELOCITY,
        ScenarioType.ABRUPT_HEADING,
    ):
        assert metrics[scenario_type.value]["detection_rate"] == 1
        assert metrics[scenario_type.value]["median_time_to_detect_seconds"] == 0
    assert metrics[ScenarioType.GRADUAL_POSITION_DRIFT.value]["detection_rate"] == 0
    assert metrics[ScenarioType.REPLAYED_TIMESTAMP.value]["detection_rate"] == 0
    assert metrics[ScenarioType.REPLAYED_TIMESTAMP.value]["insufficient_pairs"] > 0


def test_attack_metadata_records_reproduction_inputs() -> None:
    scenario = next(
        item
        for item in generate_dataset(seed=88, session_count=1)
        if item.scenario_type is ScenarioType.ABRUPT_POSITION
    )

    assert scenario.seed == 88
    assert scenario.detection_window is not None
    assert scenario.detection_window.start_index == 5
    assert scenario.attack_parameters["position_jump_degrees"] == 0.05
