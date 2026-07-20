"""Add immutable track observations.

Revision ID: 20260719_01
Revises:
Create Date: 2026-07-19
"""

from alembic import op


revision = "20260719_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Development startup still creates model metadata. IF NOT EXISTS keeps this
    # additive migration safe whether Alembic or the API reaches a fresh DB first.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS track_observations (
            observation_id UUID PRIMARY KEY,
            schema_version VARCHAR(10) NOT NULL,
            source_type VARCHAR(30) NOT NULL,
            source_id VARCHAR(100) NOT NULL,
            receiver_id VARCHAR(100),
            recording_id VARCHAR(100),
            provider VARCHAR(100),
            license_id VARCHAR(100),
            icao_hex VARCHAR(6) NOT NULL,
            observed_at TIMESTAMPTZ NOT NULL,
            received_at TIMESTAMPTZ NOT NULL,
            callsign VARCHAR(8),
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            altitude_ft INTEGER,
            ground_speed_knots DOUBLE PRECISION,
            track_degrees DOUBLE PRECISION,
            vertical_rate_fpm INTEGER,
            squawk VARCHAR(4),
            quality_flags JSONB NOT NULL,
            raw_message_id VARCHAR(200)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_track_observations_icao_time
        ON track_observations (icao_hex, observed_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_track_observations_source_time
        ON track_observations (source_id, observed_at)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_track_observations_source_time", table_name="track_observations")
    op.drop_index("ix_track_observations_icao_time", table_name="track_observations")
    op.drop_table("track_observations")
