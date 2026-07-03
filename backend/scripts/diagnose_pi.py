#!/usr/bin/env python3
"""Diagnose the Raspberry Pi deployment of the DPF backend."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_SRC = REPO_ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from dpf_backend.config import DEFAULT_ENV_FILE, load_settings  # noqa: E402


SERVICE_NAME = "dpf-mqtt-ingestor"
EXPECTED_MIGRATIONS = ("001_initial_schema", "002_telemetry_windows")
REQUIRED_TABLES = (
    "raw_mqtt",
    "boot_sessions",
    "telemetry_data",
    "actuator_events",
    "status_events",
    "telemetry_windows",
    "schema_migrations",
)
API_ENDPOINTS = (
    "/health",
    "/status",
    "/raw-mqtt/recent?limit=1",
    "/telemetry?limit=1",
    "/windows?bucket_seconds=10&limit=1",
    "/boot-sessions?limit=1",
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str


class Reporter:
    def __init__(self) -> None:
        self.results: list[CheckResult] = []

    def add(self, name: str, status: str, detail: str) -> None:
        self.results.append(CheckResult(name=name, status=status, detail=detail))
        print(f"{status:4} {name}: {detail}")

    def pass_(self, name: str, detail: str) -> None:
        self.add(name, "PASS", detail)

    def warn(self, name: str, detail: str) -> None:
        self.add(name, "WARN", detail)

    def fail(self, name: str, detail: str) -> None:
        self.add(name, "FAIL", detail)

    def skip(self, name: str, detail: str) -> None:
        self.add(name, "SKIP", detail)

    def exit_code(self, *, strict_warnings: bool = False) -> int:
        if any(result.status == "FAIL" for result in self.results):
            return 1
        if strict_warnings and any(result.status == "WARN" for result in self.results):
            return 1
        return 0


def run_command(
    args: list[str],
    *,
    timeout: float = 10.0,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        detail = stderr or f"timed out after {timeout}s"
        return subprocess.CompletedProcess(args, 124, stdout, detail)


def psql_query(database_url: str, sql: str, *, timeout: float = 10.0) -> tuple[int, str, str]:
    psql = shutil.which("psql")
    if psql is None:
        return 127, "", "psql not found. Install postgresql-client."
    result = run_command(
        [psql, database_url, "-v", "ON_ERROR_STOP=1", "-At", "-F", "\t", "-c", sql],
        timeout=timeout,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def split_tsv_rows(output: str) -> list[list[str]]:
    if not output:
        return []
    return [line.split("\t") for line in output.splitlines()]


def api_host_for_local_check(host: str) -> str:
    if host in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    return host


def fetch_json(url: str, *, timeout: float) -> tuple[int, Any | None, str]:
    try:
        with urlopen(url, timeout=timeout) as response:  # noqa: S310 - local operator check
            body = response.read().decode("utf-8")
            return response.status, json.loads(body), ""
    except URLError as exc:
        return 0, None, str(exc)
    except json.JSONDecodeError as exc:
        return 0, None, f"invalid JSON: {exc}"
    except TimeoutError:
        return 0, None, "request timed out"


def check_environment(reporter: Reporter) -> None:
    env_file = Path(DEFAULT_ENV_FILE)
    if env_file.exists():
        reporter.pass_("env file", f"{DEFAULT_ENV_FILE} exists")
    else:
        reporter.warn(
            "env file",
            f"{DEFAULT_ENV_FILE} is missing; defaults or exported variables will be used",
        )

    settings = load_settings()
    reporter.pass_(
        "settings",
        (
            f"device={settings.device_id} mqtt={settings.mqtt_host}:{settings.mqtt_port} "
            f"api={settings.api_host}:{settings.api_port}"
        ),
    )

    for command in ("psql", "systemctl"):
        path = shutil.which(command)
        if path:
            reporter.pass_(f"command {command}", path)
        else:
            level = reporter.fail if command == "psql" else reporter.warn
            level(f"command {command}", "not found")


def check_database(
    reporter: Reporter,
    *,
    database_url: str,
    stale_after_seconds: int,
    query_timeout: float,
) -> None:
    code, output, error = psql_query(
        database_url,
        "SELECT current_database(), current_user;",
        timeout=query_timeout,
    )
    if code != 0:
        reporter.fail("database connection", error or output)
        return
    rows = split_tsv_rows(output)
    if rows and len(rows[0]) >= 2:
        reporter.pass_("database connection", f"database={rows[0][0]} user={rows[0][1]}")
    else:
        reporter.pass_("database connection", "connected")

    table_sql = "\nUNION ALL\n".join(
        f"SELECT '{table}', to_regclass('public.{table}') IS NOT NULL"
        for table in REQUIRED_TABLES
    )
    code, output, error = psql_query(database_url, table_sql, timeout=query_timeout)
    if code != 0:
        reporter.fail("database tables", error or output)
    else:
        table_rows = split_tsv_rows(output)
        missing = [name for name, present in table_rows if present != "t"]
        if missing:
            reporter.fail("database tables", f"missing: {', '.join(missing)}")
        else:
            reporter.pass_("database tables", f"{len(table_rows)} required table(s) exist")

    code, output, error = psql_query(
        database_url,
        "SELECT version FROM schema_migrations ORDER BY version;",
        timeout=query_timeout,
    )
    if code != 0:
        reporter.fail("migrations", error or output)
    else:
        versions = [row[0] for row in split_tsv_rows(output)]
        missing = [version for version in EXPECTED_MIGRATIONS if version not in versions]
        if missing:
            reporter.fail("migrations", f"missing: {', '.join(missing)}")
        else:
            reporter.pass_("migrations", ", ".join(versions))

    status_sql = """
        SELECT
            (SELECT count(*) FROM raw_mqtt),
            (SELECT count(*) FROM telemetry_data),
            (SELECT count(*) FROM actuator_events),
            (SELECT count(*) FROM status_events),
            (SELECT count(*) FROM boot_sessions),
            COALESCE(EXTRACT(EPOCH FROM (now() - (SELECT max(received_at) FROM raw_mqtt)))::bigint, -1),
            COALESCE(EXTRACT(EPOCH FROM (now() - (SELECT max(received_at) FROM telemetry_data)))::bigint, -1),
            COALESCE((SELECT count(*) FROM telemetry_data WHERE boot_session_id IS NULL), 0),
            COALESCE((SELECT count(*) FROM actuator_events WHERE boot_session_id IS NULL), 0),
            COALESCE((SELECT count(*) FROM telemetry_windows WHERE bucket_seconds = 10), 0),
            COALESCE((SELECT count(*) FROM telemetry_windows WHERE bucket_seconds = 60), 0),
            COALESCE(EXTRACT(EPOCH FROM (now() - (SELECT max(window_end) FROM telemetry_windows)))::bigint, -1)
    """
    code, output, error = psql_query(database_url, status_sql, timeout=query_timeout)
    if code != 0:
        reporter.fail("database data", error or output)
        return

    rows = split_tsv_rows(output)
    if not rows or len(rows[0]) < 12:
        reporter.fail("database data", "unexpected psql output")
        return

    (
        raw_count,
        telemetry_count,
        event_count,
        status_count,
        session_count,
        raw_age,
        telemetry_age,
        telemetry_null_sessions,
        event_null_sessions,
        windows_10_count,
        windows_60_count,
        latest_window_age,
    ) = rows[0]
    reporter.pass_(
        "row counts",
        (
            f"raw={raw_count} telemetry={telemetry_count} events={event_count} "
            f"status={status_count} sessions={session_count}"
        ),
    )

    raw_age_i = int(raw_age)
    telemetry_age_i = int(telemetry_age)
    if raw_age_i < 0:
        reporter.warn("raw ingest freshness", "no raw MQTT rows found")
    elif raw_age_i > stale_after_seconds:
        reporter.warn("raw ingest freshness", f"latest raw row is {raw_age_i}s old")
    else:
        reporter.pass_("raw ingest freshness", f"latest raw row is {raw_age_i}s old")

    if telemetry_age_i < 0:
        reporter.warn("telemetry freshness", "no telemetry rows found")
    elif telemetry_age_i > stale_after_seconds:
        reporter.warn("telemetry freshness", f"latest telemetry row is {telemetry_age_i}s old")
    else:
        reporter.pass_("telemetry freshness", f"latest telemetry row is {telemetry_age_i}s old")

    null_session_total = int(telemetry_null_sessions) + int(event_null_sessions)
    if null_session_total:
        reporter.warn(
            "boot session assignment",
            (
                f"telemetry_null={telemetry_null_sessions} "
                f"event_null={event_null_sessions}; older Stage 3 rows may explain this"
            ),
        )
    else:
        reporter.pass_("boot session assignment", "telemetry/events have boot_session_id")

    if int(windows_10_count) == 0 or int(windows_60_count) == 0:
        reporter.warn(
            "telemetry windows",
            f"10s={windows_10_count} 60s={windows_60_count}; run refresh_windows.py if needed",
        )
    else:
        reporter.pass_("telemetry windows", f"10s={windows_10_count} 60s={windows_60_count}")

    latest_window_age_i = int(latest_window_age)
    if latest_window_age_i >= 0 and telemetry_age_i >= 0:
        lag = max(0, latest_window_age_i - telemetry_age_i)
        if lag > stale_after_seconds:
            reporter.warn("window freshness", f"latest window lags telemetry by about {lag}s")
        else:
            reporter.pass_("window freshness", f"latest window lag is about {lag}s")


def check_systemd(reporter: Reporter, *, service_name: str, timeout: float) -> None:
    systemctl = shutil.which("systemctl")
    if systemctl is None:
        reporter.skip("systemd service", "systemctl is not available")
        return

    active = run_command([systemctl, "is-active", service_name], timeout=timeout)
    if active.returncode == 0:
        reporter.pass_("systemd active", f"{service_name} is {active.stdout.strip()}")
    else:
        detail = active.stdout.strip() or active.stderr.strip() or "not active"
        reporter.fail("systemd active", f"{service_name} is {detail}")

    enabled = run_command([systemctl, "is-enabled", service_name], timeout=timeout)
    if enabled.returncode == 0:
        reporter.pass_("systemd enabled", f"{service_name} is {enabled.stdout.strip()}")
    else:
        detail = enabled.stdout.strip() or enabled.stderr.strip() or "not enabled"
        reporter.warn("systemd enabled", f"{service_name} is {detail}")


def check_api(reporter: Reporter, *, base_url: str, timeout: float) -> None:
    ok_count = 0
    for endpoint in API_ENDPOINTS:
        url = f"{base_url}{endpoint}"
        status, data, error = fetch_json(url, timeout=timeout)
        if status != 200 or data is None:
            reporter.warn("api " + endpoint, error or f"HTTP {status}")
            continue
        if endpoint == "/health" and data.get("status") != "ok":
            reporter.warn("api " + endpoint, f"unexpected payload: {data}")
            continue
        if endpoint != "/health" and "count" not in data and endpoint != "/status":
            reporter.warn("api " + endpoint, f"unexpected payload keys: {sorted(data)}")
            continue
        reporter.pass_("api " + endpoint, "HTTP 200 JSON")
        ok_count += 1

    if ok_count == len(API_ENDPOINTS):
        reporter.pass_("api summary", f"all {ok_count} endpoint(s) responded")
    elif ok_count == 0:
        reporter.warn("api summary", f"no endpoint responded at {base_url}")
    else:
        reporter.warn("api summary", f"{ok_count}/{len(API_ENDPOINTS)} endpoint(s) responded")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=None,
        help="PostgreSQL connection URL. Defaults to DPF_DATABASE_URL.",
    )
    parser.add_argument(
        "--service-name",
        default=SERVICE_NAME,
        help=f"systemd service to inspect. Default: {SERVICE_NAME}.",
    )
    parser.add_argument(
        "--api-url",
        default=None,
        help="API base URL. Defaults to DPF_API_HOST/DPF_API_PORT.",
    )
    parser.add_argument(
        "--stale-after-seconds",
        type=int,
        default=600,
        help="Warn when latest ingest/window data is older than this. Default: 600.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=8.0,
        help="Timeout in seconds for psql/systemctl/API checks. Default: 8.",
    )
    parser.add_argument(
        "--skip-api",
        action="store_true",
        help="Skip HTTP API endpoint checks.",
    )
    parser.add_argument(
        "--skip-systemd",
        action="store_true",
        help="Skip systemd service checks.",
    )
    parser.add_argument(
        "--strict-warnings",
        action="store_true",
        help="Return non-zero when any WARN is reported.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    settings = load_settings()
    reporter = Reporter()

    check_environment(reporter)
    check_database(
        reporter,
        database_url=args.database_url or settings.database_url,
        stale_after_seconds=args.stale_after_seconds,
        query_timeout=args.timeout,
    )

    if args.skip_systemd:
        reporter.skip("systemd checks", "disabled by --skip-systemd")
    else:
        check_systemd(reporter, service_name=args.service_name, timeout=args.timeout)

    if args.skip_api:
        reporter.skip("api checks", "disabled by --skip-api")
    else:
        if args.api_url:
            base_url = args.api_url.rstrip("/")
        else:
            host = api_host_for_local_check(settings.api_host)
            base_url = f"http://{host}:{settings.api_port}"
        check_api(reporter, base_url=base_url, timeout=args.timeout)

    return reporter.exit_code(strict_warnings=args.strict_warnings)


if __name__ == "__main__":
    raise SystemExit(main())
