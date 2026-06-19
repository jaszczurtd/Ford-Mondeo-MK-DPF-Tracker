"""MQTT ingestor service for tracker payloads."""

from __future__ import annotations

import argparse
import logging
import ssl
from typing import Any

from dpf_backend.config import load_settings
from dpf_backend.ingest.parser import parse_mqtt_message
from dpf_backend.storage.postgres import PostgresStore
from dpf_backend.topics import SUBSCRIBE_TOPICS


LOG = logging.getLogger("dpf_backend.ingest")


def _mqtt_connect_failed(reason_code: Any) -> bool:
    if hasattr(reason_code, "is_failure"):
        return bool(reason_code.is_failure)
    try:
        return int(reason_code) != 0
    except (TypeError, ValueError):
        return str(reason_code) not in {"0", "Success", "Normal disconnection"}


def _build_client(settings: Any, store: PostgresStore) -> Any:
    try:
        import paho.mqtt.client as mqtt
    except ImportError as exc:  # pragma: no cover - exercised on Pi installs
        raise RuntimeError("paho-mqtt is not installed") from exc

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=settings.mqtt_client_id)

    if settings.mqtt_username:
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password)

    if settings.mqtt_tls:
        client.tls_set(
            ca_certs=settings.mqtt_ca_file,
            cert_reqs=ssl.CERT_REQUIRED if settings.mqtt_ca_file else ssl.CERT_NONE,
        )
        if not settings.mqtt_ca_file:
            client.tls_insecure_set(True)

    def on_connect(client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        del userdata, flags, properties
        if _mqtt_connect_failed(reason_code):
            LOG.error("MQTT connect failed: %s", reason_code)
            return
        LOG.info("Connected to MQTT %s:%s", settings.mqtt_host, settings.mqtt_port)
        for topic in SUBSCRIBE_TOPICS:
            client.subscribe(topic, qos=1)
            LOG.info("Subscribed to %s", topic)

    def on_message(client: Any, userdata: Any, message: Any) -> None:
        del client, userdata
        parsed = parse_mqtt_message(
            message.topic,
            message.payload,
            device_id=settings.device_id,
        )
        raw_id = store.save_message(parsed)
        LOG.info(
            "Stored MQTT topic=%s raw_id=%s telemetry=%s events=%s status=%s parse_ok=%s",
            message.topic,
            raw_id,
            parsed.telemetry is not None,
            len(parsed.actuator_events),
            parsed.status is not None,
            parsed.raw.parse_ok,
        )

    client.on_connect = on_connect
    client.on_message = on_message
    return client


def run() -> None:
    settings = load_settings()
    with PostgresStore(settings.database_url) as store:
        client = _build_client(settings, store)
        client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
        client.loop_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
