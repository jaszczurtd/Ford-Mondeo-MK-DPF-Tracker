from dpf_backend.ingest.mqtt_ingestor import _mqtt_connect_failed


class Reason:
    def __init__(self, is_failure: bool):
        self.is_failure = is_failure


def test_mqtt_connect_failed_handles_paho_v2_reason_code() -> None:
    assert _mqtt_connect_failed(Reason(False)) is False
    assert _mqtt_connect_failed(Reason(True)) is True


def test_mqtt_connect_failed_handles_numeric_reason_code() -> None:
    assert _mqtt_connect_failed(0) is False
    assert _mqtt_connect_failed(1) is True


def test_mqtt_connect_failed_handles_string_reason_code() -> None:
    assert _mqtt_connect_failed("Success") is False
    assert _mqtt_connect_failed("Not authorized") is True
