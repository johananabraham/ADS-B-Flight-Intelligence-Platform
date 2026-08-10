#!/usr/bin/env python3
"""Validate and ingest official NTSB CAROL exports or dated eCFR parts."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from app.core.database import SessionLocal
from app.safety.ingestion import (
    fetch_ecfr_part,
    load_ntsb_carol_export,
    parse_ecfr_part_xml,
    parse_ntsb_carol_json,
    persist_ecfr_source,
    persist_ntsb_source,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    subparsers = parser.add_subparsers(dest="source", required=True)

    ntsb = subparsers.add_parser("ntsb-json", help="ingest a CAROL JSON export")
    ntsb.add_argument("--input", type=Path, required=True)
    ntsb.add_argument("--source-uri")

    ecfr = subparsers.add_parser("ecfr", help="fetch and ingest a dated 14 CFR part")
    ecfr.add_argument("--part", type=int, required=True)
    ecfr.add_argument("--effective-date", type=date.fromisoformat, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.source == "ntsb-json":
        parsed = parse_ntsb_carol_json(
            load_ntsb_carol_export(args.input, source_uri=args.source_uri)
        )
        persist = persist_ntsb_source
    else:
        parsed = parse_ecfr_part_xml(fetch_ecfr_part(args.part, args.effective_date))
        persist = persist_ecfr_source

    payload = {"validation": parsed.report.model_dump(mode="json")}
    if not args.validate_only:
        with SessionLocal.begin() as db:
            payload["database"] = asdict(persist(db, parsed))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
