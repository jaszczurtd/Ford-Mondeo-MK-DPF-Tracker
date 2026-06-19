# DPF Backend

Backend services for the Ford Mondeo MK4 DPF tracker.

The backend will be built in stages. The first stage only creates the project
skeleton; it does not connect to MQTT or PostgreSQL yet.

## Planned Services

- MQTT ingestor for `dpf/data`, `dpf/events`, and `dpf/status`.
- Raw MQTT persistence before interpretation.
- Normalized storage for telemetry, actuator events, status events, and boot
  sessions.
- Analytical workers for windows, summaries, and regeneration cycle detection.
- FastAPI API and an nginx-served visualization frontend.

## Current Stage

Stage 2 provides:

- Python package layout under `src/dpf_backend/`.
- Configuration loader based on environment variables.
- Placeholder modules for ingest, storage, analyzer, and API layers.
- Local verification that the package imports and compiles.
- PostgreSQL migration SQL under `db/migrations/`.
- A stdlib-only migration validator.
- A `psql`-based migration apply script for the Raspberry Pi.

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

## Verification

From the repository root:

```bash
python3 -m compileall backend/src backend/tests
PYTHONPATH=backend/src python3 -c "import dpf_backend; print(dpf_backend.__version__)"
python3 backend/scripts/validate_migrations.py
```
