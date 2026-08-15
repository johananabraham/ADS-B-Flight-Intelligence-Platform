#!/usr/bin/env python3
"""Validate and ingest official NTSB CAROL exports or dated eCFR parts."""

from app.safety.ingestion.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
