BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw_mqtt (
    id BIGSERIAL PRIMARY KEY,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    topic TEXT NOT NULL,
    payload_text TEXT NOT NULL,
    payload_json JSONB,
    parse_ok BOOLEAN NOT NULL DEFAULT false,
    parse_error TEXT,
    firmware_version TEXT,
    device_id TEXT NOT NULL DEFAULT 'dpf-tracker'
);

CREATE INDEX IF NOT EXISTS idx_raw_mqtt_received_at
    ON raw_mqtt (received_at);

CREATE INDEX IF NOT EXISTS idx_raw_mqtt_topic_received_at
    ON raw_mqtt (topic, received_at);

CREATE INDEX IF NOT EXISTS idx_raw_mqtt_device_received_at
    ON raw_mqtt (device_id, received_at);

CREATE TABLE IF NOT EXISTS boot_sessions (
    id BIGSERIAL PRIMARY KEY,
    device_id TEXT NOT NULL DEFAULT 'dpf-tracker',
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    first_device_ms BIGINT,
    last_device_ms BIGINT,
    first_event_seq BIGINT,
    last_event_seq BIGINT,
    start_reason TEXT NOT NULL DEFAULT 'unknown',
    watchdog_reset BOOLEAN NOT NULL DEFAULT false,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE INDEX IF NOT EXISTS idx_boot_sessions_device_started_at
    ON boot_sessions (device_id, started_at);

CREATE INDEX IF NOT EXISTS idx_boot_sessions_watchdog_reset
    ON boot_sessions (watchdog_reset)
    WHERE watchdog_reset;

CREATE TABLE IF NOT EXISTS telemetry_data (
    id BIGSERIAL PRIMARY KEY,
    raw_mqtt_id BIGINT REFERENCES raw_mqtt(id) ON DELETE SET NULL,
    boot_session_id BIGINT REFERENCES boot_sessions(id) ON DELETE SET NULL,
    received_at TIMESTAMPTZ NOT NULL,
    device_id TEXT NOT NULL DEFAULT 'dpf-tracker',
    firmware_version TEXT,
    firmware_time TEXT,
    device_ms BIGINT NOT NULL,
    egt_pre DOUBLE PRECISION,
    egt_mid DOUBLE PRECISION,
    dp_voltage DOUBLE PRECISION,
    dp_raw INTEGER,
    pump_onoff_period DOUBLE PRECISION,
    pump_freq_hz DOUBLE PRECISION,
    pump_cnt INTEGER,
    pump_state BOOLEAN,
    pump_period_ms BIGINT,
    pump_last_on_ms BIGINT,
    pump_current_on_ms BIGINT,
    glow_state BOOLEAN,
    glow_last_on_ms BIGINT,
    glow_current_on_ms BIGINT,
    mcu_temp DOUBLE PRECISION,
    data_queue_len INTEGER,
    data_overflow_count BIGINT,
    event_queue_len INTEGER,
    event_overflow_count BIGINT,
    gnss_valid BOOLEAN,
    gnss_powered BOOLEAN,
    gnss_error INTEGER,
    gnss_age_ms BIGINT,
    gnss_lat DOUBLE PRECISION,
    gnss_lng DOUBLE PRECISION,
    gnss_speed_kmh DOUBLE PRECISION,
    gnss_alt_m DOUBLE PRECISION,
    gnss_course_deg DOUBLE PRECISION,
    gnss_hdop DOUBLE PRECISION,
    gnss_sats_used INTEGER,
    gnss_sats_view INTEGER,
    gnss_fix_mode INTEGER,
    gnss_utc TEXT,
    cell_valid BOOLEAN,
    cell_error INTEGER,
    cell_age_ms BIGINT,
    cell_speed_kmh DOUBLE PRECISION,
    cell_lat DOUBLE PRECISION,
    cell_lng DOUBLE PRECISION,
    cell_acc_m DOUBLE PRECISION,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_telemetry_data_received_at
    ON telemetry_data (received_at);

CREATE INDEX IF NOT EXISTS idx_telemetry_data_device_ms
    ON telemetry_data (device_id, device_ms);

CREATE INDEX IF NOT EXISTS idx_telemetry_data_boot_received_at
    ON telemetry_data (boot_session_id, received_at);

CREATE TABLE IF NOT EXISTS actuator_events (
    id BIGSERIAL PRIMARY KEY,
    raw_mqtt_id BIGINT REFERENCES raw_mqtt(id) ON DELETE SET NULL,
    boot_session_id BIGINT REFERENCES boot_sessions(id) ON DELETE SET NULL,
    received_at TIMESTAMPTZ NOT NULL,
    device_id TEXT NOT NULL DEFAULT 'dpf-tracker',
    firmware_version TEXT,
    batch_device_ms BIGINT,
    batch_count INTEGER,
    queue_len INTEGER,
    queue_remaining_after_batch INTEGER,
    overflow_count BIGINT,
    seq BIGINT NOT NULL,
    t_us BIGINT NOT NULL,
    t_ms BIGINT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('pump', 'glow', 'unknown')),
    state BOOLEAN NOT NULL,
    gnss_speed_kmh DOUBLE PRECISION,
    dp_voltage DOUBLE PRECISION,
    dp_sample_age_ms INTEGER,
    event_payload JSONB NOT NULL,
    batch_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_actuator_events_received_at
    ON actuator_events (received_at);

CREATE INDEX IF NOT EXISTS idx_actuator_events_device_t_ms
    ON actuator_events (device_id, t_ms);

CREATE INDEX IF NOT EXISTS idx_actuator_events_boot_t_ms
    ON actuator_events (boot_session_id, t_ms);

CREATE INDEX IF NOT EXISTS idx_actuator_events_source_t_ms
    ON actuator_events (source, t_ms);

CREATE UNIQUE INDEX IF NOT EXISTS uq_actuator_events_boot_seq
    ON actuator_events (device_id, boot_session_id, seq)
    WHERE boot_session_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS status_events (
    id BIGSERIAL PRIMARY KEY,
    raw_mqtt_id BIGINT REFERENCES raw_mqtt(id) ON DELETE SET NULL,
    boot_session_id BIGINT REFERENCES boot_sessions(id) ON DELETE SET NULL,
    received_at TIMESTAMPTZ NOT NULL,
    device_id TEXT NOT NULL DEFAULT 'dpf-tracker',
    firmware_version TEXT,
    device_ms BIGINT,
    status TEXT NOT NULL,
    reason TEXT,
    watchdog_reset BOOLEAN NOT NULL DEFAULT false,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_status_events_received_at
    ON status_events (received_at);

CREATE INDEX IF NOT EXISTS idx_status_events_status_received_at
    ON status_events (status, received_at);

CREATE INDEX IF NOT EXISTS idx_status_events_watchdog_reset
    ON status_events (watchdog_reset)
    WHERE watchdog_reset;

INSERT INTO schema_migrations (version)
VALUES ('001_initial_schema')
ON CONFLICT (version) DO NOTHING;

COMMIT;
