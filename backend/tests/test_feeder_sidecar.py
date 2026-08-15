"""Transport, storage, and privacy contracts for the feeder sidecar."""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from sidecar.app import create_app
from sidecar.config import SidecarConfig
from sidecar.sbs import ParseFailure, parse_sbs_line
from sidecar.store import RotatingEventStore
from scripts.check_pilot_readiness import assess


SBS_LINE = (
    "MSG,3,1,42,A1B2C3,42,2026/08/15,12:34:56.789,"
    "2026/08/15,12:34:56.800,DAL1842,12500,310,72,"
    "39.9612,-82.9988,800,2431,0,0,0,0"
)


def config(tmp_path: Path) -> SidecarConfig:
    return SidecarConfig(
        input_host="127.0.0.1",
        input_port=30003,
        receiver_id="private-receiver-label",
        bind_host="127.0.0.1",
        port=8090,
        policy_path=Path(__file__).parents[1] / "integrity_core/policies/feeder-v1.json",
        event_directory=tmp_path / "events",
        retention_hours=168,
        store_max_mb=1,
        queue_maxsize=32,
    )


def test_sbs_parser_has_bounded_failures_and_stable_identity() -> None:
    first = parse_sbs_line(SBS_LINE)
    retry = parse_sbs_line(SBS_LINE)

    assert first.failure is None
    assert first.data == retry.data
    assert len(str(first.data["_raw_message_id"])) == 64
    assert parse_sbs_line("short").failure is ParseFailure.TOO_FEW_FIELDS
    assert parse_sbs_line(b"x" * 4097).failure is ParseFailure.TOO_LONG
    assert parse_sbs_line(SBS_LINE.replace("A1B2C3", "NOTHEX")).failure is ParseFailure.INVALID_AIRCRAFT_ID


def test_store_tolerates_truncated_tail_and_quarantines_invalid_segment(tmp_path: Path) -> None:
    directory = tmp_path / "store"
    directory.mkdir()
    valid = {"schema_version": "1.0", "observed_at": "2026-08-15T12:00:00Z"}
    (directory / "events-00000001.jsonl").write_bytes(
        (json.dumps(valid) + "\n" + '{"truncated":').encode()
    )
    (directory / "events-00000002.jsonl").write_text("not-json\n", encoding="utf-8")

    store = RotatingEventStore(directory, retention_hours=1, max_bytes=1024 * 1024)
    try:
        assert list(store.recovered_events) == [valid]
        assert (directory / "events-00000002.jsonl.invalid").exists()
    finally:
        store.close()


def test_store_rotates_and_enforces_hard_size_bound(tmp_path: Path) -> None:
    store = RotatingEventStore(
        tmp_path / "store",
        retention_hours=1,
        max_bytes=1500,
        segment_bytes=300,
    )
    try:
        for index in range(30):
            store.remember(
                {
                    "schema_version": "1.0",
                    "observed_at": "2026-08-15T12:00:00Z",
                    "state": "QUESTIONABLE",
                    "payload": "x" * 100,
                    "index": index,
                }
            )
        assert sum(path.stat().st_size for path in (tmp_path / "store").glob("*.jsonl")) <= 1500
    finally:
        store.close()


def test_store_suppresses_duplicate_deterministic_event_ids(tmp_path: Path) -> None:
    store = RotatingEventStore(
        tmp_path / "store", retention_hours=1, max_bytes=1024 * 1024
    )
    record = {
        "schema_version": "1.0",
        "event_id": "deterministic-id",
        "observed_at": "2026-08-15T12:00:00Z",
    }
    try:
        assert store.remember(record) is True
        assert store.remember(record) is False
        assert list(store.recovered_events) == [record]
    finally:
        store.close()


def test_bounded_queue_reports_every_drop(tmp_path: Path) -> None:
    app = create_app(config(tmp_path), start_ingestion=False)
    runtime = app.state.runtime
    now = datetime.now(timezone.utc)
    for _ in range(runtime.queue.maxsize):
        assert runtime.enqueue(SBS_LINE.encode(), now) is True

    assert runtime.enqueue(SBS_LINE.encode(), now) is False
    assert runtime.metrics.dropped == 1
    assert runtime.health.connection == "DEGRADED"
    runtime.store.close()


