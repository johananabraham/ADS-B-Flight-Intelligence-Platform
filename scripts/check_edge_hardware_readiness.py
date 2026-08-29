#!/usr/bin/env python3
"""Fail-closed preflight for exposing the edge MQTT broker to a physical ESP32.

The check intentionally permits only an exact private LAN address. It never prints
credentials or certificate contents.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import ssl
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
NODE_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
SECRET_FILENAMES = (
    "ca.crt",
    "server.crt",
    "server.key",
    "passwords",
    "station-consumer.password",
)


def validate_private_bind_address(value: str) -> str:
    """Return a normalized, exact private address or raise ValueError."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError("MQTT bind address must be a literal IP address") from exc
    if (
        address.version != 4
        or address.is_loopback
        or address.is_unspecified
        or address.is_multicast
        or address.is_link_local
        or address.is_reserved
        or not address.is_private
    ):
        raise ValueError(
            "physical mode requires an exact private IPv4 LAN address; loopback, "
            "wildcard, link-local, multicast, reserved, and public addresses are rejected"
        )
    return str(address)


def validate_node_id(value: str) -> str:
    if not NODE_ID_PATTERN.fullmatch(value):
        raise ValueError("node ID must match the firmware/backend identity contract")
    return value


def certificate_facts(path: Path) -> Mapping[str, Any]:
    try:
        return ssl._ssl._test_decode_cert(str(path))  # type: ignore[attr-defined]
    except (OSError, ssl.SSLError) as exc:
        raise ValueError("server certificate is unreadable or invalid") from exc


def validate_certificate(
    facts: Mapping[str, Any], broker_host: str, *, now: datetime | None = None
) -> None:
    current = now or datetime.now(timezone.utc)
    not_after = facts.get("notAfter")
    if not isinstance(not_after, str):
        raise ValueError("server certificate has no expiration")
    expires_at = datetime.fromtimestamp(ssl.cert_time_to_seconds(not_after), timezone.utc)
    if (expires_at - current).total_seconds() < 30 * 24 * 60 * 60:
        raise ValueError("server certificate expires in less than 30 days")

    expected_kind = "IP Address"
    try:
        ipaddress.ip_address(broker_host)
    except ValueError:
        expected_kind = "DNS"
    names = facts.get("subjectAltName", ())
    if (expected_kind, broker_host) not in names:
        raise ValueError("server certificate SAN does not contain the firmware broker host")


def validate_secret_files(secret_dir: Path, node_id: str) -> None:
    required = (*SECRET_FILENAMES, f"{node_id}.password", f"{node_id}-bridge.password")
    for filename in required:
        path = secret_dir / filename
        if not path.is_file():
            raise ValueError(f"missing required edge credential file: {filename}")
    for filename in (
        "server.key",
        "passwords",
        "station-consumer.password",
        f"{node_id}.password",
        f"{node_id}-bridge.password",
    ):
        mode = stat.S_IMODE((secret_dir / filename).stat().st_mode)
        if mode & 0o077:
            raise ValueError(f"credential file is group/world accessible: {filename}")


def validate_acl(acl_text: str, node_id: str) -> None:
    required = (
        f"user {node_id}",
        f"topic write adsb/stations/v1/{node_id}/telemetry",
        f"topic write adsb/stations/v1/{node_id}/presence",
        f"user {node_id}-bridge",
        f"topic write adsb/stations/v1/{node_id}/pipeline",
        "user station-consumer",
        "topic read adsb/stations/v1/+/telemetry",
        "topic read adsb/stations/v1/+/presence",
        "topic read adsb/stations/v1/+/pipeline",
    )
    missing = [line for line in required if line not in acl_text.splitlines()]
    if missing:
        raise ValueError("broker ACL is missing required station or consumer grants")


def assess_readiness(
    *,
    bind_address: str,
    broker_host: str,
    node_id: str,
    secret_dir: Path,
    acl_path: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    normalized_bind = validate_private_bind_address(bind_address)
    validate_node_id(node_id)
    try:
        broker_ip = ipaddress.ip_address(broker_host)
    except ValueError:
        broker_ip = None
    if broker_ip is not None and str(broker_ip) != normalized_bind:
        raise ValueError("numeric broker host must equal MQTT_BIND_ADDRESS")
    validate_secret_files(secret_dir, node_id)
    validate_acl(acl_path.read_text(encoding="utf-8"), node_id)
    validate_certificate(certificate_facts(secret_dir / "server.crt"), broker_host, now=now)
    return {
        "status": "READY",
        "mode": "physical_private_lan",
        "bind_address": normalized_bind,
        "broker_host": broker_host,
        "node_id": node_id,
        "checks": {
            "exact_private_bind": True,
            "certificate_san_and_expiry": True,
            "credentials_present_and_private": True,
            "least_privilege_acl": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--broker-host", required=True)
    parser.add_argument("--bind-address", default=os.getenv("MQTT_BIND_ADDRESS"))
    parser.add_argument("--node-id", default="roof-node-1")
    parser.add_argument("--secret-dir", type=Path, default=ROOT / "edge/mosquitto/secrets")
    parser.add_argument("--acl", type=Path, default=ROOT / "edge/mosquitto/config/acl")
    args = parser.parse_args()
    if not args.bind_address:
        parser.error("set MQTT_BIND_ADDRESS or pass --bind-address")
    try:
        result = assess_readiness(
            bind_address=args.bind_address,
            broker_host=args.broker_host,
            node_id=args.node_id,
            secret_dir=args.secret_dir,
            acl_path=args.acl,
        )
    except (OSError, ValueError) as exc:
        parser.exit(1, f"edge hardware preflight failed: {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
