"""Add privacy-safe receiver pipeline telemetry.

Revision ID: 20260829_08
Revises: 20260805_06
Create Date: 2026-08-29
"""

from alembic import op


revision = "20260829_08"
down_revision = "20260805_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE sensor_nodes
            ADD COLUMN IF NOT EXISTS pipeline_message_id UUID,
            ADD COLUMN IF NOT EXISTS pipeline_observed_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS pipeline_received_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS receiver_connection VARCHAR(20),
            ADD COLUMN IF NOT EXISTS receiver_policy_version VARCHAR(50),
            ADD COLUMN IF NOT EXISTS receiver_last_message_age_seconds DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS receiver_queue_depth INTEGER,
            ADD COLUMN IF NOT EXISTS receiver_queue_capacity INTEGER,
            ADD COLUMN IF NOT EXISTS receiver_dropped_messages_total INTEGER,
            ADD COLUMN IF NOT EXISTS receiver_reconnects_total INTEGER
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS receiver_pipeline_telemetry (
            message_id UUID PRIMARY KEY,
            schema_version VARCHAR(10) NOT NULL,
            node_id VARCHAR(63) NOT NULL,
            observed_at TIMESTAMPTZ NOT NULL,
            received_at TIMESTAMPTZ NOT NULL,
            connection VARCHAR(20) NOT NULL,
            policy_version VARCHAR(50) NOT NULL,
            last_message_age_seconds DOUBLE PRECISION,
            queue_depth INTEGER NOT NULL,
            queue_capacity INTEGER NOT NULL,
            dropped_messages_total INTEGER NOT NULL,
            reconnects_total INTEGER NOT NULL,
            CONSTRAINT fk_receiver_pipeline_node FOREIGN KEY (node_id)
                REFERENCES sensor_nodes(node_id) ON DELETE RESTRICT,
            CONSTRAINT ck_receiver_pipeline_connection CHECK (
                connection IN ('CONNECTED', 'DEGRADED', 'DISCONNECTED')
            ),
            CONSTRAINT ck_receiver_pipeline_queue CHECK (
                queue_depth >= 0 AND queue_capacity > 0
                AND queue_depth <= queue_capacity
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_receiver_pipeline_node_received "
        "ON receiver_pipeline_telemetry (node_id, received_at)"
    )


def downgrade() -> None:
    op.drop_table("receiver_pipeline_telemetry")
    for column in (
        "receiver_reconnects_total",
        "receiver_dropped_messages_total",
        "receiver_queue_capacity",
        "receiver_queue_depth",
        "receiver_last_message_age_seconds",
        "receiver_policy_version",
        "receiver_connection",
        "pipeline_received_at",
        "pipeline_observed_at",
        "pipeline_message_id",
    ):
        op.drop_column("sensor_nodes", column)
