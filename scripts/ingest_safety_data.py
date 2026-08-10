#!/usr/bin/env python3
"""Compatibility entry point for versioned safety-source ingestion."""

from app.safety.ingestion.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
