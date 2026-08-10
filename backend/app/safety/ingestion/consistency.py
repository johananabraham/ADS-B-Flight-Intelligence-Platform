"""SQL-to-vector corpus consistency checks with source-lineage verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class MetadataCollection(Protocol):
    """Minimal Chroma collection surface used by the consistency checker."""

    def count(self) -> int: ...

    def get(
        self,
        *,
        limit: int,
        offset: int,
        include: list[str],
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class CorpusConsistencyReport:
    """Exact document identity and source-lineage comparison."""

    expected_documents: int
    indexed_documents: int
    missing_document_ids: tuple[str, ...]
    orphan_document_ids: tuple[str, ...]
    lineage_mismatches: tuple[str, ...]

    @property
    def consistent(self) -> bool:
        return not (
            self.missing_document_ids
            or self.orphan_document_ids
            or self.lineage_mismatches
        )


def indexed_lineage(
    collection: MetadataCollection,
    *,
    page_size: int = 1_000,
) -> dict[str, str]:
    """Read all document IDs and source-run IDs without loading document text."""
    if page_size < 1:
        raise ValueError("page_size must be positive")
    lineage: dict[str, str] = {}
    for offset in range(0, collection.count(), page_size):
        page = collection.get(
            limit=page_size,
            offset=offset,
            include=["metadatas"],
        )
        ids = page.get("ids") or []
        metadatas = page.get("metadatas") or []
        for document_id, metadata in zip(ids, metadatas, strict=True):
            lineage[document_id] = str((metadata or {}).get("source_run_id", ""))
    return lineage


def compare_corpus_lineage(
    expected: dict[str, str],
    indexed: dict[str, str],
) -> CorpusConsistencyReport:
    """Compare exact document membership and source-run lineage."""
    expected_ids = set(expected)
    indexed_ids = set(indexed)
    shared_ids = expected_ids & indexed_ids
    return CorpusConsistencyReport(
        expected_documents=len(expected),
        indexed_documents=len(indexed),
        missing_document_ids=tuple(sorted(expected_ids - indexed_ids)),
        orphan_document_ids=tuple(sorted(indexed_ids - expected_ids)),
        lineage_mismatches=tuple(
            sorted(
                document_id
                for document_id in shared_ids
                if expected[document_id] != indexed[document_id]
            )
        ),
    )
