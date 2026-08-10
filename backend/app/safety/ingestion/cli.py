"""Command-line interface for validated, versioned safety-source ingestion."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Sequence

from ...core.database import SessionLocal
from .ecfr import fetch_ecfr_part, parse_ecfr_part_xml
from .ntsb import load_ntsb_carol_export, parse_ntsb_carol_json
from .persistence import persist_ecfr_source, persist_ntsb_source
from .status import get_ingestion_status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    subparsers = parser.add_subparsers(dest="source", required=True)

    ntsb = subparsers.add_parser("ntsb-json", help="ingest a CAROL JSON export")
    ntsb.add_argument("--input", type=Path, required=True)
    ntsb.add_argument("--source-uri")

    ecfr = subparsers.add_parser("ecfr", help="fetch and ingest a dated 14 CFR part")
    ecfr.add_argument("--part", type=int, required=True)
    ecfr.add_argument("--effective-date", type=date.fromisoformat, required=True)

    subparsers.add_parser("status", help="show versioned ingestion status")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.source == "status":
        print(json.dumps(get_ingestion_status(), indent=2, default=str))
        return 0
    if args.report is None:
        raise SystemExit("--report is required for ingestion and validation")

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
