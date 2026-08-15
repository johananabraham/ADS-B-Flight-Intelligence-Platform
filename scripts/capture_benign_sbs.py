#!/usr/bin/env python3
"""Capture a private, checksummed SBS day without publishing receiver metadata."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path


async def capture(host: str, port: int, duration_hours: float, output: Path) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    started = datetime.now(timezone.utc)
    deadline = asyncio.get_running_loop().time() + duration_hours * 3600
    digest = hashlib.sha256()
    line_count = 0
    outages: list[dict[str, str]] = []
    outage_started: datetime | None = None
    with output.open("xb") as handle:
        while asyncio.get_running_loop().time() < deadline:
            try:
                reader, writer = await asyncio.open_connection(host, port, limit=4097)
                if outage_started is not None:
                    outages.append(
                        {
                            "started_at": outage_started.isoformat(),
                            "ended_at": datetime.now(timezone.utc).isoformat(),
                            "reason": "SOURCE_OUTAGE",
                        }
                    )
                    outage_started = None
                try:
                    while asyncio.get_running_loop().time() < deadline:
                        line = await asyncio.wait_for(reader.readline(), timeout=30)
                        if not line:
                            break
                        handle.write(line)
                        digest.update(line)
                        line_count += 1
                        if line_count % 100 == 0:
                            handle.flush()
                            os.fsync(handle.fileno())
                finally:
                    writer.close()
                    await writer.wait_closed()
            except (OSError, asyncio.TimeoutError):
                outage_started = outage_started or datetime.now(timezone.utc)
                await asyncio.sleep(5)
        if outage_started is not None:
            outages.append(
                {
                    "started_at": outage_started.isoformat(),
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                    "reason": "SOURCE_OUTAGE",
                }
            )
        handle.flush()
        os.fsync(handle.fileno())
    return {
        "started_at": started.isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "sha256": digest.hexdigest(),
        "bytes": output.stat().st_size,
        "lines": line_count,
        "outages": outages,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", type=int, required=True, choices=range(1, 8))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=30003)
    parser.add_argument("--duration-hours", type=float, default=24)
    parser.add_argument("--output-root", type=Path, default=Path(".private/benign-capture-v1"))
    parser.add_argument("--receiver-configuration", required=True)
    args = parser.parse_args()
    if args.duration_hours <= 0 or not 1 <= args.port <= 65535:
        parser.error("duration and port must be positive and bounded")
    output = args.output_root / f"day-{args.day:02d}.sbs"
    result = asyncio.run(capture(args.host, args.port, args.duration_hours, output))
    manifest_path = args.output_root / "capture-manifest.private.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {
            "schema_version": "1.0",
            "software": {"python": platform.python_version(), "platform": platform.platform()},
            "receiver_configuration": args.receiver_configuration,
            "captures": [],
        }
    )
    manifest["captures"] = [item for item in manifest["captures"] if item["day"] != args.day]
    manifest["captures"].append(
        {"day": args.day, "path": output.name, "usable": False, **result}
    )
    manifest["captures"].sort(key=lambda item: item["day"])
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Private capture recorded at {output}; inspect it before marking usable=true.")


if __name__ == "__main__":
    main()
