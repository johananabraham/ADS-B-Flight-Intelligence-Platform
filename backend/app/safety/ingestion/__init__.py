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
from .chunking import (
    CHUNKER_VERSION,
    DEFAULT_MAX_TOKENS,
    VectorDocument,
    chunk_incident_narrative,
    regulation_document,
)
from .consistency import (
    CorpusConsistencyReport,
    compare_corpus_lineage,
    indexed_lineage,
)
from .ecfr import fetch_ecfr_part, parse_ecfr_part_xml
from .ntsb import load_ntsb_carol_export, parse_ntsb_carol_json
from .persistence import (
    IngestionOutcome,
    ingestion_run_id,
    persist_ecfr_source,
    persist_ntsb_source,
)
from .status import get_ingestion_status

__all__ = [
    "EcfrSectionRecord",
    "NtsbIncidentRecord",
    "ParsedSource",
    "SourceArtifact",
    "SourceKind",
    "ValidationIssue",
    "ValidationReport",
    "CHUNKER_VERSION",
    "DEFAULT_MAX_TOKENS",
    "VectorDocument",
    "chunk_incident_narrative",
    "regulation_document",
    "CorpusConsistencyReport",
    "compare_corpus_lineage",
    "indexed_lineage",
    "parse_ecfr_part_xml",
    "parse_ntsb_carol_json",
    "fetch_ecfr_part",
    "load_ntsb_carol_export",
    "IngestionOutcome",
    "ingestion_run_id",
    "persist_ecfr_source",
    "persist_ntsb_source",
    "get_ingestion_status",
]
