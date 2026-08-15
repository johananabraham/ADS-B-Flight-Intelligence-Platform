"""Fail-closed path rules for the complete-history release audit."""

from scripts.audit_release_history import forbidden_reason


def test_rejects_private_and_raw_artifact_paths() -> None:
    for path in (
        ".private/day-1.bin",
        "private-captures/capture.txt",
        "calibration/local/manifest.json",
        "captures/traffic.sbs",
        "backup/production.sqlite3",
        "edge/mosquitto/secrets/client.key",
        "receiver-location/exact.json",
        "metadata/private_salt/value.txt",
    ):
        assert forbidden_reason(path) is not None


def test_allows_documentation_and_inert_examples() -> None:
    for path in (
        "edge/mosquitto/secrets/README.md",
        "firmware/esp32-station/certs/broker_ca.pem.example",
        "docs/PRIVACY.md",
        "evaluation/results/frozen_policy_synthetic_v1.json",
    ):
        assert forbidden_reason(path) is None
