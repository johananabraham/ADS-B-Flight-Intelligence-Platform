"""Add edge station current state and immutable telemetry events.

Revision ID: 20260804_04
Revises: 20260803_03
Create Date: 2026-08-04
"""

from alembic import op


revision = "20260804_04"
down_revision = "20260803_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sensor_nodes (
            node_id VARCHAR(63) PRIMARY KEY,
            firmware_version VARCHAR(50),
            boot_id UUID,
            last_sequence INTEGER,
            first_seen_at TIMESTAMPTZ NOT NULL,
            last_received_at TIMESTAMPTZ NOT NULL,
            last_observed_at TIMESTAMPTZ,
            presence_status VARCHAR(20),
            presence_received_at TIMESTAMPTZ,
            uptime_seconds INTEGER,
            reconnect_count INTEGER,
            rssi_dbm INTEGER,
            free_heap_bytes INTEGER,
            offline_queue_depth INTEGER,
            watchdog_reset_count INTEGER,
            temperature_c DOUBLE PRECISION,
            supply_voltage_v DOUBLE PRECISION,
            CONSTRAINT ck_sensor_node_presence CHECK (
                presence_status IS NULL OR presence_status IN ('ONLINE', 'OFFLINE')
            )
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS station_telemetry (
            message_id UUID PRIMARY KEY,
            schema_version VARCHAR(10) NOT NULL,
            node_id VARCHAR(63) NOT NULL,
            firmware_version VARCHAR(50) NOT NULL,
            boot_id UUID NOT NULL,
            sequence INTEGER NOT NULL,
            observed_at TIMESTAMPTZ NOT NULL,
            received_at TIMESTAMPTZ NOT NULL,
            uptime_seconds INTEGER NOT NULL,
            reconnect_count INTEGER NOT NULL,
            rssi_dbm INTEGER NOT NULL,
            free_heap_bytes INTEGER NOT NULL,
            offline_queue_depth INTEGER NOT NULL,
            watchdog_reset_count INTEGER NOT NULL,
            temperature_c DOUBLE PRECISION,
            supply_voltage_v DOUBLE PRECISION,
            CONSTRAINT fk_station_telemetry_node FOREIGN KEY (node_id)
                REFERENCES sensor_nodes(node_id) ON DELETE RESTRICT,
            CONSTRAINT uq_station_telemetry_boot_sequence
                UNIQUE (node_id, boot_id, sequence)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS station_presence_events (
            message_id UUID PRIMARY KEY,
            schema_version VARCHAR(10) NOT NULL,
            node_id VARCHAR(63) NOT NULL,
            status VARCHAR(20) NOT NULL,
            observed_at TIMESTAMPTZ NOT NULL,
            received_at TIMESTAMPTZ NOT NULL,
            reason VARCHAR(100) NOT NULL,
            CONSTRAINT fk_station_presence_node FOREIGN KEY (node_id)
                REFERENCES sensor_nodes(node_id) ON DELETE RESTRICT,
            CONSTRAINT ck_station_presence_status CHECK (
                status IN ('ONLINE', 'OFFLINE')
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sensor_nodes_last_received "
        "ON sensor_nodes (last_received_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_station_telemetry_node_received "
        "ON station_telemetry (node_id, received_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_station_telemetry_boot_sequence "
        "ON station_telemetry (node_id, boot_id, sequence)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_station_presence_node_received "
        "ON station_presence_events (node_id, received_at)"
    )


def downgrade() -> None:
    op.drop_table("station_presence_events")
    op.drop_table("station_telemetry")
    op.drop_table("sensor_nodes")
