"""Tests for privacy-safe independent feeder pilot evidence reporting."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from evaluation.pilot.report import (
    PRIVACY_BOUNDARY,
    ParticipantEvidence,
    build_pilot_report,
    render_pilot_report_markdown,
)


def summary(
    day: int,
    *,
    session: str = "session_alpha_123",
    session_day: int | None = None,
    dropped: int = 0,
    policy: str = "feeder-v1",
) -> dict[str, object]:
    counter_day = session_day or day
    events = counter_day * 2
    return {
        "schema_version": "1.0",
        "pilot_session_id": session,
        "uptime_seconds": counter_day * 86_400,
        "source_connected_seconds": counter_day * 82_000,
        "source_connected_ratio": 0.949074,
        "connection": "CONNECTED",
        "policy_version": policy,
        "parsed_messages_total": counter_day * 1_000,
        "parse_failures_total": counter_day,
        "parse_failures_by_reason": {"invalid_value": counter_day},
        "observations_evaluated_total": counter_day * 999,
        "dropped_messages_total": dropped,
        "reconnects_total": counter_day - 1,
        "queue_depth": 0,
        "process_memory_mb": 42.5 + counter_day,
        "current_track_state_counts": {
            "NOMINAL": 4,
            "QUESTIONABLE": 1 if day == 4 else 0,
            "INSUFFICIENT_DATA": 1,
        },
        "current_active_evidence_counts": (
            {"TIMING_GAP": 1} if day == 4 else {}
        ),
        "stored_event_count": events,
        "stored_event_type_counts": {"evidence_opened": events},
        "stored_evidence_kind_counts": {"TIMING_GAP": events},
        "privacy_boundary": PRIVACY_BOUNDARY,
    }


def participant(
    participant_id: str,
    *,
    days: int,
    installation_minutes: int,
    useful_outcome: str = "NONE",
    withdrawn: bool = False,
    dropped: int = 0,
    drops_investigated: bool = False,
    summaries: list[dict[str, object]] | None = None,
) -> ParticipantEvidence:
    daily = summaries or [summary(day, dropped=dropped) for day in range(1, days + 1)]
    value = {
        "schema_version": "1.0",
        "participant_id": participant_id,
        "consent_confirmed": True,
        "privacy_review_confirmed": True,
        "withdrawn": withdrawn,
        "installation_attempted": True,
        "unaided_installation": True,
        "installation_minutes_rounded": installation_minutes,
        "readiness_status": "READY",
        "daily_snapshots": [
            {"day_index": index, "summary": item}
            for index, item in enumerate(daily, start=1)
        ],
        "state_meanings_explained_correctly": True,
        "drops_investigated": drops_investigated,
        "useful_outcome": useful_outcome,
        "keep_installed": "YES",
        "outcome_codes": (
            [useful_outcome] if useful_outcome == "OPERATIONAL_FINDING" else []
        ),
    }
    return ParticipantEvidence.model_validate_json(json.dumps(value))


def test_success_report_enforces_every_published_pilot_criterion() -> None:
    participants = (
        participant(
            "pilot-01",
            days=7,
            installation_minutes=10,
            useful_outcome="OPERATIONAL_FINDING",
        ),
        participant(
            "pilot-02",
            days=7,
            installation_minutes=14,
            dropped=2,
            drops_investigated=True,
        ),
        participant("pilot-03", days=3, installation_minutes=20),
    )

    report = build_pilot_report(participants)

    assert report["status"] == "PILOT_SUCCESS"
    assert all(report["success_criteria"].values())
    assert report["participants"]["median_unaided_installation_minutes"] == 14
    assert report["participants"]["seven_day_completions"] == 2
    assert report["aggregate_operations"]["dropped_messages_total"] == 2
    markdown = render_pilot_report_markdown(report)
    assert "does not establish that the detector catches spoofing" in markdown
    assert "aircraft" not in json.dumps(report["participants"]["runs"]).lower()


def test_report_preserves_withdrawals_and_refuses_premature_claim() -> None:
    report = build_pilot_report(
        (
            participant(
                "pilot-01",
                days=1,
                installation_minutes=8,
                withdrawn=True,
            ),
        )
    )

    assert report["status"] == "PILOT_INCOMPLETE"
    assert report["claim_scope"] == "pilot_criteria_not_met"
    assert report["participants"]["withdrawals"] == 1
    assert report["success_criteria"]["at_least_two_seven_day_completions"] is False


def test_counter_aggregation_handles_process_restart_without_double_counting() -> None:
    summaries = [summary(day) for day in range(1, 4)]
    summaries.extend(
        summary(
            day,
            session="session_bravo_456",
            session_day=day - 3,
        )
        for day in range(4, 8)
    )
    evidence = participant(
        "pilot-01",
        days=7,
        installation_minutes=9,
        summaries=summaries,
    )

    report = build_pilot_report((evidence,))

    assert report["aggregate_operations"]["parsed_messages_total"] == 7_000
    assert report["aggregate_operations"]["uptime_seconds"] == 7 * 86_400


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda value: value.update({"icao_hex": "A1B2C3"}), "extra_forbidden"),
        (
            lambda value: value.update({"privacy_boundary": "safe enough"}),
            "privacy boundary",
        ),
        (
            lambda value: value["current_track_state_counts"].pop("NOMINAL"),
            "every state",
        ),
    ),
)
def test_summary_allow_list_fails_closed_on_privacy_or_schema_drift(
    mutation, message: str
) -> None:
    unsafe = summary(1)
    mutation(unsafe)
    value = {
        "schema_version": "1.0",
        "participant_id": "pilot-01",
        "consent_confirmed": True,
        "privacy_review_confirmed": True,
        "withdrawn": False,
        "installation_attempted": True,
        "unaided_installation": True,
        "installation_minutes_rounded": 10,
        "readiness_status": "READY",
        "daily_snapshots": [{"day_index": 1, "summary": unsafe}],
        "state_meanings_explained_correctly": True,
        "drops_investigated": False,
        "useful_outcome": "NONE",
        "keep_installed": "UNSURE",
        "outcome_codes": [],
    }

    with pytest.raises(ValidationError, match=message):
        ParticipantEvidence.model_validate_json(json.dumps(value))


def test_rejects_counter_rollback_and_reappearing_process_session() -> None:
    rollback = [summary(1), summary(2)]
    rollback[1]["parsed_messages_total"] = 999
    rollback[1]["observations_evaluated_total"] = 998
    with pytest.raises(ValidationError, match="decreased"):
        participant(
            "pilot-01",
            days=2,
            installation_minutes=10,
            summaries=rollback,
        )

    reappearing = [
        summary(1, session="session_alpha_123"),
        summary(2, session="session_bravo_456", session_day=1),
        summary(3, session="session_alpha_123", session_day=2),
    ]
    with pytest.raises(ValidationError, match="cannot reappear"):
        participant(
            "pilot-01",
            days=3,
            installation_minutes=10,
            summaries=reappearing,
        )


def test_rejects_duplicate_participant_ids() -> None:
    first = participant("pilot-01", days=1, installation_minutes=10)
    second = participant("pilot-01", days=1, installation_minutes=12)

    with pytest.raises(ValueError, match="unique"):
        build_pilot_report((first, second))
