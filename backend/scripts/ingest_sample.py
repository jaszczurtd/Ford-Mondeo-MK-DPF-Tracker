#!/usr/bin/env python3
"""Insert a sample tracker MQTT payload into PostgreSQL through the ingestor path."""

from __future__ import annotations

import argparse

from dpf_backend.config import load_settings
from dpf_backend.ingest.parser import parse_mqtt_message
from dpf_backend.storage.postgres import PostgresStore
from dpf_backend.topics import TOPIC_DATA, TOPIC_EVENTS, TOPIC_STATUS


SAMPLES = {
    TOPIC_DATA: (
        '{"version":"v0.4","time":"2026-06-19T18:42:10+02:00",'
        '"egt_pre":312.45,"egt_mid":287.12,"dp_voltage":1.42,'
        '"dp_raw":1762,"pump_onoff_period":2.5,"pump_freq_hz":2.5,'
        '"pump_cnt":5,"pump":1,"pump_period_ms":400,'
        '"pump_last_on_ms":82,"pump_current_on_ms":37,"glow":1,'
        '"glow_dur":1400,"glow_current_on_ms":6200,"mcu_temp":42.38,'
        '"data_queue_len":3,"data_overflow_count":0,'
        '"event_queue_len":12,"event_overflow_count":0,'
        '"gnss_valid":1,"gnss_powered":1,"gnss_error":0,'
        '"gnss_age_ms":850,"gnss_speed_kmh":74.32,'
        '"cell_valid":0,"cell_error":0,"cell_age_ms":-1,'
        '"cell_speed_kmh":-1,"ms":1234567}'
    ),
    TOPIC_EVENTS: (
        '{"version":"v0.4","ms":1234600,"batch_count":2,'
        '"queue_len":2,"queue_remaining_after_batch":0,"overflow_count":0,'
        '"events":[{"seq":1201,"t_us":1234100123,"t_ms":1234100,'
        '"src":"glow","state":1,"gnss_speed_kmh":74.32,'
        '"dp_voltage":1.42,"dp_sample_age_ms":37},'
        '{"seq":1202,"t_us":1234123456,"t_ms":1234123,'
        '"src":"pump","state":0,"gnss_speed_kmh":-1,'
        '"dp_voltage":1.43,"dp_sample_age_ms":-1}]}'
    ),
    TOPIC_STATUS: '{"status":"watchdog_reset","reason":"watchdog","version":"v0.4","ms":12345}',
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--topic",
        choices=sorted(SAMPLES),
        default=TOPIC_DATA,
        help="Sample topic to insert.",
    )
    args = parser.parse_args()

    settings = load_settings()
    parsed = parse_mqtt_message(
        args.topic,
        SAMPLES[args.topic],
        device_id=settings.device_id,
    )
    with PostgresStore(settings.database_url) as store:
        raw_id = store.save_message(parsed)

    print(
        f"Inserted raw_id={raw_id} topic={args.topic} "
        f"telemetry={parsed.telemetry is not None} "
        f"events={len(parsed.actuator_events)} status={parsed.status is not None}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
