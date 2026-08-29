from datetime import date
from pathlib import Path

import pytest

from scripts.audit_python_dependencies import (
    build_audit_command,
    requirement_pins,
    validated_exception_ids,
)


ROOT = Path(__file__).resolve().parents[2]


def policy() -> dict:
    import json

    return json.loads((ROOT / "security/pip-audit-exceptions.json").read_text())


def test_dependency_exception_matches_exact_backend_pin_and_is_not_expired() -> None:
    pins = requirement_pins(ROOT / "backend/requirements.txt")
    assert validated_exception_ids(
        policy(), pins, today=date(2026, 8, 29)
    ) == ["CVE-2026-45830", "CVE-2026-45833"]


def test_dependency_exception_fails_closed_after_expiry_or_pin_change() -> None:
    pins = requirement_pins(ROOT / "backend/requirements.txt")
    with pytest.raises(ValueError, match="expired"):
        validated_exception_ids(policy(), pins, today=date(2026, 10, 1))
    with pytest.raises(ValueError, match="pin"):
        validated_exception_ids(policy(), {**pins, "chromadb": "1.0.0"})


def test_audit_command_passes_only_validated_specific_ids() -> None:
    command = build_audit_command(
        Path("backend/requirements.txt"),
        ["CVE-2026-45830", "CVE-2026-45833"],
    )
    assert command.count("--ignore-vuln") == 2
    assert "CVE-2026-45830" in command
    assert "CVE-2026-45833" in command


def test_chroma_remains_embedded_and_reset_is_disabled() -> None:
    source = (ROOT / "backend/app/core/vectorstore.py").read_text()
    compose = "\n".join(path.read_text() for path in ROOT.glob("docker-compose*.yml"))
    assert "allow_reset=False" in source
    assert "chromadb.HttpClient" not in source
    assert "chroma:" not in compose
