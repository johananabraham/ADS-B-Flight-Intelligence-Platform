"""Add immutable track observations.

Revision ID: 20260719_01
Revises:
Create Date: 2026-07-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260719_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "track_observations",
        sa.Column("observation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(length=10), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.String(length=100), nullable=False),
        sa.Column("receiver_id", sa.String(length=100), nullable=True),
        sa.Column("recording_id", sa.String(length=100), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("license_id", sa.String(length=100), nullable=True),
        sa.Column("icao_hex", sa.String(length=6), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("callsign", sa.String(length=8), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("altitude_ft", sa.Integer(), nullable=True),
        sa.Column("ground_speed_knots", sa.Float(), nullable=True),
        sa.Column("track_degrees", sa.Float(), nullable=True),
        sa.Column("vertical_rate_fpm", sa.Integer(), nullable=True),
        sa.Column("squawk", sa.String(length=4), nullable=True),
        sa.Column("quality_flags", postgresql.JSONB(), nullable=False),
        sa.Column("raw_message_id", sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint("observation_id"),
    )
    op.create_index(
        "ix_track_observations_icao_time",
        "track_observations",
        ["icao_hex", "observed_at"],
    )
    op.create_index(
        "ix_track_observations_source_time",
        "track_observations",
        ["source_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_track_observations_source_time", table_name="track_observations")
    op.drop_index("ix_track_observations_icao_time", table_name="track_observations")
    op.drop_table("track_observations")
