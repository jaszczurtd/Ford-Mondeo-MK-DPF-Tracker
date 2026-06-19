"""Parse and normalize MQTT payloads emitted by the tracker firmware."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from dpf_backend.ingest.models import (
    ActuatorEventRecord,
    JsonObject,
    ParsedMessage,
    RawMqttRecord,
    StatusRecord,
    TelemetryRecord,
)
from dpf_backend.topics import TOPIC_DATA, TOPIC_EVENTS, TOPIC_STATUS


def _none_if_unavailable(value: Any) -> Any:
    if value == -1:
        return None
    return value


def _bool_from_int(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _json_object(payload_text: str) -> tuple[JsonObject | None, str | None]:
    try:
        decoded = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        return None, str(exc)
    if not isinstance(decoded, dict):
        return None, "payload JSON is not an object"
    return decoded, None


def parse_mqtt_message(
    topic: str,
    payload: bytes | str,
    *,
    device_id: str = "dpf-tracker",
    received_at: datetime | None = None,
) -> ParsedMessage:
    """Parse one MQTT message and return raw plus normalized records."""

    if received_at is None:
        received_at = datetime.now(timezone.utc)

    payload_text = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else payload
    payload_json, parse_error = _json_object(payload_text)
    firmware_version = payload_json.get("version") if payload_json is not None else None

    raw = RawMqttRecord(
        received_at=received_at,
        topic=topic,
        payload_text=payload_text,
        payload_json=payload_json,
        parse_ok=parse_error is None,
        parse_error=parse_error,
        firmware_version=firmware_version if isinstance(firmware_version, str) else None,
        device_id=device_id,
    )

    if payload_json is None:
        return ParsedMessage(raw=raw)

    if topic == TOPIC_DATA:
        return ParsedMessage(
            raw=raw,
            telemetry=TelemetryRecord(
                received_at=received_at,
                device_id=device_id,
                payload=normalize_data_payload(payload_json),
            ),
        )

    if topic == TOPIC_EVENTS:
        records = tuple(
            ActuatorEventRecord(
                received_at=received_at,
                device_id=device_id,
                batch_payload=payload_json,
                event_payload=normalize_event_payload(event),
            )
            for event in payload_json.get("events", [])
            if isinstance(event, dict)
        )
        return ParsedMessage(raw=raw, actuator_events=records)

    if topic == TOPIC_STATUS:
        return ParsedMessage(
            raw=raw,
            status=StatusRecord(
                received_at=received_at,
                device_id=device_id,
                payload=normalize_status_payload(payload_json),
            ),
        )

    return ParsedMessage(raw=raw)


def normalize_data_payload(payload: JsonObject) -> JsonObject:
    normalized = dict(payload)
    for key in (
        "gnss_age_ms",
        "gnss_speed_kmh",
        "gnss_alt_m",
        "gnss_course_deg",
        "gnss_hdop",
        "gnss_sats_used",
        "gnss_sats_view",
        "gnss_fix_mode",
        "cell_age_ms",
        "cell_speed_kmh",
    ):
        if key in normalized:
            normalized[key] = _none_if_unavailable(normalized[key])
    return normalized


def normalize_event_payload(payload: JsonObject) -> JsonObject:
    normalized = dict(payload)
    for key in ("gnss_speed_kmh", "dp_sample_age_ms"):
        if key in normalized:
            normalized[key] = _none_if_unavailable(normalized[key])
    return normalized


def normalize_status_payload(payload: JsonObject) -> JsonObject:
    normalized = dict(payload)
    normalized["watchdog_reset"] = normalized.get("status") == "watchdog_reset"
    return normalized


def bool_field(payload: JsonObject, key: str) -> bool | None:
    return _bool_from_int(payload.get(key))

