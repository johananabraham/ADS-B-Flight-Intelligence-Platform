"""Resilient, privacy-preserving capture primitives for the benign field study."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import ipaddress
import json
import os
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


def atomic_private_json(path: Path, payload: dict[str, Any]) -> None:
    """Replace a private JSON file atomically with owner-only permissions."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            os.chmod(handle.name, 0o600)
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def allocate_output_path(output_root: Path, day: int) -> Path:
    """Return a new path without replacing an earlier capture attempt."""
    primary = output_root / f"day-{day:02d}.sbs"
    if not primary.exists():
        return primary
    attempt = 2
    while True:
        candidate = output_root / f"day-{day:02d}-attempt-{attempt:02d}.sbs"
        if not candidate.exists():
            return candidate
        attempt += 1


def validate_loopback_source(host: str) -> str:
    """Keep private RF collection attached to a host-local decoder."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("capture host must be a numeric loopback address") from exc
    if not address.is_loopback:
        raise ValueError("capture host must be loopback")
    return str(address)


async def preflight_source(host: str, port: int, timeout_seconds: float) -> None:
    """Prove that the source accepts a connection and emits an SBS record."""
    writer: asyncio.StreamWriter | None = None
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, limit=4097), timeout=timeout_seconds
        )
        line = await asyncio.wait_for(reader.readline(), timeout=timeout_seconds)
        if not line or len(line) > 4096 or not line.startswith(b"MSG,"):
            raise RuntimeError("source did not emit a bounded SBS MSG record")
    finally:
        if writer is not None:
            writer.close()
            with contextlib.suppress(OSError):
                await writer.wait_closed()


async def capture(
    host: str,
    port: int,
    duration_hours: float,
    output: Path,
    *,
    status_path: Path | None = None,
) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.parent.chmod(0o700)
    started = _now()
    loop = asyncio.get_running_loop()
    started_monotonic = loop.time()
    deadline = started_monotonic + duration_hours * 3600
    digest = hashlib.sha256()
    line_count = 0
    outages: list[dict[str, str]] = []
    outage_started: datetime | None = None
    connected_seconds = 0.0
    interrupted = False

    def write_status(state: str, source_connection: str) -> None:
        if status_path is None:
            return
        atomic_private_json(
            status_path,
            {
                "schema_version": "1.0",
                "state": state,
                "source_connection": source_connection,
                "day": int(output.name[4:6]),
                "capture_file": output.name,
                "elapsed_seconds": round(loop.time() - started_monotonic, 3),
                "bytes": output.stat().st_size if output.exists() else 0,
                "lines": line_count,
                "outage_count": len(outages) + int(outage_started is not None),
                "updated_at": _now().isoformat(),
                "privacy": "aggregate capture health only; no SBS content or receiver location",
            },
        )

    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        write_status("CAPTURING", "CONNECTING")
        try:
            while loop.time() < deadline:
                writer: asyncio.StreamWriter | None = None
                connection_started: float | None = None
                try:
                    reader, writer = await asyncio.open_connection(host, port, limit=4097)
                    connection_started = loop.time()
                    if outage_started is not None:
                        outages.append(
                            {
                                "started_at": outage_started.isoformat(),
                                "ended_at": _now().isoformat(),
                                "reason": "SOURCE_OUTAGE",
                            }
                        )
                        outage_started = None
                    write_status("CAPTURING", "CONNECTED")
                    while loop.time() < deadline:
                        line = await asyncio.wait_for(reader.readline(), timeout=30)
                        if not line:
                            break
                        handle.write(line)
                        digest.update(line)
                        line_count += 1
                        if line_count % 100 == 0:
                            handle.flush()
                            os.fsync(handle.fileno())
                            write_status("CAPTURING", "CONNECTED")
                except (OSError, asyncio.TimeoutError):
                    outage_started = outage_started or _now()
                    write_status("CAPTURING", "DISCONNECTED")
                    await asyncio.sleep(5)
                finally:
                    if connection_started is not None:
                        connected_seconds += max(0.0, loop.time() - connection_started)
                    if writer is not None:
                        writer.close()
                        with contextlib.suppress(OSError):
                            await writer.wait_closed()
        except asyncio.CancelledError:
            interrupted = True
        finally:
            if outage_started is not None:
                outages.append(
                    {
                        "started_at": outage_started.isoformat(),
                        "ended_at": _now().isoformat(),
                        "reason": "SOURCE_OUTAGE",
                    }
                )
            handle.flush()
            os.fsync(handle.fileno())

    elapsed_seconds = max(0.0, loop.time() - started_monotonic)
    result = {
        "started_at": started.isoformat(),
        "ended_at": _now().isoformat(),
        "sha256": digest.hexdigest(),
        "bytes": output.stat().st_size,
        "lines": line_count,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "connected_seconds": round(min(connected_seconds, elapsed_seconds), 3),
        "outage_seconds": round(max(0.0, elapsed_seconds - connected_seconds), 3),
        "outages": outages,
        "capture_state": "INTERRUPTED" if interrupted else "COMPLETED",
    }
    write_status(result["capture_state"], "DISCONNECTED")
    return result


def load_manifest(path: Path, receiver_configuration: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": "1.0",
            "software": {"python": platform.python_version(), "platform": platform.platform()},
            "receiver_configuration": receiver_configuration,
            "captures": [],
        }
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "1.0" or not isinstance(manifest.get("captures"), list):
        raise ValueError("existing capture manifest must use schema_version 1.0")
    if manifest.get("receiver_configuration") != receiver_configuration:
        raise ValueError("receiver configuration changed; use a separate output root")
    return manifest


def usable_captures_by_day(manifest: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Fail closed unless each usable day selects one completed attempt."""
    usable: dict[int, dict[str, Any]] = {}
    for capture_entry in manifest.get("captures", []):
        if not capture_entry.get("usable", False):
            continue
        day = int(capture_entry["day"])
        if day not in range(1, 8):
            raise ValueError(f"usable capture day {day} is outside 1-7")
        state = capture_entry.get("capture_state")
        if state is not None and state != "COMPLETED":
            raise ValueError(f"usable capture day {day} is not completed")
        if day in usable:
            raise ValueError(f"multiple usable capture attempts exist for day {day}")
        usable[day] = capture_entry
    return usable


