"""Configuration helpers for backend services."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


DEFAULT_ENV_FILE = "/etc/dpf-backend.env"


def _strip_env_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_env_file(path: str | os.PathLike[str] | None = None) -> None:
    """Load KEY=value settings from an env file without overriding os.environ."""

    env_path = Path(path or os.getenv("DPF_ENV_FILE", DEFAULT_ENV_FILE))
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _strip_env_value(raw_value)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    device_id: str
    mqtt_host: str
    mqtt_port: int
    mqtt_tls: bool
    mqtt_client_id: str
    mqtt_username: str | None
    mqtt_password: str | None
    mqtt_ca_file: str | None
    database_url: str
    api_host: str
    api_port: int


def load_settings() -> Settings:
    """Load backend settings from /etc/dpf-backend.env and environment variables."""

    load_env_file()

    return Settings(
        device_id=os.getenv("DPF_DEVICE_ID", "dpf-tracker"),
        mqtt_host=os.getenv("DPF_MQTT_HOST", "localhost"),
        mqtt_port=int(os.getenv("DPF_MQTT_PORT", "8883")),
        mqtt_tls=_env_bool("DPF_MQTT_TLS", True),
        mqtt_client_id=os.getenv("DPF_MQTT_CLIENT_ID", "dpf-backend-ingestor"),
        mqtt_username=os.getenv("DPF_MQTT_USERNAME") or None,
        mqtt_password=os.getenv("DPF_MQTT_PASSWORD") or None,
        mqtt_ca_file=os.getenv("DPF_MQTT_CA_FILE") or None,
        database_url=os.getenv(
            "DPF_DATABASE_URL",
            "postgresql://dpf_backend:dpf_backend@localhost:5432/dpf_backend",
        ),
        api_host=os.getenv("DPF_API_HOST", "127.0.0.1"),
        api_port=int(os.getenv("DPF_API_PORT", "8090")),
    )
