# DPF Backend

Backend services for the Ford Mondeo MK4 DPF tracker.

The backend is built in stages. Current code includes the project skeleton,
database schema, MQTT parsing, PostgreSQL storage, and an MQTT ingestor entry
point.

## Planned Services

- MQTT ingestor for `dpf/data`, `dpf/events`, and `dpf/status`.
- Raw MQTT persistence before interpretation.
- Normalized storage for telemetry, actuator events, status events, and boot
  sessions.
- Analytical workers for windows, summaries, and regeneration cycle detection.
- FastAPI API and an nginx-served visualization frontend.

## Current Stage

Stage 4 provides:

- Python package layout under `src/dpf_backend/`.
- Configuration loader based on environment variables.
- Placeholder modules for ingest, storage, analyzer, and API layers.
- Local verification that the package imports and compiles.
- PostgreSQL migration SQL under `db/migrations/`.
- A stdlib-only migration validator.
- A `psql`-based migration apply script for the Raspberry Pi.
- MQTT payload parser and normalizer.
- PostgreSQL storage path for raw and normalized records.
- MQTT ingestor CLI entry point.
- Sample ingestion script for database verification without MQTT.
- Online boot/session detection for newly ingested records.
- `boot_session_id` assignment for telemetry, actuator, and status rows.

## Database Migrations

The first migration creates:

- `raw_mqtt`
- `boot_sessions`
- `telemetry_data`
- `actuator_events`
- `status_events`
- `schema_migrations`

Apply migrations with:

```bash
PYTHONPATH=backend/src python3 backend/scripts/apply_migrations.py
```

The script reads `DPF_DATABASE_URL`, or the default from `.env.example`, and
uses the `psql` command-line client.

## MQTT Ingestor

Install runtime dependencies in a virtual environment:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -e backend
```

Insert sample payloads into PostgreSQL without MQTT:

```bash
export DPF_DATABASE_URL='postgresql://dpf_backend:CHANGE_ME@localhost:5432/dpf_backend'
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/ingest_sample.py --topic dpf/data
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/ingest_sample.py --topic dpf/events
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/ingest_sample.py --topic dpf/status
```

Run the ingestor in the foreground:

```bash
export DPF_DATABASE_URL='postgresql://dpf_backend:CHANGE_ME@localhost:5432/dpf_backend'
export DPF_MQTT_HOST='CHANGE_ME_CERT_HOST_OR_IP'
backend/.venv/bin/dpf-mqtt-ingestor
```

When TLS verification is enabled with `DPF_MQTT_CA_FILE`, `DPF_MQTT_HOST` must
match the hostname or IP address in the Mosquitto certificate. Do not use
`localhost` unless the certificate is valid for `localhost`.

An example systemd unit is available at
`backend/deploy/dpf-mqtt-ingestor.service.example`.

## Boot Sessions

The ingestor assigns new normalized rows to `boot_sessions`. A new session is
started when the backend sees one of these restart signals:

- first message for a device,
- watchdog reset status,
- firmware uptime `ms` drops,
- actuator event `seq` drops,
- long wall-clock gap followed by small firmware uptime.

Existing rows collected before Stage 4 may still have `boot_session_id = NULL`.

## Verification

From the repository root:

```bash
python3 -m compileall backend/src backend/tests
PYTHONPATH=backend/src python3 -c "import dpf_backend; print(dpf_backend.__version__)"
python3 backend/scripts/run_unit_tests.py
python3 backend/scripts/validate_migrations.py
PYTHONPATH=backend/src python3 -m dpf_backend.ingest.mqtt_ingestor --help
PYTHONPATH=backend/src python3 backend/scripts/ingest_sample.py --help
```
