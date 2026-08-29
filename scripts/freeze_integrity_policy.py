#!/usr/bin/env python3
"""Freeze the policy after usable days 1-6 and before viewing day 7."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from evaluation.field.capture import usable_captures_by_day


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-manifest", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.capture_manifest.read_text(encoding="utf-8"))
    try:
        usable = usable_captures_by_day(manifest)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not set(range(1, 7)) <= set(usable):
        raise SystemExit("days 1-6 must be captured, inspected, and marked usable before freeze")
    if manifest.get("day_7_results_viewed", False):
        raise SystemExit("refusing to freeze after day 7 results were viewed")
    for day, item in usable.items():
        if day not in range(1, 7):
            continue
        capture_path = Path(item["path"])
        if not capture_path.is_absolute():
            capture_path = args.capture_manifest.parent / capture_path
        if not item.get("sha256") or sha256(capture_path) != item["sha256"]:
            raise SystemExit(f"capture checksum mismatch for day {day}")
    digest = sha256(args.policy)
    payload = {
        "schema_version": "1.0",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "policy_sha256": digest,
        "development_days": [1, 2, 3, 4],
        "validation_days": [5, 6],
        "holdout_day": 7,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(digest)


if __name__ == "__main__":
    main()
