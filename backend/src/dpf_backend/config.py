"""Configuration helpers for backend services."""

from __future__ import annotations

from dataclasses import dataclass
import os


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
    """Load backend settings from environment variables."""

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
        api_port=int(os.getenv("DPF_API_PORT", "8080")),
    )
