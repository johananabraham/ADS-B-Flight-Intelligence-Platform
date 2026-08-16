"""Separate operational events from integrity evidence.

Revision ID: 20260815_07
Revises: 20260815_06b
"""

from alembic import op
import sqlalchemy as sa


revision = "20260815_07"
down_revision = "20260815_06b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'anomalytype') THEN
                ALTER TYPE anomalytype ADD VALUE IF NOT EXISTS 'TRACK_LOSS';
            END IF;
        END
        $$
        """
    )
    op.add_column(
        "anomalies",
        sa.Column(
            "category",
            sa.String(length=32),
            server_default="OPERATIONAL_EVENT",
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE anomalies
        SET category = 'INTEGRITY_EVIDENCE'
        WHERE anomaly_type::text = 'KINEMATIC_PLAUSIBILITY'
        """
    )
    op.create_index(
        "ix_anomalies_category_time",
        "anomalies",
        ["category", "detected_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_anomalies_category_time", table_name="anomalies")
    op.drop_column("anomalies", "category")
    # PostgreSQL enum values are intentionally retained to keep downgrade safe.
