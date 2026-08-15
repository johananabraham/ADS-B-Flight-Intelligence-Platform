"""Machine-readable safety evidence artifact contract tests."""

import json
import re
from pathlib import Path


EVIDENCE_PATH = Path("evaluation/results/ecfr_four_part_ingestion_proof_v1.json")


def test_four_part_ecfr_proof_has_exact_lineage_and_consistency_counts():
    evidence = json.loads(EVIDENCE_PATH.read_text())
    parts = evidence["parts"]

    assert evidence["evidence_class"] == "EXECUTED_ISOLATED_PIPELINE_PROOF"
    assert evidence["effective_date"] == "2026-07-24"
    assert [part["part"] for part in parts] == [61, 91, 121, 135]
    assert sum(part["parsed_sections"] for part in parts) == 1025
    assert all(part["rejected_sections"] == 0 for part in parts)
    assert all(part["duplicate_identifiers"] == 0 for part in parts)
    assert all(part["idempotent_rerun_applied"] is False for part in parts)
    assert all(re.fullmatch(r"[0-9a-f]{64}", part["source_sha256"]) for part in parts)

    consistency = evidence["corpus_consistency"]
    assert consistency["regulation_sql_rows"] == 1025
    assert consistency["regulation_vector_documents"] == 1025
    assert consistency["missing_documents"] == 0
    assert consistency["orphan_documents"] == 0
    assert consistency["lineage_mismatches"] == 0
    assert consistency["unversioned_sql_rows"] == 0
    assert consistency["second_check_passed"] is True
