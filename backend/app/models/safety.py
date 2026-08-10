"""SQLAlchemy models for aviation safety research data (NTSB incidents, FAA regulations)."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class Incident(Base):
    """NTSB aviation incident/accident record."""

    __tablename__ = "incidents"

    # Primary key
    ntsb_id: Mapped[str] = mapped_column(String(20), primary_key=True)

    # Event details
    event_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    event_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    event_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    event_country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Aircraft information
    aircraft_make: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    aircraft_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    aircraft_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    aircraft_damage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    registration_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Injury information
    fatal_injuries: Mapped[int] = mapped_column(Integer, default=0)
    serious_injuries: Mapped[int] = mapped_column(Integer, default=0)
    minor_injuries: Mapped[int] = mapped_column(Integer, default=0)
    uninjured: Mapped[int] = mapped_column(Integer, default=0)

    # Flight conditions
    weather_condition: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    phase_of_flight: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    flight_purpose: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Investigation details
    investigation_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    probable_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    narrative: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_run_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "safety_ingestion_runs.run_id",
            ondelete="RESTRICT",
            name="fk_incidents_source_run",
        ),
        nullable=True,
    )

    # Pilot information
    pilot_certificate: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    pilot_total_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_incidents_make_model", "aircraft_make", "aircraft_model"),
        Index("ix_incidents_state_date", "event_state", "event_date"),
        Index("ix_incidents_fatal", "fatal_injuries"),
    )

    def __repr__(self) -> str:
        return f"<Incident(ntsb_id={self.ntsb_id}, date={self.event_date}, aircraft={self.aircraft_make} {self.aircraft_model})>"


class Regulation(Base):
    """FAA regulation from 14 CFR."""

    __tablename__ = "regulations"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # CFR reference
    cfr_title: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    cfr_part: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    cfr_section: Mapped[str] = mapped_column(String(20), nullable=False)
    cfr_subpart: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Content
    section_title: Mapped[str] = mapped_column(String(500), nullable=False)
    section_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadata
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_run_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "safety_ingestion_runs.run_id",
            ondelete="RESTRICT",
            name="fk_regulations_source_run",
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Indexes
    __table_args__ = (
        Index(
            "ix_regulations_cfr_ref_date",
            "cfr_title",
            "cfr_part",
            "cfr_section",
            "effective_date",
            unique=True,
        ),
        Index("ix_regulations_part", "cfr_part"),
    )

    @property
    def cfr_reference(self) -> str:
        """Return formatted CFR reference (e.g., '14 CFR 91.103')."""
        return f"{self.cfr_title} CFR {self.cfr_part}.{self.cfr_section}"

    def __repr__(self) -> str:
        return f"<Regulation({self.cfr_reference}: {self.section_title[:50]}...)>"
