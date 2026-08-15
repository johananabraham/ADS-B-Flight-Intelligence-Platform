#!/usr/bin/env python3
"""Fail-closed verification for the network-free static evidence build."""

import argparse
import json
import re
from pathlib import Path


BANNER = "RECORDED RESEARCH DEMO — NOT LIVE TRAFFIC"
FORBIDDEN_RUNTIME_PATTERNS = {
    "API path": re.compile(r"/api/v1"),
    "local backend": re.compile(r"localhost:8000"),
    "WebSocket client": re.compile(r"new WebSocket|WebSocket\("),
    "fetch call": re.compile(r"\bfetch\("),
    "Axios client": re.compile(r"\baxios\b", re.IGNORECASE),
    "live map tiles": re.compile(r"tiles\.stadiamaps\.com"),
}


def verify(dist: Path, fixture_path: Path) -> dict[str, int | str]:
    if not (dist / "index.html").is_file():
        raise ValueError("static build index.html is missing")
    files = sorted(path for path in dist.rglob("*") if path.is_file())
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in files
        if path.suffix in {".html", ".js", ".css", ".json"}
    )
    if BANNER not in text:
        raise ValueError("permanent recorded-demo banner is missing")
    for label, pattern in FORBIDDEN_RUNTIME_PATTERNS.items():
        if pattern.search(text):
            raise ValueError(f"static bundle contains forbidden {label}")
    html = (dist / "index.html").read_text(encoding="utf-8")
    if re.search(r"<(?:script|link)[^>]+(?:src|href)=[\"']https?://", html):
        raise ValueError("static HTML loads an external script or stylesheet")
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    if fixture.get("schema_version") != "1.0":
        raise ValueError("fixture schema version is unsupported")
    families = {item["family"] for item in fixture["scenarios"]}
    if families != {"SYNTHETIC_CONTROL", "SYNTHETIC_ABRUPT", "SYNTHETIC_GRADUAL"}:
        raise ValueError("fixture scenario-family coverage is incomplete")
    if fixture["benchmark"]["status"] == "BLOCKED_CAPTURE_PENDING" and fixture["benchmark"]["value"] is not None:
        raise ValueError("a blocked physical benchmark cannot publish a numeric rate")
    if fixture["public_candidate"]["outcome"] not in {
        "DETECTED",
        "MISSED",
        "INSUFFICIENT_DATA",
        "BLOCKED_REPLICATION",
    }:
        raise ValueError("public candidate outcome is invalid")
    return {"schema_version": "1.0", "files_checked": len(files), "scenarios": len(fixture["scenarios"])}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=Path("frontend/dist"))
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("frontend/src/fixtures/static-evidence-v1.json"),
    )
    args = parser.parse_args()
    print(json.dumps(verify(args.dist, args.fixture), sort_keys=True))


if __name__ == "__main__":
    main()
