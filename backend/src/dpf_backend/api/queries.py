"""Read-only PostgreSQL queries for the HTTP API."""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime
from types import TracebackType
from typing import Any


DEFAULT_LIMIT = 100
MAX_LIMIT = 1000


def clamp_limit(value: int | None, default: int = DEFAULT_LIMIT) -> int:
    """Clamp user-provided row limits to a bounded positive range."""

    if value is None:
        return default
    return max(1, min(int(value), MAX_LIMIT))


def _add_time_range(
    clauses: list[str],
    params: list[Any],
    column: str,
    from_ts: datetime | None,
    to_ts: datetime | None,
) -> None:
    if from_ts is not None:
        clauses.append(f"{column} >= %s")
        params.append(from_ts)
    if to_ts is not None:
        clauses.append(f"{column} <= %s")
        params.append(to_ts)


def _where_sql(clauses: list[str]) -> str:
    if not clauses:
        return ""
    return " WHERE " + " AND ".join(clauses)


class ApiStore(AbstractContextManager["ApiStore"]):
    """Small read-only psycopg wrapper used by FastAPI handlers."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.conn: Any | None = None

    def __enter__(self) -> "ApiStore":
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - exercised on Pi installs
            raise RuntimeError("psycopg is not installed") from exc
        self.conn = psycopg.connect(self.database_url, row_factory=dict_row)
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

    def backend_status(self) -> dict[str, Any]:
        if self.conn is None:
            raise RuntimeError("ApiStore is not connected")
        row = self.conn.execute(
            """
            SELECT
                (SELECT count(*) FROM raw_mqtt) AS raw_mqtt_count,
                (SELECT count(*) FROM telemetry_data) AS telemetry_count,
                (SELECT count(*) FROM actuator_events) AS actuator_event_count,
                (SELECT count(*) FROM status_events) AS status_event_count,
                (SELECT count(*) FROM boot_sessions) AS boot_session_count,
                (SELECT max(received_at) FROM raw_mqtt) AS latest_raw_received_at,
                (SELECT max(received_at) FROM telemetry_data) AS latest_telemetry_received_at,
                (SELECT max(received_at) FROM actuator_events) AS latest_event_received_at
            """
        ).fetchone()
        return dict(row)

    def recent_raw_mqtt(
        self,
        *,
        limit: int | None = None,
        topic: str | None = None,
        device_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if self.conn is None:
            raise RuntimeError("ApiStore is not connected")
        clauses: list[str] = []
        params: list[Any] = []
        if topic:
            clauses.append("topic = %s")
            params.append(topic)
        if device_id:
            clauses.append("device_id = %s")
            params.append(device_id)
        params.append(clamp_limit(limit))
        rows = self.conn.execute(
            f"""
            SELECT id, received_at, topic, parse_ok, parse_error,
                   firmware_version, device_id, payload_json, payload_text
            FROM raw_mqtt
            {_where_sql(clauses)}
            ORDER BY received_at DESC, id DESC
            LIMIT %s
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def telemetry_rows(
        self,
        *,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        limit: int | None = None,
        device_id: str | None = None,
        boot_session_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if self.conn is None:
            raise RuntimeError("ApiStore is not connected")
        clauses: list[str] = []
        params: list[Any] = []
        _add_time_range(clauses, params, "received_at", from_ts, to_ts)
        if device_id:
            clauses.append("device_id = %s")
            params.append(device_id)
        if boot_session_id is not None:
            clauses.append("boot_session_id = %s")
            params.append(boot_session_id)
        params.append(clamp_limit(limit))
        rows = self.conn.execute(
            f"""
            SELECT id, received_at, device_id, boot_session_id,
                   firmware_version, firmware_time, device_ms,
                   egt_pre, egt_mid, dp_voltage, dp_raw,
                   pump_freq_hz, pump_cnt, pump_state, pump_period_ms,
                   pump_last_on_ms, pump_current_on_ms,
                   glow_state, glow_last_on_ms, glow_current_on_ms,
                   mcu_temp, data_queue_len, data_overflow_count,
                   event_queue_len, event_overflow_count,
                   gnss_valid, gnss_age_ms, gnss_lat, gnss_lng,
                   gnss_speed_kmh, cell_valid, cell_age_ms,
                   cell_speed_kmh, cell_lat, cell_lng, cell_acc_m
            FROM telemetry_data
            {_where_sql(clauses)}
            ORDER BY received_at DESC, id DESC
            LIMIT %s
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def telemetry_windows(
        self,
        *,
        bucket_seconds: int,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        limit: int | None = None,
        device_id: str | None = None,
        boot_session_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if self.conn is None:
            raise RuntimeError("ApiStore is not connected")
        clauses: list[str] = ["bucket_seconds = %s"]
        params: list[Any] = [bucket_seconds]
        _add_time_range(clauses, params, "window_start", from_ts, to_ts)
        if device_id:
            clauses.append("device_id = %s")
            params.append(device_id)
        if boot_session_id is not None:
            clauses.append("boot_session_id = %s")
            params.append(boot_session_id)
        params.append(clamp_limit(limit))
        rows = self.conn.execute(
            f"""
            SELECT id, device_id, boot_session_id, bucket_seconds,
                   window_start, window_end, sample_count,
                   first_received_at, last_received_at,
                   first_device_ms, last_device_ms,
                   egt_pre_avg, egt_pre_min, egt_pre_max,
                   egt_mid_avg, egt_mid_min, egt_mid_max,
                   egt_mid_slope_c_per_min,
                   dp_voltage_avg, dp_voltage_min, dp_voltage_max,
                   dp_voltage_slope_v_per_min,
                   speed_avg_kmh, speed_max_kmh,
                   pump_pulse_count, pump_event_count, pump_on_event_count,
                   pump_active_sample_count, glow_event_count,
                   glow_on_event_count, glow_active_sample_count,
                   data_overflow_max, event_overflow_max, any_overflow
            FROM telemetry_windows
            {_where_sql(clauses)}
            ORDER BY window_start DESC, id DESC
            LIMIT %s
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def boot_sessions(
        self,
        *,
        limit: int | None = None,
        device_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if self.conn is None:
            raise RuntimeError("ApiStore is not connected")
        clauses: list[str] = []
        params: list[Any] = []
        if device_id:
            clauses.append("device_id = %s")
            params.append(device_id)
        params.append(clamp_limit(limit))
        rows = self.conn.execute(
            f"""
            SELECT id, device_id, started_at, ended_at, first_device_ms,
                   last_device_ms, first_event_seq, last_event_seq,
                   start_reason, watchdog_reset, notes, created_at, updated_at
            FROM boot_sessions
            {_where_sql(clauses)}
            ORDER BY started_at DESC, id DESC
            LIMIT %s
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]
