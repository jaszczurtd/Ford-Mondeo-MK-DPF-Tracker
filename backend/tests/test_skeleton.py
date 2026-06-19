from dpf_backend import __version__
from dpf_backend.config import load_settings
from dpf_backend.topics import SUBSCRIBE_TOPICS


def test_package_version_is_defined() -> None:
    assert __version__


def test_default_settings_load() -> None:
    settings = load_settings()
    assert settings.mqtt_host == "localhost"
    assert settings.mqtt_port == 8883
    assert settings.mqtt_tls is True


def test_subscribe_topics_match_firmware_contract() -> None:
    assert SUBSCRIBE_TOPICS == ("dpf/data", "dpf/events", "dpf/status")

