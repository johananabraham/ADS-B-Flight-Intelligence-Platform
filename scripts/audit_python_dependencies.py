#!/usr/bin/env python3
"""Run pip-audit with narrow, version-bound, expiring exceptions."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence


PIN_PATTERN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s;]+)")


def requirement_pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = PIN_PATTERN.match(raw_line.strip())
        if match:
            pins[match.group(1).lower().replace("_", "-")] = match.group(2)
    return pins


def validated_exception_ids(
    policy: Mapping[str, Any], pins: Mapping[str, str], *, today: date | None = None
) -> list[str]:
    if policy.get("schema_version") != "1.0":
        raise ValueError("unsupported dependency-exception policy schema")
    current = today or date.today()
    result: list[str] = []
    for exception in policy.get("exceptions", []):
        package = str(exception.get("package", "")).lower().replace("_", "-")
        version = str(exception.get("version", ""))
        if pins.get(package) != version:
            raise ValueError(f"exception package pin does not match requirements: {package}")
        try:
            expiry = date.fromisoformat(str(exception.get("expires_on", "")))
        except ValueError as exc:
            raise ValueError(f"invalid exception expiry for {package}") from exc
        if expiry < current:
            raise ValueError(f"dependency exception expired for {package} on {expiry}")
        vulnerability_ids = exception.get("vulnerability_ids")
        if not isinstance(vulnerability_ids, list) or not vulnerability_ids:
            raise ValueError(f"dependency exception has no vulnerability IDs: {package}")
        for vulnerability_id in vulnerability_ids:
            value = str(vulnerability_id)
            if not re.fullmatch(r"(?:CVE-\d{4}-\d{4,}|GHSA-[a-z0-9-]+|PYSEC-[A-Za-z0-9-]+)", value):
                raise ValueError(f"invalid vulnerability ID in exception for {package}")
            result.append(value)
    if len(result) != len(set(result)):
        raise ValueError("duplicate vulnerability ID in dependency exceptions")
    return sorted(result)


def build_audit_command(requirements: Path, exception_ids: Sequence[str]) -> list[str]:
    command = [sys.executable, "-m", "pip_audit", "-r", str(requirements)]
    for vulnerability_id in exception_ids:
        command.extend(("--ignore-vuln", vulnerability_id))
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--exceptions", type=Path)
    args = parser.parse_args()
    try:
        exception_ids: list[str] = []
        if args.exceptions:
            policy = json.loads(args.exceptions.read_text(encoding="utf-8"))
            if not isinstance(policy, dict):
                raise ValueError("dependency-exception policy must be an object")
            exception_ids = validated_exception_ids(
                policy,
                requirement_pins(args.requirements),
            )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.exit(1, f"dependency exception validation failed: {exc}\n")
    completed = subprocess.run(  # noqa: S603 - fixed interpreter/module and validated args
        build_audit_command(args.requirements, exception_ids),
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
