BEGIN;

CREATE TABLE IF NOT EXISTS telemetry_windows (
    id BIGSERIAL PRIMARY KEY,
    device_id TEXT NOT NULL DEFAULT 'dpf-tracker',
    boot_session_id BIGINT REFERENCES boot_sessions(id) ON DELETE SET NULL,
    bucket_seconds INTEGER NOT NULL CHECK (bucket_seconds > 0),
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    sample_count INTEGER NOT NULL,
    first_received_at TIMESTAMPTZ,
    last_received_at TIMESTAMPTZ,
    first_device_ms BIGINT,
    last_device_ms BIGINT,
    egt_pre_avg DOUBLE PRECISION,
    egt_pre_min DOUBLE PRECISION,
    egt_pre_max DOUBLE PRECISION,
    egt_mid_avg DOUBLE PRECISION,
    egt_mid_min DOUBLE PRECISION,
    egt_mid_max DOUBLE PRECISION,
    egt_mid_slope_c_per_min DOUBLE PRECISION,
    dp_voltage_avg DOUBLE PRECISION,
    dp_voltage_min DOUBLE PRECISION,
    dp_voltage_max DOUBLE PRECISION,
    dp_voltage_slope_v_per_min DOUBLE PRECISION,
    speed_avg_kmh DOUBLE PRECISION,
    speed_max_kmh DOUBLE PRECISION,
    pump_pulse_count INTEGER NOT NULL DEFAULT 0,
    pump_event_count INTEGER NOT NULL DEFAULT 0,
    pump_on_event_count INTEGER NOT NULL DEFAULT 0,
    pump_active_sample_count INTEGER NOT NULL DEFAULT 0,
    glow_event_count INTEGER NOT NULL DEFAULT 0,
    glow_on_event_count INTEGER NOT NULL DEFAULT 0,
    glow_active_sample_count INTEGER NOT NULL DEFAULT 0,
    data_overflow_max BIGINT,
    event_overflow_max BIGINT,
    any_overflow BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (window_end > window_start),
    UNIQUE (device_id, boot_session_id, bucket_seconds, window_start)
);

CREATE INDEX IF NOT EXISTS idx_telemetry_windows_bucket_start
    ON telemetry_windows (bucket_seconds, window_start);

CREATE INDEX IF NOT EXISTS idx_telemetry_windows_device_bucket_start
    ON telemetry_windows (device_id, bucket_seconds, window_start);

CREATE INDEX IF NOT EXISTS idx_telemetry_windows_boot_bucket_start
    ON telemetry_windows (boot_session_id, bucket_seconds, window_start);

INSERT INTO schema_migrations (version)
VALUES ('002_telemetry_windows')
ON CONFLICT (version) DO NOTHING;

COMMIT;
