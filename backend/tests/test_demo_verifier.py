"""Tests for the end-to-end demo verification rules."""

import pytest

from scripts import verify_demo


def test_verifier_reports_cross_service_evidence(monkeypatch) -> None:
    monkeypatch.setattr(
        verify_demo,
        "fetch_json",
        lambda url: {"status": "healthy"} if url.endswith("/health") else [{}] * 6,
    )
    monkeypatch.setattr(
        verify_demo,
        "fetch_text",
        lambda _url: '<html><div id="root"></div></html>',
    )
    monkeypatch.setattr(
        verify_demo,
        "query_observation_evidence",
        lambda _database_container: (24, 24, 6),
    )

    evidence = verify_demo.verify_once(
        api_url="http://api",
        frontend_url="http://frontend",
        database_container="database",
        minimum_aircraft=6,
        minimum_observations=6,
    )

    assert evidence.active_aircraft == 6
    assert evidence.observations == 24
    assert evidence.unique_observations == 24
    assert evidence.observed_aircraft == 6


def test_verifier_rejects_duplicate_observation_ids(monkeypatch) -> None:
    monkeypatch.setattr(
        verify_demo,
        "fetch_json",
        lambda url: {"status": "healthy"} if url.endswith("/health") else [{}] * 6,
    )
    monkeypatch.setattr(
        verify_demo,
        "fetch_text",
        lambda _url: '<div id="root"></div>',
    )
    monkeypatch.setattr(
        verify_demo,
        "query_observation_evidence",
        lambda _database_container: (24, 23, 6),
    )

    with pytest.raises(RuntimeError, match="duplicate observation IDs"):
        verify_demo.verify_once(
            api_url="http://api",
            frontend_url="http://frontend",
            database_container="database",
            minimum_aircraft=6,
            minimum_observations=6,
        )
