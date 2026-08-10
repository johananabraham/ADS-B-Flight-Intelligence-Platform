"""Read-only status summary for versioned safety-source ingestion."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from ...core.database import SessionLocal
from ...core.vectorstore import get_collection_stats
from ...models import (
    Incident,
    Regulation,
    SafetyIngestionRejectionRecord,
    SafetyIngestionRunRecord,
)
from .contracts import SourceKind


def _run_summary(run: SafetyIngestionRunRecord) -> dict[str, Any]:
    return {
        "run_id": str(run.run_id),
        "source_kind": run.source_kind,
        "source_uri": run.source_uri,
        "source_sha256": run.source_sha256,
        "source_bytes": run.source_bytes,
        "retrieved_at": run.retrieved_at.isoformat(),
        "effective_date": (
            run.effective_date.isoformat() if run.effective_date else None
        ),
        "parser_version": run.parser_version,
        "source_record_count": run.source_record_count,
        "parsed_record_count": run.parsed_record_count,
        "rejected_record_count": run.rejected_record_count,
        "duplicate_identifier_count": run.duplicate_identifier_count,
    }


def get_ingestion_status() -> dict[str, Any]:
    """Return database counts, latest manifests, and current vector counts."""
    latest: dict[str, dict[str, Any]] = {}
    with SessionLocal() as db:
        for source_kind in SourceKind:
            run = db.scalars(
                select(SafetyIngestionRunRecord)
                .where(SafetyIngestionRunRecord.source_kind == source_kind.value)
                .order_by(SafetyIngestionRunRecord.retrieved_at.desc())
                .limit(1)
            ).first()
            if run is not None:
                latest[source_kind.value] = _run_summary(run)

        database_counts = {
            "source_runs": db.scalar(
                select(func.count()).select_from(SafetyIngestionRunRecord)
            )
            or 0,
            "rejections": db.scalar(
                select(func.count()).select_from(SafetyIngestionRejectionRecord)
            )
            or 0,
            "incidents": db.scalar(select(func.count()).select_from(Incident)) or 0,
            "regulations": db.scalar(select(func.count()).select_from(Regulation))
            or 0,
        }

    return {
        "latest_manifests": latest,
        "database": database_counts,
        "vectorstore": get_collection_stats(),
    }
