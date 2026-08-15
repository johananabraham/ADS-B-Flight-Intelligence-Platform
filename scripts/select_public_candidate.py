#!/usr/bin/env python3
"""Stream pinned archives and freeze the first qualifying public candidate."""

import argparse
import csv
import json
import zipfile
from pathlib import Path

from evaluation.public_replay.manifest import checksum, validate_sources
from evaluation.public_replay.selection import select_candidate


def csv_rows(archive: Path, expected_name: str):
    with zipfile.ZipFile(archive) as bundle:
        members = [name for name in bundle.namelist() if Path(name).name == expected_name]
        if len(members) != 1:
            raise ValueError(f"archive must contain exactly one {expected_name}")
        with bundle.open(members[0]) as raw:
            import io

            yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))


def load_traces(directory: Path) -> dict[str, list[dict]]:
    traces = {}
    for path in sorted(directory.glob("*.jsonl")):
        aircraft = path.stem.lower()
        if len(aircraft) == 6:
            traces[aircraft] = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return traces


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--candidate-archive", type=Path, required=True)
    parser.add_argument("--notam-archive", type=Path, required=True)
    parser.add_argument("--trace-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = validate_sources(
        args.manifest, args.candidate_archive, args.notam_archive
    )
    notams = tuple(csv_rows(args.notam_archive, "NOTAM_ICAO_GPS-2023.csv"))
    candidates = csv_rows(args.candidate_archive, "GPS_Jumps_from_Routes-2023.csv")
    selection = select_candidate(candidates, notams, load_traces(args.trace_directory))
    payload = selection.private_dict()
    payload.update(
        {
            "source_manifest_sha256": checksum(args.manifest, "sha256"),
            "trace_license": manifest["surrounding_trace"]["license"],
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(selection.candidate_id)


if __name__ == "__main__":
    main()
