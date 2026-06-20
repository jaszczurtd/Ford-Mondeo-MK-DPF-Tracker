import os
from tempfile import TemporaryDirectory

from dpf_backend import __version__
from dpf_backend.config import load_env_file, load_settings
from dpf_backend.topics import SUBSCRIBE_TOPICS


def test_package_version_is_defined() -> None:
    assert __version__


def test_default_settings_load() -> None:
    settings = load_settings()
    assert settings.mqtt_host
    assert settings.mqtt_port == 8883
    assert settings.mqtt_tls is True
    assert settings.device_id == "dpf-tracker"
    assert settings.mqtt_client_id


def test_env_file_loads_missing_values_without_overriding_existing() -> None:
    with TemporaryDirectory() as tmp:
        env_path = os.path.join(tmp, "dpf.env")
        with open(env_path, "w", encoding="utf-8") as handle:
            handle.write("DPF_TEST_FROM_FILE=from-file\n")
            handle.write("DPF_TEST_EXISTING=from-file\n")
            handle.write("DPF_TEST_QUOTED='quoted value'\n")

        old_from_file = os.environ.pop("DPF_TEST_FROM_FILE", None)
        old_existing = os.environ.get("DPF_TEST_EXISTING")
        old_quoted = os.environ.pop("DPF_TEST_QUOTED", None)
        os.environ["DPF_TEST_EXISTING"] = "from-env"
        try:
            load_env_file(env_path)
            assert os.environ["DPF_TEST_FROM_FILE"] == "from-file"
            assert os.environ["DPF_TEST_EXISTING"] == "from-env"
            assert os.environ["DPF_TEST_QUOTED"] == "quoted value"
        finally:
            for key in ("DPF_TEST_FROM_FILE", "DPF_TEST_EXISTING", "DPF_TEST_QUOTED"):
                os.environ.pop(key, None)
            if old_from_file is not None:
                os.environ["DPF_TEST_FROM_FILE"] = old_from_file
            if old_existing is not None:
                os.environ["DPF_TEST_EXISTING"] = old_existing
            if old_quoted is not None:
                os.environ["DPF_TEST_QUOTED"] = old_quoted


def test_subscribe_topics_match_firmware_contract() -> None:
    assert SUBSCRIBE_TOPICS == ("dpf/data", "dpf/events", "dpf/status")
