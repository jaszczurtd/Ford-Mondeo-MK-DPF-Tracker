from datetime import datetime, timezone

from dpf_backend.ingest.parser import parse_mqtt_message
from dpf_backend.topics import TOPIC_DATA, TOPIC_EVENTS, TOPIC_STATUS


RECEIVED_AT = datetime(2026, 6, 19, 21, 0, tzinfo=timezone.utc)


def test_parse_data_payload() -> None:
    payload = (
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
    )

    parsed = parse_mqtt_message(TOPIC_DATA, payload, received_at=RECEIVED_AT)

    assert parsed.raw.parse_ok is True
    assert parsed.raw.firmware_version == "v0.4"
    assert parsed.telemetry is not None
    assert parsed.telemetry.payload["ms"] == 1234567
    assert parsed.telemetry.payload["cell_age_ms"] is None
    assert parsed.telemetry.payload["cell_speed_kmh"] is None
    assert parsed.actuator_events == ()
    assert parsed.status is None


def test_parse_event_batch_payload() -> None:
    payload = (
        '{"version":"v0.4","ms":1234600,"batch_count":2,'
        '"queue_len":2,"queue_remaining_after_batch":0,"overflow_count":0,'
        '"events":[{"seq":1201,"t_us":1234100123,"t_ms":1234100,'
        '"src":"glow","state":1,"gnss_speed_kmh":74.32,'
        '"dp_voltage":1.42,"dp_sample_age_ms":37},'
        '{"seq":1202,"t_us":1234123456,"t_ms":1234123,'
        '"src":"pump","state":0,"gnss_speed_kmh":-1,'
        '"dp_voltage":1.43,"dp_sample_age_ms":-1}]}'
    )

    parsed = parse_mqtt_message(TOPIC_EVENTS, payload, received_at=RECEIVED_AT)

    assert parsed.raw.parse_ok is True
    assert len(parsed.actuator_events) == 2
    assert parsed.actuator_events[0].event_payload["src"] == "glow"
    assert parsed.actuator_events[0].event_payload["state"] == 1
    assert parsed.actuator_events[1].event_payload["src"] == "pump"
    assert parsed.actuator_events[1].event_payload["gnss_speed_kmh"] is None
    assert parsed.actuator_events[1].event_payload["dp_sample_age_ms"] is None


def test_parse_watchdog_status_payload() -> None:
    payload = '{"status":"watchdog_reset","reason":"watchdog","version":"v0.4","ms":12345}'

    parsed = parse_mqtt_message(TOPIC_STATUS, payload, received_at=RECEIVED_AT)

    assert parsed.raw.parse_ok is True
    assert parsed.status is not None
    assert parsed.status.payload["status"] == "watchdog_reset"
    assert parsed.status.payload["watchdog_reset"] is True


def test_invalid_json_is_raw_only() -> None:
    parsed = parse_mqtt_message(TOPIC_DATA, "not json", received_at=RECEIVED_AT)

    assert parsed.raw.parse_ok is False
    assert parsed.raw.payload_json is None
    assert parsed.raw.parse_error
    assert parsed.telemetry is None
