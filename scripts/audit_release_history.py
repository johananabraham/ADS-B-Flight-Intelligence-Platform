#!/usr/bin/env python3
"""Reject private or restricted artifacts anywhere in reachable Git history."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import PurePosixPath


FORBIDDEN_SUFFIXES = {
    ".db",
    ".dump",
    ".pcap",
    ".pcapng",
    ".sbs",
    ".sqlite",
    ".sqlite3",
}
FORBIDDEN_PARTS = {".private", "private-captures", "secrets"}
FORBIDDEN_PATTERNS = (
    re.compile(r"(^|/)calibration/local(/|$)"),
    re.compile(r"(^|/)(receiver[-_.]?location|private[-_.]?salt)(/|$)", re.I),
)
ALLOWED_EXAMPLE_SUFFIXES = (".example", ".sample")
ALLOWED_PATHS = {"edge/mosquitto/secrets/README.md"}


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], check=True, text=True, capture_output=True
    )
    return result.stdout


def forbidden_reason(path_text: str) -> str | None:
    path = PurePosixPath(path_text)
    lowered_parts = {part.lower() for part in path.parts}
    if path_text in ALLOWED_PATHS:
        return None
    if path_text.endswith(ALLOWED_EXAMPLE_SUFFIXES):
        return None
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        return f"restricted extension {path.suffix.lower()}"
    overlap = lowered_parts & FORBIDDEN_PARTS
    if overlap:
        return f"restricted path component {sorted(overlap)[0]}"
    if any(pattern.search(path_text) for pattern in FORBIDDEN_PATTERNS):
        return "private receiver metadata path"
    return None


def main() -> int:
    violations: dict[str, str] = {}
    commits = git("rev-list", "--all").splitlines()
    if not commits:
        print("release-history audit: no commits found", file=sys.stderr)
        return 2

    paths = git("log", "--all", "--pretty=format:", "--name-only").splitlines()
    for raw_path in paths:
        path = raw_path.strip()
        if not path:
            continue
        reason = forbidden_reason(path)
        if reason:
            violations[path] = reason

    if violations:
        print("release-history audit failed:", file=sys.stderr)
        for path, reason in sorted(violations.items()):
            print(f"  {path}: {reason}", file=sys.stderr)
        return 1

    print(
        "release-history audit passed: "
        f"{len(commits)} reachable commits; no restricted artifact paths"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
