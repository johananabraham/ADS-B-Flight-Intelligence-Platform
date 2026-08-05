#!/usr/bin/env python3
"""Verify the intentionally impossible replay produces exact rule evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import time

from verify_demo import fetch_json


EXPECTED_RULES = {
    "IMPLIED_GROUND_SPEED",
    "REPORTED_ACCELERATION",
    "TURN_RATE",
    "DERIVED_VERTICAL_RATE",
    "SPEED_DISAGREEMENT",
}


def query_database(container: str) -> dict[str, object]:
    sql = """
    SELECT json_build_object(
      'observations', (
        SELECT COUNT(*) FROM track_observations
        WHERE recording_id = 'kinematic-attack-generated-v2'
      ),
      'evaluations', (
        SELECT COUNT(*) FROM kinematic_evaluations
        WHERE source_id = 'kinematic-attack-fixture-v2'
      ),
      'flagged', (
        SELECT COUNT(*) FROM kinematic_evaluations
        WHERE source_id = 'kinematic-attack-fixture-v2' AND status = 'FLAGGED'
      ),
      'rules', (
        SELECT rule_results FROM kinematic_evaluations
        WHERE source_id = 'kinematic-attack-fixture-v2' AND status = 'FLAGGED'
        ORDER BY evaluated_at DESC LIMIT 1
      ),
      'alerts', (
        SELECT COUNT(*) FROM anomalies
        WHERE anomaly_type = 'KINEMATIC_PLAUSIBILITY'
          AND details->>'source_id' = 'kinematic-attack-fixture-v2'
      )
    )
    """
    result = subprocess.run(
        [
            "docker",
            "exec",
            container,
            "psql",
            "-U",
            "postgres",
            "-d",
            "adsb_intel",
            "-tAc",
            sql,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout.strip())


def verify_once(frontend_url: str, database_container: str) -> dict[str, object]:
    evaluations = fetch_json(
        f"{frontend_url}/api/v1/kinematics/evaluations"
        "?icao_hex=A0B0C0&status=FLAGGED&source_id=kinematic-attack-fixture-v2"
    )
    if not isinstance(evaluations, list) or len(evaluations) != 1:
        raise RuntimeError("expected one flagged API evaluation")

    evidence = query_database(database_container)
    if evidence["observations"] != 2:
        raise RuntimeError(f"expected two source observations: {evidence}")
    if evidence["evaluations"] != 1 or evidence["flagged"] != 1:
        raise RuntimeError(f"expected one flagged evaluation: {evidence}")
    if evidence["alerts"] != 1:
        raise RuntimeError(f"expected one idempotent operator alert: {evidence}")

    rules = evidence["rules"]
    actual_rules = {
        rule["rule"] for rule in rules if rule.get("status") == "FLAGGED"
    }
    if actual_rules != EXPECTED_RULES:
        raise RuntimeError(f"unexpected failed rules: {sorted(actual_rules)}")

    return {
        "status": "passed",
        "recording_id": "kinematic-attack-generated-v2",
        "observations": evidence["observations"],
        "evaluations": evidence["evaluations"],
        "alerts": evidence["alerts"],
        "failed_rules": sorted(actual_rules),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-url", default="http://127.0.0.1:5173")
    parser.add_argument("--database-container", default="adsb-postgres")
    parser.add_argument("--timeout", type=float, default=60)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    deadline = time.monotonic() + args.timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            evidence = verify_once(args.frontend_url.rstrip("/"), args.database_container)
            print(json.dumps(evidence, indent=2))
            return 0
        except Exception as error:  # Poll startup and ingestion dependencies.
            last_error = error
            time.sleep(2)
    print(json.dumps({"status": "failed", "error": str(last_error)}, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
