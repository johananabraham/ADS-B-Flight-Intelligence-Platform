"""Bounded MQTT message validation before edge-station persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..schemas.edge import (
    PresenceStatus,
    StationPresence,
    StationTelemetry,
    node_id_from_topic,
)
from .station_persistence import persist_presence, persist_telemetry


MAX_PAYLOAD_BYTES = 4_096


class StationMessageError(ValueError):
    """A rejected station message safe to log without payload contents."""


@dataclass(frozen=True)
class ProcessedStationMessage:
    kind: Literal["telemetry", "presence"]
    node_id: str
    message_id: str
    inserted: bool


def process_station_message(
    db: Session,
    *,
    topic: str,
    payload: bytes,
    received_at: datetime,
) -> ProcessedStationMessage:
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise StationMessageError("station payload exceeds 4096 bytes")
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StationMessageError("station payload is not valid UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise StationMessageError("station payload must be a JSON object")

    kind = _message_kind(topic)
    try:
        if kind == "telemetry":
            message = StationTelemetry.model_validate(document)
            _require_topic_identity(topic, message.node_id, kind)
            inserted = persist_telemetry(db, message, received_at)
        else:
            message = StationPresence.model_validate(document)
            _require_topic_identity(topic, message.node_id, kind)
            if message.status is PresenceStatus.OFFLINE:
                message = message.model_copy(update={"observed_at": received_at})
            inserted = persist_presence(db, message, received_at)
    except ValidationError as exc:
        raise StationMessageError("station payload failed schema validation") from exc
    return ProcessedStationMessage(
        kind=kind,
        node_id=message.node_id,
        message_id=str(message.message_id),
        inserted=inserted,
    )


def _message_kind(topic: str) -> Literal["telemetry", "presence"]:
    if topic.endswith("/telemetry"):
        return "telemetry"
    if topic.endswith("/presence"):
        return "presence"
    raise StationMessageError("unsupported station topic")


def _require_topic_identity(
    topic: str, node_id: str, kind: Literal["telemetry", "presence"]
) -> None:
    try:
        topic_node_id = node_id_from_topic(topic, kind)
    except ValueError as exc:
        raise StationMessageError("invalid station topic") from exc
    if topic_node_id != node_id:
        raise StationMessageError("topic node does not match payload node")
