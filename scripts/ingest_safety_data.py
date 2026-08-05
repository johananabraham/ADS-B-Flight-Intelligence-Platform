#!/usr/bin/env python3
"""Ingest NTSB and eCFR data into PostgreSQL and ChromaDB.

Usage:
    PYTHONPATH=backend:. python scripts/ingest_safety_data.py
    PYTHONPATH=backend:. python scripts/ingest_safety_data.py --ntsb-only
    PYTHONPATH=backend:. python scripts/ingest_safety_data.py --ecfr-only
    PYTHONPATH=backend:. python scripts/ingest_safety_data.py --status
"""

import argparse
import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest safety research data")
    parser.add_argument(
        "--ntsb-only",
        action="store_true",
        help="Only ingest NTSB data",
    )
    parser.add_argument(
        "--ecfr-only",
        action="store_true",
        help="Only ingest eCFR data",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current ingestion status",
    )
    parser.add_argument(
        "--ntsb-url",
        type=str,
        help="Override NTSB data URL",
    )
    parser.add_argument(
        "--ecfr-parts",
        type=str,
        default="61,91,121,135",
        help="Comma-separated CFR parts to ingest",
    )
    args = parser.parse_args()

    # Import after argparse
    from app.safety.ingestion import (
        get_ingestion_status,
        ingest_all,
        ingest_ecfr_data,
        ingest_ntsb_data,
    )

    if args.status:
        status = get_ingestion_status()
        print(json.dumps(status, indent=2, default=str))
        return 0

    ecfr_parts = [int(p.strip()) for p in args.ecfr_parts.split(",")]

    if args.ntsb_only:
        print("Ingesting NTSB data...")
        manifest = ingest_ntsb_data(url=args.ntsb_url)
        print(f"NTSB: {manifest.record_count} records, {manifest.vector_count} vectors")
        if manifest.errors:
            print(f"Errors: {manifest.errors}")
        return 0 if not manifest.errors else 1

    if args.ecfr_only:
        print(f"Ingesting eCFR Parts {ecfr_parts}...")
        manifest = ingest_ecfr_data(parts=ecfr_parts)
        print(f"eCFR: {manifest.record_count} records, {manifest.vector_count} vectors")
        if manifest.errors:
            print(f"Errors: {manifest.errors}")
        return 0 if not manifest.errors else 1

    # Full ingestion
    print("Running full safety data ingestion...")
    print("=" * 60)

    manifests = ingest_all(ntsb_url=args.ntsb_url, ecfr_parts=ecfr_parts)

    total_errors = 0
    for source_type, manifest in manifests.items():
        print(f"\n{source_type.upper()}:")
        print(f"  Records: {manifest.record_count}")
        print(f"  Vectors: {manifest.vector_count}")
        print(f"  Hash:    {manifest.source_hash[:16]}...")
        if manifest.errors:
            print(f"  Errors:  {len(manifest.errors)}")
            for err in manifest.errors[:5]:
                print(f"    - {err}")
            total_errors += len(manifest.errors)

    print("\n" + "=" * 60)
    print(f"Ingestion complete. Total errors: {total_errors}")

    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
