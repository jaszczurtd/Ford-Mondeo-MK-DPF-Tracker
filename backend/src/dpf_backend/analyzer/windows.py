"""Refresh analytical telemetry windows."""

from __future__ import annotations

from contextlib import AbstractContextManager
from types import TracebackType
from typing import Any


WINDOW_BUCKET_SECONDS = (10, 60)


class WindowRefresher(AbstractContextManager["WindowRefresher"]):
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.conn: Any | None = None

    def __enter__(self) -> "WindowRefresher":
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

    def refresh_bucket(self, bucket_seconds: int) -> int:
        if bucket_seconds <= 0:
            raise ValueError("bucket_seconds must be positive")
        if self.conn is None:
            raise RuntimeError("WindowRefresher is not connected")

        with self.conn.transaction():
            self.conn.execute(
                "DELETE FROM telemetry_windows WHERE bucket_seconds = %s",
                (bucket_seconds,),
            )
            row = self.conn.execute(
                REFRESH_WINDOWS_SQL,
                (
                    bucket_seconds,
                    bucket_seconds,
                    bucket_seconds,
                    bucket_seconds,
                    bucket_seconds,
                    bucket_seconds,
                    bucket_seconds,
                    bucket_seconds,
                ),
            ).fetchone()
        return int(row[0])


REFRESH_WINDOWS_SQL = """
WITH telemetry_base AS (
    SELECT
        t.*,
        to_timestamp(
            floor(extract(epoch FROM t.received_at) / %s) * %s
        ) AS window_start,
        first_value(t.egt_mid) OVER w AS first_egt_mid,
        last_value(t.egt_mid) OVER w AS last_egt_mid,
        first_value(t.dp_voltage) OVER w AS first_dp_voltage,
        last_value(t.dp_voltage) OVER w AS last_dp_voltage
    FROM telemetry_data t
    WINDOW w AS (
        PARTITION BY
            t.device_id,
            t.boot_session_id,
            to_timestamp(floor(extract(epoch FROM t.received_at) / %s) * %s)
        ORDER BY t.received_at
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    )
),
telemetry_agg AS (
    SELECT
        device_id,
        boot_session_id,
        window_start,
        window_start + make_interval(secs => %s) AS window_end,
        count(*)::integer AS sample_count,
        min(received_at) AS first_received_at,
        max(received_at) AS last_received_at,
        min(device_ms) AS first_device_ms,
        max(device_ms) AS last_device_ms,
        avg(egt_pre) AS egt_pre_avg,
        min(egt_pre) AS egt_pre_min,
        max(egt_pre) AS egt_pre_max,
        avg(egt_mid) AS egt_mid_avg,
        min(egt_mid) AS egt_mid_min,
        max(egt_mid) AS egt_mid_max,
        CASE
            WHEN max(device_ms) > min(device_ms)
            THEN ((max(last_egt_mid) - max(first_egt_mid)) /
                  ((max(device_ms) - min(device_ms)) / 60000.0))
            ELSE NULL
        END AS egt_mid_slope_c_per_min,
        avg(dp_voltage) AS dp_voltage_avg,
        min(dp_voltage) AS dp_voltage_min,
        max(dp_voltage) AS dp_voltage_max,
        CASE
            WHEN max(device_ms) > min(device_ms)
            THEN ((max(last_dp_voltage) - max(first_dp_voltage)) /
                  ((max(device_ms) - min(device_ms)) / 60000.0))
            ELSE NULL
        END AS dp_voltage_slope_v_per_min,
        avg(COALESCE(gnss_speed_kmh, cell_speed_kmh)) AS speed_avg_kmh,
        max(COALESCE(gnss_speed_kmh, cell_speed_kmh)) AS speed_max_kmh,
        COALESCE(sum(pump_cnt), 0)::integer AS pump_pulse_count,
        count(*) FILTER (WHERE pump_state)::integer AS pump_active_sample_count,
        count(*) FILTER (WHERE glow_state)::integer AS glow_active_sample_count,
        max(data_overflow_count) AS data_overflow_max,
        max(event_overflow_count) AS event_overflow_max,
        bool_or(COALESCE(data_overflow_count, 0) > 0 OR
                COALESCE(event_overflow_count, 0) > 0) AS any_overflow
    FROM telemetry_base
    GROUP BY device_id, boot_session_id, window_start
),
event_agg AS (
    SELECT
        device_id,
        boot_session_id,
        to_timestamp(floor(extract(epoch FROM received_at) / %s) * %s) AS window_start,
        count(*) FILTER (WHERE source = 'pump')::integer AS pump_event_count,
        count(*) FILTER (WHERE source = 'pump' AND state)::integer AS pump_on_event_count,
        count(*) FILTER (WHERE source = 'glow')::integer AS glow_event_count,
        count(*) FILTER (WHERE source = 'glow' AND state)::integer AS glow_on_event_count
    FROM actuator_events
    GROUP BY device_id, boot_session_id, window_start
),
inserted AS (
INSERT INTO telemetry_windows (
    device_id, boot_session_id, bucket_seconds, window_start, window_end,
    sample_count, first_received_at, last_received_at, first_device_ms,
    last_device_ms, egt_pre_avg, egt_pre_min, egt_pre_max, egt_mid_avg,
    egt_mid_min, egt_mid_max, egt_mid_slope_c_per_min, dp_voltage_avg,
    dp_voltage_min, dp_voltage_max, dp_voltage_slope_v_per_min,
    speed_avg_kmh, speed_max_kmh, pump_pulse_count, pump_event_count,
    pump_on_event_count, pump_active_sample_count, glow_event_count,
    glow_on_event_count, glow_active_sample_count, data_overflow_max,
    event_overflow_max, any_overflow
)
SELECT
    t.device_id,
    t.boot_session_id,
    %s AS bucket_seconds,
    t.window_start,
    t.window_end,
    t.sample_count,
    t.first_received_at,
    t.last_received_at,
    t.first_device_ms,
    t.last_device_ms,
    t.egt_pre_avg,
    t.egt_pre_min,
    t.egt_pre_max,
    t.egt_mid_avg,
    t.egt_mid_min,
    t.egt_mid_max,
    t.egt_mid_slope_c_per_min,
    t.dp_voltage_avg,
    t.dp_voltage_min,
    t.dp_voltage_max,
    t.dp_voltage_slope_v_per_min,
    t.speed_avg_kmh,
    t.speed_max_kmh,
    t.pump_pulse_count,
    COALESCE(e.pump_event_count, 0),
    COALESCE(e.pump_on_event_count, 0),
    t.pump_active_sample_count,
    COALESCE(e.glow_event_count, 0),
    COALESCE(e.glow_on_event_count, 0),
    t.glow_active_sample_count,
    t.data_overflow_max,
    t.event_overflow_max,
    t.any_overflow
FROM telemetry_agg t
LEFT JOIN event_agg e
  ON e.device_id = t.device_id
 AND e.boot_session_id IS NOT DISTINCT FROM t.boot_session_id
 AND e.window_start = t.window_start
ORDER BY t.device_id, t.boot_session_id, t.window_start
RETURNING id
)
SELECT count(*) FROM inserted
"""
