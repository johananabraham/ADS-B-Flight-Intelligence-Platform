"""Consume validated station telemetry over authenticated MQTT/TLS."""

from __future__ import annotations

import logging
import os
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from app.core.database import SessionLocal
from app.services.station_mqtt import StationMessageError, process_station_message


LOGGER = logging.getLogger("edge-telemetry-consumer")
SUBSCRIPTIONS = (
    ("adsb/stations/v1/+/telemetry", 1),
    ("adsb/stations/v1/+/presence", 1),
    ("adsb/stations/v1/+/pipeline", 1),
)


@dataclass(frozen=True)
class ConsumerSettings:
    host: str
    port: int
    username: str
    password: str
    ca_cert: str
    client_cert: str | None = None
    client_key: str | None = None
    keepalive_seconds: int = 60

    @classmethod
    def from_environment(cls) -> "ConsumerSettings":
        return cls(
            host=_required("MQTT_HOST"),
            port=int(os.environ.get("MQTT_PORT", "8883")),
            username=_required("MQTT_CONSUMER_USERNAME"),
            password=_secret("MQTT_CONSUMER_PASSWORD"),
            ca_cert=_required("MQTT_CA_CERT"),
            client_cert=os.environ.get("MQTT_CLIENT_CERT") or None,
            client_key=os.environ.get("MQTT_CLIENT_KEY") or None,
        )

    def __post_init__(self) -> None:
        if not 1 <= self.port <= 65_535:
            raise ValueError("MQTT_PORT must be between 1 and 65535")
        if self.keepalive_seconds <= 0:
            raise ValueError("MQTT keepalive must be positive")
        if bool(self.client_cert) != bool(self.client_key):
            raise ValueError(
                "MQTT client certificate and key must be configured together"
            )


def build_client(settings: ConsumerSettings) -> mqtt.Client:
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="adsb-edge-telemetry-consumer",
        clean_session=False,
        protocol=mqtt.MQTTv311,
        manual_ack=True,
    )
    client.username_pw_set(settings.username, settings.password)
    context = ssl.create_default_context(cafile=settings.ca_cert)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    if settings.client_cert and settings.client_key:
        context.load_cert_chain(settings.client_cert, settings.client_key)
    client.tls_set_context(context)
    client.tls_insecure_set(False)
    client.reconnect_delay_set(min_delay=1, max_delay=60)
    client.on_connect = _on_connect
    client.on_message = _on_message
    client.enable_logger(LOGGER)
    return client


def _on_connect(client, _userdata, _flags, reason_code, _properties) -> None:
    if reason_code.is_failure:
        LOGGER.error("MQTT connection rejected: %s", reason_code)
        return
    for topic, qos in SUBSCRIPTIONS:
        result, _message_id = client.subscribe(topic, qos=qos)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"failed to subscribe to {topic}: MQTT error {result}")
    LOGGER.info("Connected to MQTT broker and subscribed to station topics")


def _on_message(client, _userdata, message) -> None:
    db = SessionLocal()
    try:
        result = process_station_message(
            db,
            topic=message.topic,
            payload=bytes(message.payload),
            received_at=datetime.now(timezone.utc),
        )
        db.commit()
        client.ack(message.mid, message.qos)
        LOGGER.info(
            "Processed station message kind=%s node_id=%s inserted=%s",
            result.kind,
            result.node_id,
            result.inserted,
        )
    except StationMessageError as exc:
        db.rollback()
        client.ack(message.mid, message.qos)
        LOGGER.warning(
            "Rejected station message topic=%s reason=%s", message.topic, exc
        )
    except Exception:
        db.rollback()
        LOGGER.exception(
            "Station persistence failed; disconnecting before acknowledgement"
        )
        client.disconnect()
    finally:
        db.close()


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = ConsumerSettings.from_environment()
    client = build_client(settings)
    client.connect(settings.host, settings.port, settings.keepalive_seconds)
    client.loop_forever(retry_first_connection=True)


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _secret(name: str) -> str:
    file_path = os.environ.get(f"{name}_FILE", "").strip()
    inline_value = os.environ.get(name, "").strip()
    if file_path and inline_value:
        raise ValueError(f"configure only one of {name} or {name}_FILE")
    if file_path:
        try:
            value = open(file_path, encoding="utf-8").read().strip()
        except OSError as exc:
            raise ValueError(f"could not read {name}_FILE") from exc
        if value:
            return value
        raise ValueError(f"{name}_FILE must not be empty")
    if inline_value:
        return inline_value
    raise ValueError(f"{name} or {name}_FILE is required")


if __name__ == "__main__":
    main()