def run_capture_cli() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", type=int, required=True, choices=range(1, 8))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=30003)
    parser.add_argument("--duration-hours", type=float, default=24)
    parser.add_argument("--preflight-timeout-seconds", type=float, default=30)
    parser.add_argument("--output-root", type=Path, default=Path(".private/benign-capture-v1"))
    parser.add_argument("--receiver-configuration", required=True)
    args = parser.parse_args()
    if args.duration_hours <= 0 or not 1 <= args.port <= 65535:
        parser.error("duration and port must be positive and bounded")
    if args.preflight_timeout_seconds <= 0:
        parser.error("preflight timeout must be positive")
    try:
        args.host = validate_loopback_source(args.host)
    except ValueError as exc:
        parser.error(str(exc))

    args.output_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest_path = args.output_root / "capture-manifest.private.json"
    try:
        manifest = load_manifest(manifest_path, args.receiver_configuration)
        asyncio.run(preflight_source(args.host, args.port, args.preflight_timeout_seconds))
    except (OSError, asyncio.TimeoutError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"capture preflight failed without creating a capture: {exc}\n")

    output = allocate_output_path(args.output_root, args.day)
    result = asyncio.run(
        capture(
            args.host,
            args.port,
            args.duration_hours,
            output,
            status_path=args.output_root / "capture-status.private.json",
        )
    )
    manifest["captures"].append(
        {
            "day": args.day,
            "path": output.name,
            "usable": False,
            "review_status": "MANUAL_REVIEW_REQUIRED",
            **result,
        }
    )
    manifest["captures"].sort(key=lambda item: (int(item["day"]), item["started_at"]))
    atomic_private_json(manifest_path, manifest)
    print(
        f"Private capture recorded at {output}; checksum and aggregate health are in "
        f"{manifest_path}. Manual review is required before usable=true."
    )
    if result["capture_state"] != "COMPLETED":
        raise SystemExit(130)
