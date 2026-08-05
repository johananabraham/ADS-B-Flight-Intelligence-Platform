"""Generator 1.1 scenario coverage and classification contracts."""

from app.evaluation.kinematic_harness import (
    DatasetSplit,
    ScenarioClass,
    ScenarioType,
    build_extended_report,
    generate_dataset,
    generate_extended_dataset,
    validate_no_split_leakage,
)


def scenario_by_type(scenario_type: ScenarioType):
    return next(
        scenario
        for scenario in generate_extended_dataset(seed=42, session_count=1)
        if scenario.scenario_type is scenario_type
    )


def test_generator_v1_baseline_is_unchanged() -> None:
    scenarios = generate_dataset(seed=42, session_count=1)

    assert len(scenarios) == 7
    assert {scenario.generator_version for scenario in scenarios} == {"1.0"}


def test_extended_generation_is_deterministic_and_leakage_safe() -> None:
    first = generate_extended_dataset(seed=42, session_count=12)
    second = generate_extended_dataset(seed=42, session_count=12)

    assert first == second
    assert len(first) == 12 * len(ScenarioType)
    assert {scenario.generator_version for scenario in first} == {"1.1"}
    validate_no_split_leakage(first)


def test_missing_messages_preserve_elapsed_motion() -> None:
    scenario = scenario_by_type(ScenarioType.MISSING_MESSAGES)

    assert len(scenario.observations) == 10
    assert scenario.attack_parameters["removed_observations"] == 2
    assert max(
        (
            current.observed_at - previous.observed_at
        ).total_seconds()
        for previous, current in zip(
            scenario.observations,
            scenario.observations[1:],
        )
    ) == 3


def test_latency_jitter_changes_receive_time_not_aircraft_time() -> None:
    clean = scenario_by_type(ScenarioType.CLEAN)
    jittered = scenario_by_type(ScenarioType.LATENCY_JITTER)

    assert [item.observed_at for item in jittered.observations] == [
        item.observed_at for item in clean.observations
    ]
    assert any(
        item.received_at != item.observed_at for item in jittered.observations
    )


def test_ghost_and_identity_conflict_encode_distinct_detector_gaps() -> None:
    clean = scenario_by_type(ScenarioType.CLEAN)
    ghost = scenario_by_type(ScenarioType.GHOST_TRACK)
    conflict = scenario_by_type(ScenarioType.IDENTITY_CONFLICT)

    assert ghost.observations[0].icao_hex != clean.observations[0].icao_hex
    assert {item.icao_hex for item in ghost.observations} == {
        ghost.observations[0].icao_hex
    }
    assert conflict.observations[5].provenance != conflict.observations[4].provenance
    assert conflict.observations[5].icao_hex == conflict.observations[4].icao_hex


def test_edge_controls_cover_high_rate_date_line_and_polar_tracks() -> None:
    high_rate = scenario_by_type(ScenarioType.CLEAN_HIGH_RATE)
    date_line = scenario_by_type(ScenarioType.CLEAN_DATE_LINE)
    polar = scenario_by_type(ScenarioType.CLEAN_POLAR)

    assert (
        high_rate.observations[1].observed_at
        - high_rate.observations[0].observed_at
    ).total_seconds() == 0.2
    assert any(item.longitude < 0 for item in date_line.observations)
    assert all(item.latitude > 89 for item in polar.observations)


def test_extended_report_separates_controls_impairments_and_attacks() -> None:
    report = build_extended_report(
        generate_extended_dataset(session_count=30),
        split=DatasetSplit.TEST,
    )
    classes = report["metrics_by_scenario_class"]
    metrics = report["metrics_by_scenario_type"]

    assert report["generator"]["version"] == "1.1"
    assert report["synthetic_control_sequence_alert_rate"] == 0
    assert report["synthetic_impairment_sequence_alert_rate"] == 0
    test_sessions = report["generator"]["source_session_count"]
    assert classes[ScenarioClass.CONTROL.value]["scenarios"] == 4 * test_sessions
    assert classes[ScenarioClass.IMPAIRMENT.value]["scenarios"] == 2 * test_sessions
    assert metrics[ScenarioType.ABRUPT_POSITION.value]["detection_rate"] == 1
    assert metrics[ScenarioType.GHOST_TRACK.value]["detection_rate"] == 0
    assert metrics[ScenarioType.IDENTITY_CONFLICT.value]["insufficient_pairs"] > 0
    assert metrics[ScenarioType.CLEAN_HIGH_RATE.value]["insufficient_pairs"] > 0
    assert all(
        "scenario_parameters" in entry and "attack_parameters" not in entry
        for entry in report["scenario_manifest"]
    )
