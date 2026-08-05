"""Publish schema-valid station telemetry without physical ESP32 hardware."""

from __future__ import annotations

import argparse
import os
import signal
import ssl
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import paho.mqtt.client as mqtt

from app.schemas.edge import (
    PresenceStatus,
    StationPresence,
    StationTelemetry,
    presence_topic,
    telemetry_topic,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--node-id", default=os.environ.get("STATION_NODE_ID", "roof-node-1")
    )
    parser.add_argument("--interval", type=float, default=15.0)
    parser.add_argument(
        "--count", type=int, default=0, help="zero publishes until stopped"
    )
    args = parser.parse_args()
    if args.interval <= 0 or args.count < 0:
        parser.error("interval must be positive and count cannot be negative")

    password = _read_secret("STATION_MQTT_PASSWORD")
    ca_cert = _required("MQTT_CA_CERT")
    boot_id = uuid4()
    started = time.monotonic()
    stop_event = threading.Event()

    def request_stop(_signum, _frame) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"station-simulator-{args.node_id}",
        clean_session=False,
        protocol=mqtt.MQTTv311,
    )
    client.username_pw_set(args.node_id, password)
    context = ssl.create_default_context(cafile=ca_cert)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    client.tls_set_context(context)
    offline = _presence(args.node_id, PresenceStatus.OFFLINE, "mqtt-last-will")
    client.will_set(
        presence_topic(args.node_id), offline.model_dump_json(), qos=1, retain=True
    )
    client.connect(_required("MQTT_HOST"), int(os.environ.get("MQTT_PORT", "8883")))
    client.loop_start()
    connection_deadline = time.monotonic() + 10
    while not client.is_connected() and time.monotonic() < connection_deadline:
        stop_event.wait(0.1)
    if not client.is_connected():
        client.loop_stop()
        raise RuntimeError("MQTT connection did not become ready within 10 seconds")
    online = _presence(args.node_id, PresenceStatus.ONLINE, "simulator-connected")
    client.publish(
        presence_topic(args.node_id), online.model_dump_json(), qos=1, retain=True
    ).wait_for_publish()

    sequence = 0
    try:
        while not stop_event.is_set() and (args.count == 0 or sequence < args.count):
            telemetry = StationTelemetry(
                node_id=args.node_id,
                firmware_version="0.1.0+simulator",
                boot_id=boot_id,
                sequence=sequence,
                observed_at=datetime.now(timezone.utc),
                uptime_seconds=int(time.monotonic() - started),
                reconnect_count=0,
                rssi_dbm=-50,
                free_heap_bytes=120_000,
                offline_queue_depth=0,
                watchdog_reset_count=0,
            )
            client.publish(
                telemetry_topic(args.node_id),
                telemetry.model_dump_json(),
                qos=1,
            ).wait_for_publish()
            sequence += 1
            if not stop_event.is_set() and (args.count == 0 or sequence < args.count):
                stop_event.wait(args.interval)
    finally:
        if client.is_connected():
            graceful = _presence(
                args.node_id, PresenceStatus.OFFLINE, "simulator-stopped"
            )
            client.publish(
                presence_topic(args.node_id),
                graceful.model_dump_json(),
                qos=1,
                retain=True,
            ).wait_for_publish()
        client.disconnect()
        client.loop_stop()
    return 0


def _presence(node_id: str, status: PresenceStatus, reason: str) -> StationPresence:
    return StationPresence(
        node_id=node_id,
        status=status,
        observed_at=datetime.now(timezone.utc),
        reason=reason,
    )


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _read_secret(name: str) -> str:
    file_path = os.environ.get(f"{name}_FILE", "").strip()
    inline = os.environ.get(name, "").strip()
    if file_path and inline:
        raise ValueError(f"configure only one of {name} or {name}_FILE")
    if file_path:
        value = Path(file_path).read_text(encoding="utf-8").strip()
    else:
        value = inline
    if not value:
        raise ValueError(f"{name} or {name}_FILE is required")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
