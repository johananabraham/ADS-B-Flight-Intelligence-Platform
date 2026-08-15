"""Source-manifest and dead-letter records for safety-data ingestion."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class SafetyIngestionRunRecord(Base):
    """Immutable lineage and validation summary for one exact source artifact."""

    __tablename__ = "safety_ingestion_runs"

    run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    parser_version: Mapped[str] = mapped_column(String(20), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    parsed_record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    duplicate_identifier_count: Mapped[int] = mapped_column(Integer, nullable=False)
    null_rates: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "source_kind",
            "source_sha256",
            "parser_version",
            name="uq_safety_ingestion_source",
        ),
        Index("ix_safety_ingestion_runs_source_time", "source_kind", "retrieved_at"),
    )


class SafetyIngestionRejectionRecord(Base):
    """A source-row rejection that can be replayed from the retained artifact."""

    __tablename__ = "safety_ingestion_rejections"

    rejection_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("safety_ingestion_runs.run_id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_index: Mapped[int] = mapped_column(Integer, nullable=False)
    source_identifier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str] = mapped_column(String(1_000), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "source_index",
            "code",
            name="uq_safety_ingestion_rejection",
        ),
    )
