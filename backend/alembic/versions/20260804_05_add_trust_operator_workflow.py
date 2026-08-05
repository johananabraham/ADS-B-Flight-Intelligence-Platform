"""Add trust assessments and append-only operator actions.

Revision ID: 20260804_05
Revises: 20260804_04
Create Date: 2026-08-04
"""

from alembic import op


revision = "20260804_05"
down_revision = "20260804_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS trust_assessments (
            assessment_id UUID PRIMARY KEY,
            policy_version VARCHAR(30) NOT NULL,
            icao_hex VARCHAR(6) NOT NULL,
            evaluated_at TIMESTAMPTZ NOT NULL,
            state VARCHAR(30) NOT NULL,
            reasons JSONB NOT NULL,
            components JSONB NOT NULL,
            CONSTRAINT ck_trust_assessment_state CHECK (
                state IN ('TRUSTED', 'QUESTIONABLE', 'LOW_CONFIDENCE',
                          'INSUFFICIENT_DATA')
            )
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS trust_operator_actions (
            action_id UUID PRIMARY KEY,
            assessment_id UUID NOT NULL,
            action_type VARCHAR(20) NOT NULL,
            actor VARCHAR(100) NOT NULL,
            note VARCHAR(2000),
            created_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT fk_trust_action_assessment FOREIGN KEY (assessment_id)
                REFERENCES trust_assessments(assessment_id) ON DELETE RESTRICT,
            CONSTRAINT ck_trust_operator_action_type CHECK (
                action_type IN ('ACKNOWLEDGE', 'ANNOTATE')
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trust_assessments_icao_time "
        "ON trust_assessments (icao_hex, evaluated_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trust_assessments_state_time "
        "ON trust_assessments (state, evaluated_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trust_operator_actions_assessment_time "
        "ON trust_operator_actions (assessment_id, created_at)"
    )


def downgrade() -> None:
    op.drop_table("trust_operator_actions")
    op.drop_table("trust_assessments")
