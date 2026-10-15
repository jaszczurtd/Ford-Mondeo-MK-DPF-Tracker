# DPF backend

[Polski](README.pl.md) · [Project overview](../README.md)

The backend stores tracker MQTT messages in PostgreSQL, normalizes telemetry
and actuator events, infers boot sessions, computes analytical windows and
provides a read-only HTTP API. Visualization, regeneration detection, command
publishing, retention and scheduled window refresh are not implemented yet.

Run all commands below from the repository root, one directory above `backend/`.
The [telemetry guide](../docs/TELEMETRY.md) describes firmware fields and limits.

## Install and configure

Use Python 3.11 or newer. The database commands also require PostgreSQL's
`psql` client and an existing database/user with schema creation permissions.
Package dependencies are declared in [pyproject.toml](pyproject.toml).

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -e backend
```

Use [.env.example](.env.example) as a list of settings, replace its sample
values, and keep the private configuration in `/etc/dpf-backend.env`.
Applications load that file automatically; exported shell variables win.
`DPF_ENV_FILE` selects another file. `.env.example` is not loaded automatically,
and the loader does not expand shell expressions or variables in values.

| Setting | Purpose |
| --- | --- |
| `DPF_DATABASE_URL` | PostgreSQL connection URL for the prepared database |
| `DPF_MQTT_HOST`, `DPF_MQTT_PORT` | Broker address; default port 8883 |
| `DPF_MQTT_TLS`, `DPF_MQTT_CA_FILE` | TLS switch and readable CA path |
| `DPF_MQTT_USERNAME`, `DPF_MQTT_PASSWORD` | Broker credentials, if required |
| `DPF_MQTT_CLIENT_ID`, `DPF_DEVICE_ID` | Ingestor client ID and device label stored with records |
| `DPF_API_HOST`, `DPF_API_PORT` | API bind address; defaults to `127.0.0.1:8090` |

Set `DPF_MQTT_CA_FILE` for certificate verification and use a broker address
matching its certificate. With TLS enabled but no CA file, the current ingestor
disables certificate verification. This differs from the tracker's modem setup.
The device ID is assigned by backend configuration; the shared `dpf/*` topics
do not identify several trackers automatically.

## Database and first ingestion

Apply both migrations to the configured database:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/apply_migrations.py
```

The script reads `DPF_DATABASE_URL` through the configuration loader and invokes
`psql`. [001_initial_schema.sql](db/migrations/001_initial_schema.sql) creates
`raw_mqtt`, `boot_sessions`, `telemetry_data`, `actuator_events`, `status_events`
and `schema_migrations`. [002_telemetry_windows.sql](db/migrations/002_telemetry_windows.sql)
adds `telemetry_windows`. Default example credentials are not database provisioning.

For a disposable test database, insert sample records without MQTT:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/ingest_sample.py --topic dpf/data
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/ingest_sample.py --topic dpf/events
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/ingest_sample.py --topic dpf/status
```

These commands write to the configured database. For live collection, run:

```bash
backend/.venv/bin/dpf-mqtt-ingestor
```

The service subscribes to `dpf/data`, `dpf/events` and `dpf/status` at QoS 1.
Storage inserts the raw record, including parse status, then normalized rows
in one transaction. A failed transaction rolls both back; raw insertion is
not a separate durable step. The ingestor does not publish commands.

## Run the ingestor as a service

First confirm foreground collection with real MQTT and database settings.
The [installer](scripts/install_systemd_service.sh) and
[example unit](deploy/dpf-mqtt-ingestor.service.example) assume a Raspberry Pi
account named `pi`. The account needs access to the repository, virtualenv,
CA certificate and `/etc/dpf-backend.env`. For a private root-owned env file,
a read-only group such as `dpf-backend` with mode `0640` can grant access;
add `pi` to that group and use a new login before foreground checks.

Pass the actual absolute repository path:

```bash
bash backend/scripts/install_systemd_service.sh /home/pi/Documents/Ford-Mondeo-MK-DPF-Tracker
sudo systemctl start dpf-mqtt-ingestor
sudo systemctl status dpf-mqtt-ingestor
```

The installer checks for the env file and installed executable, writes the unit
using `sudo`, reloads systemd and **enables autostart**. It does not start the
service; the second command does. Adapt the account and paths before installing
on a host without `pi`. This unit runs only the MQTT ingestor.

## Sessions and analytical windows

New normalized records receive a `boot_session_id`. Session inference starts
a new session for the first record, watchdog status, a decrease in device `ms`
or event `seq`, or a gap over 30 minutes followed by uptime below 5 minutes.
This is a heuristic: delayed or out-of-order messages and counter wraps can
look like a restart. Older unassigned rows may still contain `NULL`.

Refresh both supported window sizes (10 and 60 seconds), or select one:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/refresh_windows.py
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/refresh_windows.py --bucket-seconds 10
```

Windows contain temperature, voltage, speed, pump/glow activity, overflow flags
and slope metrics. They are grouped by **server receive time** within a device
and boot session, so an offline backlog can distort acquisition-time trends.
Refreshing rebuilds the selected size; it is not scheduled automatically.
No regeneration classifier runs as part of this operation.

## Read-only HTTP API

Start the API in the foreground:

```bash
backend/.venv/bin/dpf-api
```

The default address is `127.0.0.1:8090`. No API systemd unit, reverse proxy or
authentication layer is supplied here. Keep deployment exposure separate from
this local read-only workflow.

| Endpoint | Result and optional filters |
| --- | --- |
| `GET /health` | Process health and version; no database query |
| `GET /status` | Database counts and latest receive times |
| `GET /raw-mqtt/recent` | Raw records; `topic`, `device_id`, `limit` |
| `GET /telemetry` | Telemetry; `from`, `to`, `device_id`, `boot_session_id`, `limit` |
| `GET /windows` | Windows; `bucket_seconds`, `from`, `to`, `device_id`, `boot_session_id`, `limit` |
| `GET /boot-sessions` | Sessions; `device_id`, `limit` |

List responses contain `count` and `rows`. `limit` defaults to 100 and accepts
1–1000. Time filters use ISO 8601 timestamps: telemetry filters `received_at`,
windows filter `window_start`. The default window size is 10 seconds; only
sizes actually generated have rows. Database errors produce HTTP 503.

```bash
curl 'http://127.0.0.1:8090/health'
curl 'http://127.0.0.1:8090/telemetry?limit=100&from=2026-06-20T10:00:00Z&to=2026-06-20T11:00:00Z'
```

## Checks and Raspberry Pi diagnostics

Host tests and SQL validation do not connect to a live database or broker:

```bash
python3 -m compileall backend/src backend/tests
python3 backend/scripts/run_unit_tests.py
python3 backend/scripts/validate_migrations.py
PYTHONPATH=backend/src python3 -m dpf_backend.ingest.mqtt_ingestor --help
PYTHONPATH=backend/src python3 -m dpf_backend.api.server --help
```

On the deployed Pi, run the separate diagnostic:

```bash
backend/.venv/bin/python backend/scripts/diagnose_pi.py
```

It checks the environment, commands, PostgreSQL connection, migrations/tables,
row counts, ingest freshness, session assignment, windows, the ingestor service
and API endpoints. Use `--skip-api` or `--skip-systemd` for a partial deployment,
`--stale-after-seconds 600` to choose the freshness threshold, or
`--strict-warnings` to make warnings fail the command. A `FAIL` always returns
a nonzero status; warnings alone normally return zero.

Unit tests and migration validation do not prove that database migrations,
service autostart, live MQTT or the API work on the deployment host.
