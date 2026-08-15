"""Fail-closed source license and checksum validation."""

import hashlib
import json
from pathlib import Path


def checksum(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_sources(
    manifest_path: str | Path,
    candidate_archive: str | Path,
    notam_archive: str | Path,
) -> dict:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    for section, archive in (
        ("candidate_index", Path(candidate_archive)),
        ("notam_index", Path(notam_archive)),
    ):
        source = manifest[section]
        if source.get("license_status") != "APPROVED_FOR_PROCESSING":
            raise ValueError(f"{section} license is not approved for processing")
        if archive.name != source["filename"]:
            raise ValueError(f"{section} filename does not match the pinned manifest")
        if checksum(archive, "md5") != source["md5"]:
            raise ValueError(f"{section} checksum mismatch")
    trace = manifest["surrounding_trace"]
    if not str(trace.get("processing_status", "")).startswith("ALLOWED"):
        raise ValueError("surrounding trace license is not approved for processing")
    return manifest
