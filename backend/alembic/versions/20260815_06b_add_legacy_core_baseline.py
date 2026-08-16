"""Reconcile the legacy core schema for clean Alembic installations.

Revision ID: 20260815_06b
Revises: 20260815_06

The original application created these tables outside Alembic.  Every operation
is idempotent so this revision is safe for databases that already contain them.
"""

from alembic import op


revision = "20260815_06b"
down_revision = "20260815_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'anomalytype') THEN
                CREATE TYPE anomalytype AS ENUM (
                    'RAPID_DESCENT',
                    'RAPID_CLIMB',
                    'SPEED_ANOMALY',
                    'SQUAWK_7500',
                    'SQUAWK_7600',
                    'SQUAWK_7700',
                    'TRACK_LOSS',
                    'GHOST_FLIGHT',
                    'RESTRICTED_AIRSPACE',
                    'ALTITUDE_DEVIATION',
                    'KINEMATIC_PLAUSIBILITY'
                );
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'anomalyseverity') THEN
                CREATE TYPE anomalyseverity AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
            END IF;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS aircraft (
            id SERIAL PRIMARY KEY,
            icao_hex VARCHAR(6) NOT NULL UNIQUE,
            callsign VARCHAR(8),
            registration VARCHAR(10),
            aircraft_type VARCHAR(10),
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            position geometry(POINT, 4326),
            altitude INTEGER,
            ground_speed DOUBLE PRECISION,
            track DOUBLE PRECISION,
            vertical_rate INTEGER,
            squawk VARCHAR(4),
            last_seen TIMESTAMP WITHOUT TIME ZONE,
            first_seen TIMESTAMP WITHOUT TIME ZONE,
            messages_received INTEGER
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS aircraft_positions (
            id SERIAL PRIMARY KEY,
            icao_hex VARCHAR(6) NOT NULL,
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            position geometry(POINT, 4326),
            altitude INTEGER,
            ground_speed DOUBLE PRECISION,
            track DOUBLE PRECISION,
            vertical_rate INTEGER,
            timestamp TIMESTAMP WITHOUT TIME ZONE
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS anomalies (
            id SERIAL PRIMARY KEY,
            icao_hex VARCHAR(6) NOT NULL,
            callsign VARCHAR(8),
            anomaly_type anomalytype NOT NULL,
            severity anomalyseverity NOT NULL,
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            altitude INTEGER,
            description VARCHAR(500),
            details JSONB,
            detected_at TIMESTAMP WITHOUT TIME ZONE,
            resolved_at TIMESTAMP WITHOUT TIME ZONE,
            acknowledged INTEGER
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_summaries (
            id SERIAL PRIMARY KEY,
            date TIMESTAMP WITHOUT TIME ZONE NOT NULL UNIQUE,
            total_aircraft INTEGER,
            total_positions INTEGER,
            total_anomalies INTEGER,
            summary_text VARCHAR(5000),
            key_events JSONB,
            generated_at TIMESTAMP WITHOUT TIME ZONE
        )
        """
    )

    indexes = (
        "CREATE INDEX IF NOT EXISTS ix_aircraft_position ON aircraft USING gist (position)",
        "CREATE INDEX IF NOT EXISTS ix_aircraft_last_seen ON aircraft (last_seen)",
        "CREATE INDEX IF NOT EXISTS ix_aircraft_last_seen_icao ON aircraft (last_seen, icao_hex)",
        "CREATE INDEX IF NOT EXISTS ix_positions_icao_time ON aircraft_positions (icao_hex, timestamp)",
        "CREATE INDEX IF NOT EXISTS ix_positions_time ON aircraft_positions (timestamp)",
        "CREATE INDEX IF NOT EXISTS ix_anomalies_icao_hex ON anomalies (icao_hex)",
        "CREATE INDEX IF NOT EXISTS ix_anomalies_detected_at ON anomalies (detected_at)",
        "CREATE INDEX IF NOT EXISTS ix_anomalies_type_time ON anomalies (anomaly_type, detected_at)",
        "CREATE INDEX IF NOT EXISTS ix_daily_summaries_date ON daily_summaries (date)",
    )
    for statement in indexes:
        op.execute(statement)


def downgrade() -> None:
    # This revision adopts tables that may predate Alembic. Dropping them would
    # destroy operator data, so downgrade intentionally preserves the baseline.
    pass
