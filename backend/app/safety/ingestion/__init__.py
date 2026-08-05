"""Versioned safety-source ingestion contracts and parsers."""

from .contracts import (
    EcfrSectionRecord,
    NtsbIncidentRecord,
    ParsedSource,
    SourceArtifact,
    SourceKind,
    ValidationIssue,
    ValidationReport,
)
from .ecfr import parse_ecfr_part_xml
from .ntsb import parse_ntsb_carol_json

__all__ = [
    "EcfrSectionRecord",
    "NtsbIncidentRecord",
    "ParsedSource",
    "SourceArtifact",
    "SourceKind",
    "ValidationIssue",
    "ValidationReport",
    "parse_ecfr_part_xml",
    "parse_ntsb_carol_json",
]