def test_rest_websocket_metrics_and_privacy_contract(tmp_path: Path) -> None:
    app = create_app(config(tmp_path), start_ingestion=False)
    runtime = app.state.runtime
    asyncio.run(
        runtime.process_line(
            SBS_LINE,
            received_at=datetime(2026, 8, 15, 12, 34, 56, 800000, tzinfo=timezone.utc),
        )
    )
    with TestClient(app) as client:
        health = client.get("/api/v1/integrity/health")
        listing = client.get("/api/v1/integrity/tracks")
        assert health.status_code == 200
        assert listing.status_code == 200
        snapshot = listing.json()["tracks"][0]
        assert set(snapshot) == {
            "schema_version",
            "track_id",
            "observed_at",
            "state",
            "observation_count",
            "window_seconds",
            "policy_version",
            "active_evidence",
            "limitations",
        }
        assert client.get(f"/api/v1/integrity/tracks/{snapshot['track_id']}").status_code == 200
        assert client.get("/api/v1/integrity/events?limit=1001").status_code == 422
        metrics = client.get("/metrics").text
        assert "adsb_sidecar_dropped_messages_total" in metrics
        assert "private-receiver-label" not in metrics
        assert "A1B2C3" not in metrics
        with client.websocket_connect("/api/v1/integrity/stream") as websocket:
            assert websocket.receive_json() == {
                "type": "hello",
                "schema_version": "1.0",
                "policy_version": "1.0-development",
            }


def test_ui_is_read_only_and_has_permanent_claim_boundary(tmp_path: Path) -> None:
    app = create_app(config(tmp_path), start_ingestion=False)
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Research integrity evidence" in page.text
        assert "login" not in page.text.lower()
        assert client.post("/api/v1/integrity/tracks").status_code == 405
        assert "default-src 'self'" in page.headers["content-security-policy"]


def test_accelerated_soak_has_no_hidden_drops_and_meets_latency_memory_targets() -> None:
    root = Path(__file__).parents[2]
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_feeder_soak.py",
            "--duration",
            "10",
            "--rate",
            "100",
            "--accelerated",
        ],
        cwd=root,
        env={**os.environ, "PYTHONPATH": "backend:."},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout)

    assert result["messages"] == 1000
    assert result["dropped_messages_total"] == 0
    assert result["p95_processing_ms"] < 100
    assert result["process_memory_mb"] <= 256
    assert result["passed"] is True


def test_pilot_summary_is_aggregate_and_readiness_requires_live_progress(
    tmp_path: Path,
) -> None:
    app = create_app(config(tmp_path), start_ingestion=False)
    runtime = app.state.runtime
    before = runtime.pilot_summary()
    with TestClient(app) as client:
        accepted = asyncio.run(
            runtime.process_line(
                SBS_LINE,
                received_at=datetime(2026, 8, 15, 12, 0, 1, tzinfo=timezone.utc),
            )
        )
        assert accepted is True
        after = client.get("/api/v1/pilot/summary").json()
        serialized = json.dumps(after)
        assert "private-receiver-label" not in serialized
        assert "A1B2C3" not in serialized
        assert "40.6413" not in serialized
        assert "2026-08-15" not in serialized
        assert after["parsed_messages_total"] == 1
        assert after["observations_evaluated_total"] == 1
        runtime.health.connection = "CONNECTED"
        readiness = assess(before, after, runtime.health_dict())
        assert readiness["status"] == "READY"
        assert all(readiness["checks"].values())


def test_pilot_readiness_fails_closed_without_traffic_progress(tmp_path: Path) -> None:
    app = create_app(config(tmp_path), start_ingestion=False)
    summary = app.state.runtime.pilot_summary()
    result = assess(summary, summary, app.state.runtime.health_dict())

    assert result["status"] == "NOT_READY"
    assert result["checks"]["source_connected"] is False
    assert result["checks"]["messages_advancing"] is False
