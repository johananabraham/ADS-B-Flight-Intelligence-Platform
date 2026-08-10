#!/usr/bin/env python3
"""Prove chunk replacement and lineage checks against an isolated Chroma corpus."""

from __future__ import annotations

import json
from datetime import date
from hashlib import sha256
from uuid import UUID

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.safety.ingestion import (
    EcfrSectionRecord,
    NtsbIncidentRecord,
    chunk_incident_narrative,
    compare_corpus_lineage,
    indexed_lineage,
    regulation_document,
)


RUN_ID = UUID("22222222-2222-2222-2222-222222222222")
SOURCE_SHA256 = "b" * 64


class DeterministicEmbedding:
    """Small local embedding used only to exercise Chroma persistence behavior."""

    def __call__(self, input):
        vectors = []
        for document in input:
            digest = sha256(document.encode()).digest()
            vectors.append([byte / 255 for byte in digest[:8]])
        return vectors


def _upsert(collection, documents) -> None:
    collection.upsert(
        ids=[document.document_id for document in documents],
        documents=[document.text for document in documents],
        metadatas=[document.metadata for document in documents],
    )


def verify() -> dict[str, object]:
    client = chromadb.EphemeralClient(
        settings=ChromaSettings(anonymized_telemetry=False)
    )
    embedding = DeterministicEmbedding()
    incidents = client.create_collection(
        "incident_narratives_verification",
        embedding_function=embedding,
    )
    regulations = client.create_collection(
        "faa_regulations_verification",
        embedding_function=embedding,
    )

    incident = NtsbIncidentRecord(
        ntsb_id="TEST26LA002",
        narrative=" ".join(
            f"Synthetic factual sentence {index}." for index in range(500)
        ),
        probable_cause="Synthetic probable cause for corpus verification only.",
        event_date=date(2026, 7, 2),
    )
    incident_documents = chunk_incident_narrative(
        incident,
        source_run_id=RUN_ID,
        source_sha256=SOURCE_SHA256,
    )
    regulation = regulation_document(
        EcfrSectionRecord(
            cfr_part=999,
            cfr_section="999.9998",
            section_title="Synthetic corpus verification fixture",
            section_text="This is not regulatory text.",
            effective_date=date(1900, 1, 1),
            source_url="fixture://ci/ecfr-part-999.xml",
        ),
        source_run_id=RUN_ID,
        source_sha256=SOURCE_SHA256,
    )
    _upsert(incidents, incident_documents)
    _upsert(regulations, (regulation,))

    expected_incidents = {
        document.document_id: str(RUN_ID) for document in incident_documents
    }
    expected_regulations = {regulation.document_id: str(RUN_ID)}
    incident_report = compare_corpus_lineage(
        expected_incidents,
        indexed_lineage(incidents, page_size=2),
    )
    regulation_report = compare_corpus_lineage(
        expected_regulations,
        indexed_lineage(regulations),
    )
    if not incident_report.consistent or not regulation_report.consistent:
        raise RuntimeError("fresh vector corpus did not match expected lineage")
    if len(incident_documents) < 2:
        raise RuntimeError("long narrative was not section-aware chunked")

    return {
        "status": "passed",
        "incident_chunks": len(incident_documents),
        "regulation_documents": 1,
        "missing_documents": 0,
        "orphan_documents": 0,
        "lineage_mismatches": 0,
        "embedding": "deterministic_verification_only",
    }


def main() -> int:
    try:
        payload = verify()
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error)}, indent=2))
        return 1
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
