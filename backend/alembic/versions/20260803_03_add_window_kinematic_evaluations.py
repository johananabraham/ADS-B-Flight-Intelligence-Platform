"""Add short-window kinematic evaluations.

Revision ID: 20260803_03
Revises: 20260720_02
Create Date: 2026-08-03
"""

from alembic import op


revision = "20260803_03"
down_revision = "20260720_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS window_kinematic_evaluations (
            evaluation_id UUID PRIMARY KEY,
            policy_version VARCHAR(30) NOT NULL,
            first_observation_id UUID NOT NULL
                REFERENCES track_observations(observation_id) ON DELETE RESTRICT,
            current_observation_id UUID NOT NULL
                REFERENCES track_observations(observation_id) ON DELETE RESTRICT,
            observation_ids JSONB NOT NULL,
            source_type VARCHAR(30) NOT NULL,
            source_id VARCHAR(100) NOT NULL,
            icao_hex VARCHAR(6) NOT NULL,
            evaluated_at TIMESTAMPTZ NOT NULL,
            status VARCHAR(30) NOT NULL,
            reason VARCHAR(300),
            duration_seconds DOUBLE PRECISION NOT NULL,
            measurements JSONB NOT NULL,
            rule_results JSONB NOT NULL,
            CONSTRAINT ck_window_kinematic_evaluation_status CHECK (
                status IN ('PASS', 'FLAGGED', 'INSUFFICIENT_DATA')
            ),
            CONSTRAINT uq_window_kinematic_evaluation_window_policy UNIQUE (
                first_observation_id, current_observation_id, policy_version
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_window_kinematic_icao_time
        ON window_kinematic_evaluations (icao_hex, evaluated_at)
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_window_kinematic_icao_time",
        table_name="window_kinematic_evaluations",
    )
    op.drop_table("window_kinematic_evaluations")
