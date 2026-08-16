"""Regression tests for lightweight schema consumers such as the feeder sidecar."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def test_observation_schema_import_does_not_require_sqlalchemy() -> None:
    """The standalone sidecar must not inherit backend ORM dependencies."""
    repository_root = Path(__file__).resolve().parents[2]
    python_path = os.pathsep.join(
        [
            str(repository_root / "backend"),
            str(repository_root),
            os.environ.get("PYTHONPATH", ""),
        ]
    )
    code = """
import builtins

real_import = builtins.__import__

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "sqlalchemy" or name.startswith("sqlalchemy."):
        raise AssertionError("observation schema unexpectedly imported SQLAlchemy")
    return real_import(name, globals, locals, fromlist, level)

builtins.__import__ = guarded_import
from app.schemas.observation import TrackObservation
assert TrackObservation.__name__ == "TrackObservation"
"""

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repository_root,
        env={**os.environ, "PYTHONPATH": python_path},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
