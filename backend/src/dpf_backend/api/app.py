"""FastAPI application factory for DPF backend data access."""

from __future__ import annotations

from datetime import datetime

from dpf_backend import __version__
from dpf_backend.config import Settings, load_settings
from dpf_backend.api.queries import ApiStore, MAX_LIMIT


def create_app(settings: Settings | None = None):
    """Create the FastAPI application.

    FastAPI is imported lazily so command-line help and unit tests that only
    inspect query helpers do not require the optional web stack to be installed.
    """

    try:
        from fastapi import FastAPI, HTTPException, Query
    except ImportError as exc:  # pragma: no cover - depends on deployment env
        raise RuntimeError("FastAPI is not installed") from exc

    app_settings = settings or load_settings()
    app = FastAPI(
        title="DPF Backend API",
        version=__version__,
        description="Read-only API for Ford Mondeo MK4 DPF tracker telemetry.",
    )

    def open_store() -> ApiStore:
        return ApiStore(app_settings.database_url)

    def db_error(exc: Exception) -> HTTPException:
        return HTTPException(status_code=503, detail=str(exc))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/status")
    def status() -> dict[str, object]:
        try:
            with open_store() as store:
                data = store.backend_status()
        except Exception as exc:  # noqa: BLE001 - surfaced as API 503
            raise db_error(exc) from exc
        return {"status": "ok", "version": __version__, "database": data}

    @app.get("/raw-mqtt/recent")
    def recent_raw_mqtt(
        limit: int = Query(100, ge=1, le=MAX_LIMIT),
        topic: str | None = None,
        device_id: str | None = None,
    ) -> dict[str, object]:
        try:
            with open_store() as store:
                rows = store.recent_raw_mqtt(
                    limit=limit,
                    topic=topic,
                    device_id=device_id,
                )
        except Exception as exc:  # noqa: BLE001 - surfaced as API 503
            raise db_error(exc) from exc
        return {"count": len(rows), "rows": rows}

    @app.get("/telemetry")
    def telemetry(
        from_ts: datetime | None = Query(None, alias="from"),
        to_ts: datetime | None = Query(None, alias="to"),
        limit: int = Query(100, ge=1, le=MAX_LIMIT),
        device_id: str | None = None,
        boot_session_id: int | None = None,
    ) -> dict[str, object]:
        try:
            with open_store() as store:
                rows = store.telemetry_rows(
                    from_ts=from_ts,
                    to_ts=to_ts,
                    limit=limit,
                    device_id=device_id,
                    boot_session_id=boot_session_id,
                )
        except Exception as exc:  # noqa: BLE001 - surfaced as API 503
            raise db_error(exc) from exc
        return {"count": len(rows), "rows": rows}

    @app.get("/windows")
    def windows(
        bucket_seconds: int = Query(10, ge=1),
        from_ts: datetime | None = Query(None, alias="from"),
        to_ts: datetime | None = Query(None, alias="to"),
        limit: int = Query(100, ge=1, le=MAX_LIMIT),
        device_id: str | None = None,
        boot_session_id: int | None = None,
    ) -> dict[str, object]:
        try:
            with open_store() as store:
                rows = store.telemetry_windows(
                    bucket_seconds=bucket_seconds,
                    from_ts=from_ts,
                    to_ts=to_ts,
                    limit=limit,
                    device_id=device_id,
                    boot_session_id=boot_session_id,
                )
        except Exception as exc:  # noqa: BLE001 - surfaced as API 503
            raise db_error(exc) from exc
        return {"count": len(rows), "rows": rows}

    @app.get("/boot-sessions")
    def boot_sessions(
        limit: int = Query(100, ge=1, le=MAX_LIMIT),
        device_id: str | None = None,
    ) -> dict[str, object]:
        try:
            with open_store() as store:
                rows = store.boot_sessions(limit=limit, device_id=device_id)
        except Exception as exc:  # noqa: BLE001 - surfaced as API 503
            raise db_error(exc) from exc
        return {"count": len(rows), "rows": rows}

    return app
