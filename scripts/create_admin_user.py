#!/usr/bin/env python3
"""Compatibility entry point for explicit administrator bootstrap."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.auth.bootstrap import create_admin, main  # noqa: E402


__all__ = ["create_admin", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
