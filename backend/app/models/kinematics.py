"""Persistence model for deterministic kinematic evidence."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class KinematicEvaluationRecord(Base):
    """One versioned evaluation of two immutable source observations."""

    __tablename__ = "kinematic_evaluations"

    evaluation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True
    )
    policy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    previous_observation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    current_observation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    icao_hex: Mapped[str] = mapped_column(String(6), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(300))
    delta_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    measurements: Mapped[dict[str, float]] = mapped_column(JSONB, nullable=False)
    rule_results: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "previous_observation_id",
            "current_observation_id",
            "policy_version",
            name="uq_kinematic_evaluation_pair_policy",
        ),
        Index("ix_kinematic_evaluations_icao_time", "icao_hex", "evaluated_at"),
        Index("ix_kinematic_evaluations_status_time", "status", "evaluated_at"),
    )
