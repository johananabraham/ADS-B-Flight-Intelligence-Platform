"""Publish privacy-safe local receiver-pipeline health over authenticated MQTT."""

from __future__ import annotations

import argparse
import json
import os
import signal
import ssl
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, build_opener

import paho.mqtt.client as mqtt

from app.schemas.edge import (
    ReceiverConnection,
    ReceiverPipelineTelemetry,
    pipeline_topic,
)


LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_sidecar_url(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in LOOPBACK_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("sidecar URL must be an unauthenticated HTTP loopback URL")
    path = parsed.path.rstrip("/")
    if path not in ("", "/api/v1/integrity"):
        raise ValueError("sidecar URL path must be empty or /api/v1/integrity")
    return value.rstrip("/")


def pipeline_from_health(
    node_id: str,
    health: Mapping[str, Any],
    *,
    observed_at: datetime,
) -> ReceiverPipelineTelemetry:
    if health.get("schema_version") != "1.0":
        raise ValueError("unsupported sidecar health schema")
    last_message_age: float | None = None
    raw_last_message = health.get("last_message_at")
    if raw_last_message is not None:
        last_message = datetime.fromisoformat(str(raw_last_message).replace("Z", "+00:00"))
        if last_message.tzinfo is None or last_message.utcoffset() is None:
            raise ValueError("sidecar last_message_at must include a timezone")
        last_message_age = max(0.0, (observed_at - last_message).total_seconds())
    return ReceiverPipelineTelemetry(
        node_id=node_id,
        observed_at=observed_at,
        connection=ReceiverConnection(str(health["connection"])),
        policy_version=str(health["policy_version"]),
        last_message_age_seconds=last_message_age,
        queue_depth=int(health["queue_depth"]),
        queue_capacity=int(health["queue_capacity"]),
        dropped_messages_total=int(health["dropped_messages_total"]),
        reconnects_total=int(health["reconnects_total"]),
    )


def unavailable_pipeline(node_id: str, observed_at: datetime) -> ReceiverPipelineTelemetry:
    return ReceiverPipelineTelemetry(
        node_id=node_id,
        observed_at=observed_at,
        connection=ReceiverConnection.DISCONNECTED,
        policy_version="sidecar-unavailable",
        queue_depth=0,
        queue_capacity=1,
        dropped_messages_total=0,
        reconnects_total=0,
    )


def read_sidecar_health(base_url: str) -> dict[str, Any]:
    url = (
        f"{base_url}/api/v1/integrity/health"
        if "/api/v1/integrity" not in base_url
        else f"{base_url}/health"
    )
    opener = build_opener(_RejectRedirects)
    with opener.open(url, timeout=3) as response:  # noqa: S310 - loopback only
        if response.status != 200:
            raise RuntimeError(f"sidecar returned HTTP {response.status}")
        document = json.load(response)
    if not isinstance(document, dict):
        raise ValueError("sidecar health response must be an object")
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node-id", default=os.environ.get("STATION_NODE_ID", "roof-node-1"))
    parser.add_argument("--sidecar-url", default="http://127.0.0.1:8090")
    parser.add_argument("--interval", type=float, default=15.0)
    parser.add_argument("--count", type=int, default=0, help="zero publishes until stopped")
    args = parser.parse_args()
    if not 5 <= args.interval <= 300 or args.count < 0:
        parser.error("interval must be 5-300 seconds and count cannot be negative")
    try:
        sidecar_url = validate_sidecar_url(args.sidecar_url)
    except ValueError as exc:
        parser.error(str(exc))

    password = _read_secret("PIPELINE_MQTT_PASSWORD")
    stop_event = threading.Event()

    def request_stop(_signum, _frame) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    client = _mqtt_client(args.node_id, password)
    client.connect(_required("MQTT_HOST"), int(os.environ.get("MQTT_PORT", "8883")))
    client.loop_start()
    deadline = time.monotonic() + 10
    while not client.is_connected() and time.monotonic() < deadline:
        stop_event.wait(0.1)
    if not client.is_connected():
        client.loop_stop()
        raise RuntimeError("MQTT connection did not become ready within 10 seconds")

    published = 0
    try:
        while not stop_event.is_set() and (args.count == 0 or published < args.count):
            now = datetime.now(timezone.utc)
            try:
                health = read_sidecar_health(sidecar_url)
                telemetry = pipeline_from_health(args.node_id, health, observed_at=now)
            except (HTTPError, URLError, TimeoutError, OSError, KeyError, TypeError, ValueError):
                telemetry = unavailable_pipeline(args.node_id, now)
            client.publish(
                pipeline_topic(args.node_id), telemetry.model_dump_json(), qos=1
            ).wait_for_publish()
            published += 1
            if args.count == 0 or published < args.count:
                stop_event.wait(args.interval)
    finally:
        client.disconnect()
        client.loop_stop()
    return 0


def _mqtt_client(node_id: str, password: str) -> mqtt.Client:
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"receiver-pipeline-{node_id}",
        clean_session=False,
        protocol=mqtt.MQTTv311,
    )
    client.username_pw_set(f"{node_id}-bridge", password)
    context = ssl.create_default_context(cafile=_required("MQTT_CA_CERT"))
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    client.tls_set_context(context)
    client.tls_insecure_set(False)
    client.reconnect_delay_set(min_delay=1, max_delay=60)
    return client


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
    value = Path(file_path).read_text(encoding="utf-8").strip() if file_path else inline
    if not value:
        raise ValueError(f"{name} or {name}_FILE is required")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
