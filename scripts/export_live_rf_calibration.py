#!/usr/bin/env python3
"""Export a bounded LIVE_RF observation set for offline calibration review."""

from __future__ import annotations

import argparse
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.evaluation.calibration import (
    CalibrationManifest,
    DatasetClass,
    ReviewStatus,
)
from app.models.observation import TrackObservationRecord
from app.schemas.observation import ObservationSourceType
from app.schemas.observation import TrackObservation
from app.services.kinematic_persistence import record_to_observation


def timezone_aware_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--receiver-id", required=True)
    parser.add_argument("--from", dest="captured_from", type=timezone_aware_timestamp, required=True)
    parser.add_argument("--to", dest="captured_to", type=timezone_aware_timestamp, required=True)
    parser.add_argument("--license-id", required=True)
    parser.add_argument("--attribution", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    if args.captured_to < args.captured_from:
        parser.error("--to must not precede --from")
    return args


def write_dataset(
    observations: Iterable[TrackObservation], args: argparse.Namespace
) -> tuple[Path, Path, int]:
    output_directory = args.output_directory
    output_directory.mkdir(parents=True, exist_ok=True)
    observations_path = output_directory / "observations.jsonl"
    manifest_path = output_directory / "manifest.json"
    observations_temporary = output_directory / ".observations.jsonl.tmp"
    manifest_temporary = output_directory / ".manifest.json.tmp"
    targets = (
        observations_path,
        manifest_path,
        observations_temporary,
        manifest_temporary,
    )
    if any(path.exists() for path in targets):
        raise FileExistsError(
            "output dataset already exists; choose an empty directory to preserve evidence"
        )

    digest = hashlib.sha256()
    count = 0
    first_observed_at = None
    last_observed_at = None
    try:
        with observations_temporary.open("x", encoding="utf-8") as output:
            for observation in observations:
                provenance = observation.provenance
                if (
                    provenance.source_type is not ObservationSourceType.LIVE_RF
                    or provenance.source_id != args.source_id
                    or provenance.receiver_id != args.receiver_id
                ):
                    raise ValueError(
                        "every exported observation must match the requested LIVE_RF source"
                    )
                line = observation.model_dump_json() + "\n"
                output.write(line)
                digest.update(line.encode("utf-8"))
                count += 1
                first_observed_at = first_observed_at or observation.observed_at
                last_observed_at = observation.observed_at
        if count == 0 or first_observed_at is None or last_observed_at is None:
            raise ValueError("no matching LIVE_RF observations were found")
        manifest = CalibrationManifest(
            dataset_id=args.dataset_id,
            dataset_class=DatasetClass.CAPTURED_RF,
            review_status=ReviewStatus.UNREVIEWED,
            source_type=ObservationSourceType.LIVE_RF,
            source_id=args.source_id,
            receiver_id=args.receiver_id,
            license_id=args.license_id,
            attribution=args.attribution,
            captured_from=first_observed_at,
            captured_to=last_observed_at,
            observation_count=count,
            observations_sha256=digest.hexdigest(),
        )
        manifest_temporary.write_text(
            manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        observations_temporary.replace(observations_path)
        manifest_temporary.replace(manifest_path)
    except Exception:
        observations_temporary.unlink(missing_ok=True)
        manifest_temporary.unlink(missing_ok=True)
        raise
    return manifest_path, observations_path, count


def export_dataset(args: argparse.Namespace) -> tuple[Path, Path, int]:
    engine = create_engine(args.database_url)
    try:
        with Session(engine) as session:
            records = (
                session.query(TrackObservationRecord)
                .filter(
                    TrackObservationRecord.source_type
                    == ObservationSourceType.LIVE_RF.value,
                    TrackObservationRecord.source_id == args.source_id,
                    TrackObservationRecord.receiver_id == args.receiver_id,
                    TrackObservationRecord.observed_at >= args.captured_from,
                    TrackObservationRecord.observed_at <= args.captured_to,
                )
                .order_by(
                    TrackObservationRecord.observed_at.asc(),
                    TrackObservationRecord.observation_id.asc(),
                )
                .yield_per(1_000)
            )
            observations = (record_to_observation(record) for record in records)
            return write_dataset(observations, args)
    finally:
        engine.dispose()


def main() -> None:
    args = parse_args()
    manifest_path, observations_path, count = export_dataset(args)
    print(f"Exported {count} immutable LIVE_RF observations")
    print(f"Manifest: {manifest_path}")
    print(f"Observations: {observations_path}")
    print("Review the capture before changing review_status; do not call this a false-positive rate.")


if __name__ == "__main__":
    main()
