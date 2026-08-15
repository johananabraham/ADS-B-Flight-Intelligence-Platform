"""Validated sidecar environment configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True)
class SidecarConfig:
    input_host: str
    input_port: int
    receiver_id: str
    bind_host: str
    port: int
    policy_path: Path
    event_directory: Path
    retention_hours: int
    store_max_mb: int
    queue_maxsize: int

    @classmethod
    def from_env(cls) -> "SidecarConfig":
        receiver_id = os.getenv("RECEIVER_ID", "").strip()
        if not receiver_id:
            raise ValueError("RECEIVER_ID is required")
        if len(receiver_id) > 100 or any(ord(char) < 32 for char in receiver_id):
            raise ValueError("RECEIVER_ID must be 1-100 printable characters")
        input_host = os.getenv("ADSB_INPUT_HOST", "host.docker.internal").strip()
        bind_host = os.getenv("SIDECAR_BIND_HOST", "127.0.0.1").strip()
        if not input_host or not bind_host:
            raise ValueError("host values cannot be empty")
        default_policy = Path(__file__).resolve().parents[1] / "backend" / "integrity_core" / "policies" / "feeder-v1.json"
        return cls(
            input_host=input_host,
            input_port=_bounded_int("ADSB_INPUT_PORT", 30003, 1, 65535),
            receiver_id=receiver_id,
            bind_host=bind_host,
            port=_bounded_int("SIDECAR_PORT", 8090, 1, 65535),
            policy_path=Path(os.getenv("INTEGRITY_POLICY_PATH", str(default_policy))),
            event_directory=Path(os.getenv("EVENT_STORE_PATH", "/data/events")),
            retention_hours=_bounded_int("EVENT_RETENTION_HOURS", 168, 1, 24 * 366),
            store_max_mb=_bounded_int("EVENT_STORE_MAX_MB", 128, 1, 4096),
            queue_maxsize=_bounded_int("SIDECAR_QUEUE_MAX", 4096, 32, 65536),
        )
