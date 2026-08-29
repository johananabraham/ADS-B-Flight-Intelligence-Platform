from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.check_edge_hardware_readiness import (
    validate_acl,
    validate_certificate,
    validate_node_id,
    validate_private_bind_address,
    validate_secret_files,
)


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "0.0.0.0", "169.254.1.2", "8.8.8.8", "mqtt.local", "fd00::10"],
)
def test_physical_broker_rejects_non_private_or_non_exact_bind(address: str) -> None:
    with pytest.raises(ValueError):
        validate_private_bind_address(address)


def test_physical_broker_accepts_exact_private_lan_bind() -> None:
    assert validate_private_bind_address("192.168.50.10") == "192.168.50.10"


@pytest.mark.parametrize("node_id", ["Roof-Node", "-roof-node", "roof_node", "roof-node-"])
def test_node_identity_rejects_values_outside_wire_contract(node_id: str) -> None:
    with pytest.raises(ValueError):
        validate_node_id(node_id)


def test_certificate_requires_matching_san_and_at_least_30_days() -> None:
    facts = {
        "notAfter": "Dec 31 23:59:59 2027 GMT",
        "subjectAltName": (("IP Address", "192.168.50.10"),),
    }
    validate_certificate(
        facts,
        "192.168.50.10",
        now=datetime(2026, 8, 29, tzinfo=timezone.utc),
    )
    with pytest.raises(ValueError, match="SAN"):
        validate_certificate(
            facts,
            "192.168.50.11",
            now=datetime(2026, 8, 29, tzinfo=timezone.utc),
        )


def test_certificate_rejects_near_expiry() -> None:
    with pytest.raises(ValueError, match="30 days"):
        validate_certificate(
            {
                "notAfter": "Sep 10 00:00:00 2026 GMT",
                "subjectAltName": (("DNS", "mqtt.lan"),),
            },
            "mqtt.lan",
            now=datetime(2026, 8, 29, tzinfo=timezone.utc),
        )


def test_secret_permissions_and_acl_are_fail_closed(tmp_path: Path) -> None:
    node_id = "roof-node-1"
    for filename in (
        "ca.crt",
        "server.crt",
        "server.key",
        "passwords",
        "station-consumer.password",
        f"{node_id}.password",
    ):
        path = tmp_path / filename
        path.write_text("fixture", encoding="utf-8")
        path.chmod(0o600 if filename not in {"ca.crt", "server.crt"} else 0o644)
    validate_secret_files(tmp_path, node_id)

    (tmp_path / f"{node_id}.password").chmod(0o644)
    with pytest.raises(ValueError, match="group/world"):
        validate_secret_files(tmp_path, node_id)

    valid_acl = "\n".join(
        (
            f"user {node_id}",
            f"topic write adsb/stations/v1/{node_id}/telemetry",
            f"topic write adsb/stations/v1/{node_id}/presence",
            "user station-consumer",
            "topic read adsb/stations/v1/+/telemetry",
            "topic read adsb/stations/v1/+/presence",
        )
    )
    validate_acl(valid_acl, node_id)
    with pytest.raises(ValueError, match="ACL"):
        validate_acl(valid_acl.replace("/presence", "/wrong", 1), node_id)
