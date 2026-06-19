"""PostgreSQL persistence for parsed tracker MQTT messages."""

from __future__ import annotations

from contextlib import AbstractContextManager
import json
from types import TracebackType
from typing import Any

from dpf_backend.ingest.models import (
    ActuatorEventRecord,
    ParsedMessage,
    RawMqttRecord,
    StatusRecord,
    TelemetryRecord,
)
from dpf_backend.ingest.parser import bool_field


def _json_dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _get(payload: dict[str, Any], key: str) -> Any:
    return payload.get(key)


class PostgresStore(AbstractContextManager["PostgresStore"]):
    """Small psycopg wrapper used by the MQTT ingestor."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.conn: Any | None = None

    def __enter__(self) -> "PostgresStore":
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - exercised on Pi installs
            raise RuntimeError("psycopg is not installed") from exc
        self.conn = psycopg.connect(self.database_url)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        return None

    def save_message(self, message: ParsedMessage) -> int:
        if self.conn is None:
            raise RuntimeError("PostgresStore is not connected")

        with self.conn.transaction():
            raw_id = self._insert_raw(message.raw)
            if message.telemetry is not None:
                self._insert_telemetry(raw_id, message.telemetry)
            for event in message.actuator_events:
                self._insert_actuator_event(raw_id, event)
            if message.status is not None:
                self._insert_status(raw_id, message.status)
        return raw_id

    def _insert_raw(self, record: RawMqttRecord) -> int:
        assert self.conn is not None
        row = self.conn.execute(
            """
            INSERT INTO raw_mqtt (
                received_at, topic, payload_text, payload_json, parse_ok,
                parse_error, firmware_version, device_id
            )
            VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                record.received_at,
                record.topic,
                record.payload_text,
                _json_dumps(record.payload_json) if record.payload_json is not None else None,
                record.parse_ok,
                record.parse_error,
                record.firmware_version,
                record.device_id,
            ),
        ).fetchone()
        return int(row[0])

    def _insert_telemetry(self, raw_id: int, record: TelemetryRecord) -> None:
        assert self.conn is not None
        p = record.payload
        self.conn.execute(
            """
            INSERT INTO telemetry_data (
                raw_mqtt_id, received_at, device_id, firmware_version,
                firmware_time, device_ms, egt_pre, egt_mid, dp_voltage,
                dp_raw, pump_onoff_period, pump_freq_hz, pump_cnt, pump_state,
                pump_period_ms, pump_last_on_ms, pump_current_on_ms,
                glow_state, glow_last_on_ms, glow_current_on_ms, mcu_temp,
                data_queue_len, data_overflow_count, event_queue_len,
                event_overflow_count, gnss_valid, gnss_powered, gnss_error,
                gnss_age_ms, gnss_lat, gnss_lng, gnss_speed_kmh, gnss_alt_m,
                gnss_course_deg, gnss_hdop, gnss_sats_used, gnss_sats_view,
                gnss_fix_mode, gnss_utc, cell_valid, cell_error, cell_age_ms,
                cell_speed_kmh, cell_lat, cell_lng, cell_acc_m, payload
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s::jsonb
            )
            """,
            (
                raw_id,
                record.received_at,
                record.device_id,
                _get(p, "version"),
                _get(p, "time"),
                _get(p, "ms"),
                _get(p, "egt_pre"),
                _get(p, "egt_mid"),
                _get(p, "dp_voltage"),
                _get(p, "dp_raw"),
                _get(p, "pump_onoff_period"),
                _get(p, "pump_freq_hz"),
                _get(p, "pump_cnt"),
                bool_field(p, "pump"),
                _get(p, "pump_period_ms"),
                _get(p, "pump_last_on_ms"),
                _get(p, "pump_current_on_ms"),
                bool_field(p, "glow"),
                _get(p, "glow_dur"),
                _get(p, "glow_current_on_ms"),
                _get(p, "mcu_temp"),
                _get(p, "data_queue_len"),
                _get(p, "data_overflow_count"),
                _get(p, "event_queue_len"),
                _get(p, "event_overflow_count"),
                bool_field(p, "gnss_valid"),
                bool_field(p, "gnss_powered"),
                _get(p, "gnss_error"),
                _get(p, "gnss_age_ms"),
                _get(p, "gnss_lat"),
                _get(p, "gnss_lng"),
                _get(p, "gnss_speed_kmh"),
                _get(p, "gnss_alt_m"),
                _get(p, "gnss_course_deg"),
                _get(p, "gnss_hdop"),
                _get(p, "gnss_sats_used"),
                _get(p, "gnss_sats_view"),
                _get(p, "gnss_fix_mode"),
                _get(p, "gnss_utc"),
                bool_field(p, "cell_valid"),
                _get(p, "cell_error"),
                _get(p, "cell_age_ms"),
                _get(p, "cell_speed_kmh"),
                _get(p, "cell_lat"),
                _get(p, "cell_lng"),
                _get(p, "cell_acc_m"),
                _json_dumps(p),
            ),
        )

    def _insert_actuator_event(self, raw_id: int, record: ActuatorEventRecord) -> None:
        assert self.conn is not None
        b = record.batch_payload
        e = record.event_payload
        self.conn.execute(
            """
            INSERT INTO actuator_events (
                raw_mqtt_id, received_at, device_id, firmware_version,
                batch_device_ms, batch_count, queue_len,
                queue_remaining_after_batch, overflow_count, seq, t_us, t_ms,
                source, state, gnss_speed_kmh, dp_voltage, dp_sample_age_ms,
                event_payload, batch_payload
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s::jsonb, %s::jsonb
            )
            """,
            (
                raw_id,
                record.received_at,
                record.device_id,
                _get(b, "version"),
                _get(b, "ms"),
                _get(b, "batch_count"),
                _get(b, "queue_len"),
                _get(b, "queue_remaining_after_batch"),
                _get(b, "overflow_count"),
                _get(e, "seq"),
                _get(e, "t_us"),
                _get(e, "t_ms"),
                _get(e, "src"),
                bool_field(e, "state"),
                _get(e, "gnss_speed_kmh"),
                _get(e, "dp_voltage"),
                _get(e, "dp_sample_age_ms"),
                _json_dumps(e),
                _json_dumps(b),
            ),
        )

    def _insert_status(self, raw_id: int, record: StatusRecord) -> None:
        assert self.conn is not None
        p = record.payload
        self.conn.execute(
            """
            INSERT INTO status_events (
                raw_mqtt_id, received_at, device_id, firmware_version,
                device_ms, status, reason, watchdog_reset, payload
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                raw_id,
                record.received_at,
                record.device_id,
                _get(p, "version"),
                _get(p, "ms"),
                _get(p, "status"),
                _get(p, "reason"),
                bool(_get(p, "watchdog_reset")),
                _json_dumps(p),
            ),
        )

