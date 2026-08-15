"""Section-aware chunking and SQL/vector consistency tests."""

from datetime import date
from uuid import UUID

import pytest

from app.models.safety import format_cfr_reference
from app.safety import tools
from app.safety.ingestion import (
    EcfrSectionRecord,
    NtsbIncidentRecord,
    chunk_incident_narrative,
    compare_corpus_lineage,
    indexed_lineage,
    regulation_document,
)


RUN_ID = UUID("11111111-1111-1111-1111-111111111111")
SHA256 = "a" * 64


class FakeCollection:
    def __init__(self, rows):
        self.rows = rows

    def count(self):
        return len(self.rows)

    def get(self, *, limit, offset, include):
        assert include == ["metadatas"]
        page = self.rows[offset : offset + limit]
        return {
            "ids": [document_id for document_id, _ in page],
            "metadatas": [metadata for _, metadata in page],
        }


def test_short_incident_stays_in_one_combined_document():
    record = NtsbIncidentRecord(
        ntsb_id="ERA26LA001",
        narrative="The airplane lost engine power and landed in a field.",
        probable_cause="Fuel exhaustion caused the loss of power.",
        event_date=date(2026, 7, 1),
    )

    documents = chunk_incident_narrative(
        record,
        source_run_id=RUN_ID,
        source_sha256=SHA256,
    )

    assert len(documents) == 1
    assert documents[0].document_id == "ERA26LA001:combined:0"
    assert documents[0].metadata["section"] == "combined"
    assert documents[0].metadata["source_run_id"] == str(RUN_ID)
    assert "Factual Information:" in documents[0].text
    assert "Probable Cause:" in documents[0].text


def test_long_incident_splits_only_at_sentences_and_preserves_sections():
    factual_sentences = [f"Factual sentence number {index}." for index in range(12)]
    cause_sentences = [f"Cause sentence number {index}." for index in range(4)]
    record = NtsbIncidentRecord(
        ntsb_id="ERA26LA002",
        narrative=" ".join(factual_sentences),
        probable_cause=" ".join(cause_sentences),
    )

    documents = chunk_incident_narrative(
        record,
        source_run_id=RUN_ID,
        source_sha256=SHA256,
        max_tokens=24,
    )

    assert len(documents) > 2
    assert {document.metadata["section"] for document in documents} == {
        "factual_information",
        "probable_cause",
    }
    assert all(
        document.metadata["estimated_token_count"] <= 24 for document in documents
    )
    rendered = " ".join(document.text for document in documents)
    assert all(sentence in rendered for sentence in factual_sentences + cause_sentences)


def test_one_oversized_sentence_is_never_cut_mid_sentence():
    sentence = "word " * 100 + "finished."
    record = NtsbIncidentRecord(ntsb_id="ERA26LA003", narrative=sentence)

    documents = chunk_incident_narrative(
        record,
        source_run_id=RUN_ID,
        source_sha256=SHA256,
        max_tokens=20,
    )

    assert len(documents) == 1
    assert documents[0].text.endswith("finished.")
    assert documents[0].metadata["estimated_token_count"] > 20


def test_regulation_is_one_dated_lineage_document():
    record = EcfrSectionRecord(
        cfr_part=91,
        cfr_section="91.103",
        section_title="Preflight action",
        section_text="Each pilot in command shall become familiar with available information.",
        effective_date=date(2026, 7, 24),
        source_url="https://www.ecfr.gov/api/versioner/v1/full/2026-07-24/title-14.xml?part=91",
    )

    document = regulation_document(
        record,
        source_run_id=RUN_ID,
        source_sha256=SHA256,
    )

    assert document.document_id == "14:91:91.103:2026-07-24"
    assert document.metadata["effective_date"] == "2026-07-24"
    assert document.metadata["source_run_id"] == str(RUN_ID)


def test_cfr_reference_does_not_repeat_part_number():
    assert format_cfr_reference(14, 91, "91.103") == "14 CFR 91.103"
    assert format_cfr_reference(14, 91, "103") == "14 CFR 91.103"


@pytest.mark.asyncio
async def test_regulation_search_formats_reference_and_perfect_score(monkeypatch):
    async def fake_search(**_kwargs):
        return {
            "ids": ["14:91:91.103:2026-07-24"],
            "documents": ["Preflight action."],
            "metadatas": [
                {
                    "cfr_part": 91,
                    "cfr_section": "91.103",
                    "section_title": "Preflight action",
                    "effective_date": "2026-07-24",
                    "source_url": "https://www.ecfr.gov/current/title-14/section-91.103",
                    "source_sha256": "a" * 64,
                    "source_run_id": "run-1",
                }
            ],
            "distances": [0.0],
        }

    monkeypatch.setattr(tools, "search_faa_regulations", fake_search)

    result = await tools.tool_search_faa_regulations("preflight", cfr_part=91)

    assert result["results"][0]["cfr_reference"] == "14 CFR 91.103"
    assert result["results"][0]["document_id"] == "14:91:91.103:2026-07-24"
    assert result["results"][0]["effective_date"] == "2026-07-24"
    assert result["results"][0]["char_end"] == len("Preflight action.")
    assert result["results"][0]["relevance_score"] == 1.0


def test_consistency_reports_missing_orphan_and_wrong_lineage_documents():
    expected = {"a": "run-1", "b": "run-2", "c": "run-3"}
    indexed = {"a": "run-1", "b": "wrong-run", "orphan": "run-4"}

    report = compare_corpus_lineage(expected, indexed)

    assert report.consistent is False
    assert report.missing_document_ids == ("c",)
    assert report.orphan_document_ids == ("orphan",)
    assert report.lineage_mismatches == ("b",)


def test_indexed_lineage_reads_every_page():
    collection = FakeCollection(
        [
            ("a", {"source_run_id": "run-1"}),
            ("b", {"source_run_id": "run-2"}),
            ("c", {}),
        ]
    )

    assert indexed_lineage(collection, page_size=2) == {
        "a": "run-1",
        "b": "run-2",
        "c": "",
    }
