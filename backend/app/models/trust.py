"""Persisted trust evidence and append-only operator actions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class TrustAssessmentRecord(Base):
    __tablename__ = "trust_assessments"

    assessment_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True
    )
    policy_version: Mapped[str] = mapped_column(String(30), nullable=False)
    icao_hex: Mapped[str] = mapped_column(String(6), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    components: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "state IN ('TRUSTED', 'QUESTIONABLE', 'LOW_CONFIDENCE', "
            "'INSUFFICIENT_DATA')",
            name="ck_trust_assessment_state",
        ),
        Index("ix_trust_assessments_icao_time", "icao_hex", "evaluated_at"),
        Index("ix_trust_assessments_state_time", "state", "evaluated_at"),
    )


class TrustOperatorActionRecord(Base):
    __tablename__ = "trust_operator_actions"

    action_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True
    )
    assessment_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("trust_assessments.assessment_id", ondelete="RESTRICT"),
        nullable=False,
    )
    action_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    note: Mapped[str | None] = mapped_column(String(2_000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "action_type IN ('ACKNOWLEDGE', 'ANNOTATE')",
            name="ck_trust_operator_action_type",
        ),
        Index(
            "ix_trust_operator_actions_assessment_time",
            "assessment_id",
            "created_at",
        ),
    )
