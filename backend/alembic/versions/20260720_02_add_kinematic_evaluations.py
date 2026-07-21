"""Add deterministic kinematic evaluations.

Revision ID: 20260720_02
Revises: 20260719_01
Create Date: 2026-07-20
"""

from alembic import op


revision = "20260720_02"
down_revision = "20260719_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'anomalytype') THEN
                ALTER TYPE anomalytype ADD VALUE IF NOT EXISTS 'KINEMATIC_PLAUSIBILITY';
            END IF;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS kinematic_evaluations (
            evaluation_id UUID PRIMARY KEY,
            policy_version VARCHAR(20) NOT NULL,
            previous_observation_id UUID NOT NULL
                REFERENCES track_observations(observation_id) ON DELETE RESTRICT,
            current_observation_id UUID NOT NULL
                REFERENCES track_observations(observation_id) ON DELETE RESTRICT,
            source_type VARCHAR(30) NOT NULL,
            source_id VARCHAR(100) NOT NULL,
            icao_hex VARCHAR(6) NOT NULL,
            evaluated_at TIMESTAMPTZ NOT NULL,
            status VARCHAR(30) NOT NULL,
            reason VARCHAR(300),
            delta_seconds DOUBLE PRECISION NOT NULL,
            measurements JSONB NOT NULL,
            rule_results JSONB NOT NULL,
            CONSTRAINT ck_kinematic_evaluation_status CHECK (
                status IN ('PASS', 'FLAGGED', 'INSUFFICIENT_DATA')
            ),
            CONSTRAINT uq_kinematic_evaluation_pair_policy UNIQUE (
                previous_observation_id,
                current_observation_id,
                policy_version
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_kinematic_evaluations_icao_time
        ON kinematic_evaluations (icao_hex, evaluated_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_kinematic_evaluations_status_time
        ON kinematic_evaluations (status, evaluated_at)
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_kinematic_evaluations_status_time",
        table_name="kinematic_evaluations",
    )
    op.drop_index(
        "ix_kinematic_evaluations_icao_time",
        table_name="kinematic_evaluations",
    )
    op.drop_table("kinematic_evaluations")
    # PostgreSQL cannot safely remove one enum value in-place. Leaving the value is
    # backward compatible and avoids rebuilding the anomalies table during rollback.
