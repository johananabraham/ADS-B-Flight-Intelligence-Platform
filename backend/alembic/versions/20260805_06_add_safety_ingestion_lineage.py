"""Add safety-source manifests, dead letters, and row lineage.

Revision ID: 20260805_06
Revises: 20260815_07
Create Date: 2026-08-05
"""

from alembic import op


revision = "20260805_06"
down_revision = "20260815_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS safety_ingestion_runs (
            run_id UUID PRIMARY KEY,
            source_kind VARCHAR(40) NOT NULL,
            source_uri TEXT NOT NULL,
            source_sha256 VARCHAR(64) NOT NULL,
            source_bytes BIGINT NOT NULL CHECK (source_bytes > 0),
            retrieved_at TIMESTAMPTZ NOT NULL,
            effective_date DATE,
            parser_version VARCHAR(20) NOT NULL,
            parameters JSONB NOT NULL,
            source_record_count INTEGER NOT NULL CHECK (source_record_count >= 0),
            parsed_record_count INTEGER NOT NULL CHECK (parsed_record_count >= 0),
            rejected_record_count INTEGER NOT NULL CHECK (rejected_record_count >= 0),
            duplicate_identifier_count INTEGER NOT NULL
                CHECK (duplicate_identifier_count >= 0),
            null_rates JSONB NOT NULL,
            ingested_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT uq_safety_ingestion_source
                UNIQUE (source_kind, source_sha256, parser_version)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS safety_ingestion_rejections (
            rejection_id BIGSERIAL PRIMARY KEY,
            run_id UUID NOT NULL REFERENCES safety_ingestion_runs(run_id)
                ON DELETE RESTRICT,
            source_index INTEGER NOT NULL CHECK (source_index >= 0),
            source_identifier VARCHAR(100),
            code VARCHAR(80) NOT NULL,
            message VARCHAR(1000) NOT NULL,
            CONSTRAINT uq_safety_ingestion_rejection
                UNIQUE (run_id, source_index, code)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS incidents (
            ntsb_id VARCHAR(20) PRIMARY KEY,
            event_date DATE,
            event_city VARCHAR(100),
            event_state VARCHAR(50),
            event_country VARCHAR(100),
            aircraft_make VARCHAR(100),
            aircraft_model VARCHAR(100),
            aircraft_category VARCHAR(50),
            aircraft_damage VARCHAR(50),
            registration_number VARCHAR(20),
            fatal_injuries INTEGER NOT NULL DEFAULT 0,
            serious_injuries INTEGER NOT NULL DEFAULT 0,
            minor_injuries INTEGER NOT NULL DEFAULT 0,
            uninjured INTEGER NOT NULL DEFAULT 0,
            weather_condition VARCHAR(20),
            phase_of_flight VARCHAR(50),
            flight_purpose VARCHAR(100),
            investigation_type VARCHAR(20),
            probable_cause TEXT,
            narrative TEXT,
            pilot_certificate VARCHAR(50),
            pilot_total_hours INTEGER,
            source_url TEXT,
            source_run_id UUID CONSTRAINT fk_incidents_source_run
                REFERENCES safety_ingestion_runs(run_id) ON DELETE RESTRICT,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS regulations (
            id SERIAL PRIMARY KEY,
            cfr_title INTEGER NOT NULL DEFAULT 14,
            cfr_part INTEGER NOT NULL,
            cfr_section VARCHAR(20) NOT NULL,
            cfr_subpart VARCHAR(10),
            section_title VARCHAR(500) NOT NULL,
            section_text TEXT NOT NULL,
            effective_date DATE,
            source_url VARCHAR(500),
            source_run_id UUID CONSTRAINT fk_regulations_source_run
                REFERENCES safety_ingestion_runs(run_id) ON DELETE RESTRICT,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS source_url TEXT")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS source_run_id UUID")
    op.execute("ALTER TABLE regulations ADD COLUMN IF NOT EXISTS source_run_id UUID")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_incidents_source_run'
            ) THEN
                ALTER TABLE incidents ADD CONSTRAINT fk_incidents_source_run
                    FOREIGN KEY (source_run_id) REFERENCES safety_ingestion_runs(run_id)
                    ON DELETE RESTRICT;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_regulations_source_run'
            ) THEN
                ALTER TABLE regulations ADD CONSTRAINT fk_regulations_source_run
                    FOREIGN KEY (source_run_id) REFERENCES safety_ingestion_runs(run_id)
                    ON DELETE RESTRICT;
            END IF;
        END $$
        """
    )
    op.execute("DROP INDEX IF EXISTS ix_regulations_cfr_ref")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_regulations_cfr_ref_date
        ON regulations (cfr_title, cfr_part, cfr_section, effective_date)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_safety_ingestion_runs_source_time
        ON safety_ingestion_runs (source_kind, retrieved_at)
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_incidents_make_model "
        "ON incidents (aircraft_make, aircraft_model)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_incidents_state_date "
        "ON incidents (event_state, event_date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_incidents_fatal ON incidents (fatal_injuries)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_regulations_part ON regulations (cfr_part)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_regulations_cfr_ref_date")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_regulations_cfr_ref
        ON regulations (cfr_title, cfr_part, cfr_section)
        """
    )
    op.execute("ALTER TABLE regulations DROP CONSTRAINT IF EXISTS fk_regulations_source_run")
    op.execute("ALTER TABLE incidents DROP CONSTRAINT IF EXISTS fk_incidents_source_run")
    op.execute("ALTER TABLE regulations DROP COLUMN IF EXISTS source_run_id")
    op.execute("ALTER TABLE incidents DROP COLUMN IF EXISTS source_run_id")
    op.execute("ALTER TABLE incidents DROP COLUMN IF EXISTS source_url")
    op.drop_table("safety_ingestion_rejections")
    op.drop_table("safety_ingestion_runs")
