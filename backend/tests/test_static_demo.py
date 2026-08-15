"""Source and fixture safeguards for the static portfolio mode."""

import json
from pathlib import Path


ROOT = Path(__file__).parents[2]
SOURCE = ROOT / "frontend/src/StaticEvidenceApp.tsx"
FIXTURE = ROOT / "frontend/src/fixtures/static-evidence-v1.json"


def test_static_source_has_permanent_banner_and_no_live_capabilities() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert source.count("RECORDED RESEARCH DEMO — NOT LIVE TRAFFIC") >= 2
    for forbidden in (
        "fetch(",
        "axios.create",
        "new WebSocket",
        "/api/",
        "<AuthProvider",
        "<LoginForm",
    ):
        assert forbidden not in source
    for required in ("Play", "Pause", "Reset", "Speed", "Scenario"):
        assert required in source


def test_fixture_has_required_scenarios_and_honest_blocked_results() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert fixture["schema_version"] == "1.0"
    assert {item["family"] for item in fixture["scenarios"]} == {
        "SYNTHETIC_CONTROL",
        "SYNTHETIC_ABRUPT",
        "SYNTHETIC_GRADUAL",
    }
    assert fixture["benchmark"]["status"] == "BLOCKED_CAPTURE_PENDING"
    assert fixture["benchmark"]["value"] is None
    assert fixture["public_candidate"]["outcome"] == "BLOCKED_REPLICATION"
    assert "synthetic substitute" in fixture["public_candidate"]["detail"]


def test_document_links_target_existing_repository_files() -> None:
    for path in (
        ROOT / "docs/FEEDER_SIDECAR.md",
        ROOT / "docs/BENCHMARK_METHODOLOGY.md",
        ROOT / "docs/DATA_MODEL_CARD.md",
        ROOT / "docs/PUBLIC_ANOMALY_REPLAY.md",
        ROOT / "evaluation/manifests/public-anomaly-sources-v1.json",
    ):
        assert path.is_file()
