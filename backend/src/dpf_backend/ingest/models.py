"""Normalized records produced from tracker MQTT payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class RawMqttRecord:
    received_at: datetime
    topic: str
    payload_text: str
    payload_json: JsonObject | None
    parse_ok: bool
    parse_error: str | None
    firmware_version: str | None
    device_id: str


@dataclass(frozen=True)
class TelemetryRecord:
    received_at: datetime
    device_id: str
    payload: JsonObject


@dataclass(frozen=True)
class ActuatorEventRecord:
    received_at: datetime
    device_id: str
    batch_payload: JsonObject
    event_payload: JsonObject


@dataclass(frozen=True)
class StatusRecord:
    received_at: datetime
    device_id: str
    payload: JsonObject


@dataclass(frozen=True)
class ParsedMessage:
    raw: RawMqttRecord
    telemetry: TelemetryRecord | None = None
    actuator_events: tuple[ActuatorEventRecord, ...] = ()
    status: StatusRecord | None = None

