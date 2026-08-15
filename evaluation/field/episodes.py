"""Deterministic routine-traffic episode and promotion-gate reporting."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


VALID_DISPOSITIONS = {
    "EXPECTED_MANEUVER_OR_DATA_ARTIFACT",
    "RECEIVER_OR_PIPELINE_ISSUE",
    "UNEXPLAINED",
    "INSUFFICIENT_CONTEXT",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _episodes(rows: list[dict[str, Any]], cooldown_seconds: float) -> list[dict[str, Any]]:
    questionable: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["policy_state"] == "QUESTIONABLE":
            questionable[(row["split"], row["public_track_id"])].append(row)
    episodes: list[dict[str, Any]] = []
    for (split, track_id), items in sorted(questionable.items()):
        current: list[dict[str, Any]] = []
        for item in sorted(items, key=lambda value: value["elapsed_seconds"]):
            if current and item["elapsed_seconds"] - current[-1]["elapsed_seconds"] >= cooldown_seconds:
                episodes.append(_episode(split, track_id, current))
                current = []
            current.append(item)
        if current:
            episodes.append(_episode(split, track_id, current))
    return episodes


def _episode(split: str, track_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    kinds = sorted({kind for item in items for kind in item["evidence_kinds"]})
    identity = json.dumps(
        [split, track_id, items[0]["elapsed_seconds"], items[-1]["elapsed_seconds"], kinds],
        separators=(",", ":"),
    )
    return {
        "episode_id": hashlib.sha256(identity.encode()).hexdigest()[:24],
        "split": split,
        "public_track_id": track_id,
        "start_seconds": items[0]["elapsed_seconds"],
        "end_seconds": items[-1]["elapsed_seconds"],
        "evidence_kinds": kinds,
    }


def build_report(
    export_path: str | Path,
    policy_path: str | Path,
    freeze_manifest_path: str | Path,
    *,
    reviews_path: str | Path | None = None,
    synthetic_results_path: str | Path | None = None,
    cooldown_seconds: float = 60,
) -> dict[str, Any]:
    export = Path(export_path)
    policy = Path(policy_path)
    freeze = json.loads(Path(freeze_manifest_path).read_text(encoding="utf-8"))
    if freeze.get("policy_sha256") != _sha256(policy):
        raise ValueError("frozen policy checksum does not match the evaluated policy")
    rows = [json.loads(line) for line in export.read_text(encoding="utf-8").splitlines()]
    public_manifest_path = export.with_suffix(".manifest.json")
    public_manifest = (
        json.loads(public_manifest_path.read_text(encoding="utf-8"))
        if public_manifest_path.exists()
        else {"sessions": []}
    )
    if public_manifest.get("feature_sha256") not in (None, _sha256(export)):
        raise ValueError("public feature manifest checksum does not match the export")
    episodes = _episodes(rows, cooldown_seconds)
    reviews: dict[str, str] = {}
    if reviews_path:
        review_payload = json.loads(Path(reviews_path).read_text(encoding="utf-8"))
        reviews = {item["episode_id"]: item["disposition"] for item in review_payload["reviews"]}
        invalid = set(reviews.values()) - VALID_DISPOSITIONS
        if invalid:
            raise ValueError(f"invalid reviewer dispositions: {sorted(invalid)}")
    for episode in episodes:
        episode["reviewer_disposition"] = reviews.get(episode["episode_id"], "UNREVIEWED")

    tracks: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        tracks[(row["split"], row["public_track_id"])].append(row["elapsed_seconds"])
    split_metrics: dict[str, dict[str, Any]] = {}
    for split in ("development", "validation", "holdout"):
        split_tracks = {key: values for key, values in tracks.items() if key[0] == split}
        track_hours = sum(max(values) - min(values) for values in split_tracks.values()) / 3600
        split_episodes = [item for item in episodes if item["split"] == split]
        split_metrics[split] = {
            "tracks": len(split_tracks),
            "track_hours": round(track_hours, 6),
            "episodes": len(split_episodes),
            "reviewed_episodes": sum(
                item["reviewer_disposition"] != "UNREVIEWED" for item in split_episodes
            ),
            "reviewed_routine_traffic_integrity_alerts_per_track_hour": (
                round(len(split_episodes) / track_hours, 6) if track_hours else None
            ),
        }
    synthetic = None
    if synthetic_results_path:
        synthetic = json.loads(Path(synthetic_results_path).read_text(encoding="utf-8"))
    holdout = split_metrics["holdout"]
    holdout_complete = bool(holdout["tracks"] and holdout["track_hours"])
    all_holdout_reviewed = holdout["episodes"] == holdout["reviewed_episodes"]
    rate_passed = bool(
        holdout_complete
        and holdout["reviewed_routine_traffic_integrity_alerts_per_track_hour"] <= 0.1
    )
    synthetic_passed = bool(
        synthetic
        and synthetic.get("abrupt_targeted_recall", 0) >= 0.95
        and synthetic.get("gradual_targeted_recall", 0) >= 0.95
    )
    passed = holdout_complete and all_holdout_reviewed and rate_passed and synthetic_passed
    return {
        "schema_version": "1.0",
        "status": "PASSED" if passed else ("BLOCKED_CAPTURE_PENDING" if not holdout_complete else "GATE_NOT_MET"),
        "metric_name": "reviewed routine-traffic integrity-alert rate",
        "policy_sha256": freeze["policy_sha256"],
        "export_sha256": _sha256(export),
        "cooldown_seconds": cooldown_seconds,
        "usable_duration_seconds": sum(
            item.get("usable_duration_seconds", 0) for item in public_manifest["sessions"]
        ),
        "excluded_intervals": [
            {"public_session_id": item["public_session_id"], **interval}
            for item in public_manifest["sessions"]
            for interval in item.get("excluded_intervals", [])
        ],
        "splits": split_metrics,
        "episodes": episodes,
        "synthetic": synthetic,
        "gate": {
            "holdout_complete": holdout_complete,
            "all_holdout_episodes_reviewed": all_holdout_reviewed,
            "holdout_rate_at_most_0_1": rate_passed,
            "synthetic_abrupt_and_gradual_recall_at_least_0_95": synthetic_passed,
            "passed": passed,
        },
    }
