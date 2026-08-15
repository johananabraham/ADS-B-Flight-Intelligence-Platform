"""Strict versioned integrity-policy loading."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from app.services.kinematics import KinematicPolicy
from app.services.windowed_kinematics import WindowPolicy


class PolicyError(ValueError):
    """Raised when a policy cannot be safely interpreted."""


@dataclass(frozen=True)
class TimingPolicy:
    maximum_reordering_seconds: float = 2.0
    maximum_latency_seconds: float = 10.0
    gap_seconds: float = 30.0
    evidence_ttl_seconds: float = 60.0


@dataclass(frozen=True)
class RuntimePolicy:
    minimum_observations: int = 2
    maximum_tracks: int = 2048
    maximum_observations_per_track: int = 64
    inactive_track_seconds: float = 600.0


@dataclass(frozen=True)
class IntegrityPolicy:
    schema_version: str = "1.0"
    policy_version: str = "1.0-development"
    timing: TimingPolicy = TimingPolicy()
    pair: KinematicPolicy = KinematicPolicy()
    window: WindowPolicy = WindowPolicy()
    runtime: RuntimePolicy = RuntimePolicy()

    def canonical_bytes(self) -> bytes:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()


def _strict_dataclass(cls: type, payload: Any, section: str):
    if not isinstance(payload, dict):
        raise PolicyError(f"{section} must be an object")
    allowed = {item.name for item in fields(cls)}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise PolicyError(f"unknown {section} fields: {', '.join(unknown)}")
    try:
        return cls(**payload)
    except (TypeError, ValueError) as exc:
        raise PolicyError(f"invalid {section}: {exc}") from exc


def policy_from_dict(payload: dict[str, Any]) -> IntegrityPolicy:
    allowed = {"schema_version", "policy_version", "timing", "pair", "window", "runtime"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise PolicyError(f"unknown policy fields: {', '.join(unknown)}")
    if payload.get("schema_version") != "1.0":
        raise PolicyError("only integrity policy schema_version 1.0 is supported")
    version = payload.get("policy_version")
    if not isinstance(version, str) or not version.strip():
        raise PolicyError("policy_version must be a non-empty string")
    policy = IntegrityPolicy(
        schema_version="1.0",
        policy_version=version,
        timing=_strict_dataclass(TimingPolicy, payload.get("timing", {}), "timing"),
        pair=_strict_dataclass(KinematicPolicy, payload.get("pair", {}), "pair"),
        window=_strict_dataclass(WindowPolicy, payload.get("window", {}), "window"),
        runtime=_strict_dataclass(RuntimePolicy, payload.get("runtime", {}), "runtime"),
    )
    if policy.runtime.minimum_observations < 2:
        raise PolicyError("runtime.minimum_observations must be at least 2")
    if policy.runtime.maximum_tracks < 1 or policy.runtime.maximum_observations_per_track < 2:
        raise PolicyError("runtime cache bounds must be positive")
    if min(asdict(policy.timing).values()) < 0:
        raise PolicyError("timing values cannot be negative")
    return policy


def load_policy(path: str | Path) -> IntegrityPolicy:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyError(f"unable to load policy: {exc}") from exc
    if not isinstance(payload, dict):
        raise PolicyError("policy root must be an object")
    return policy_from_dict(payload)
