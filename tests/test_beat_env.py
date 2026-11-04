"""Credentials handed to the external hue_beat script: file section, fallbacks, no leaks."""

from halo_light.config import Settings, load_settings, save_config
from halo_light.runtime import Runtime


def test_beat_env_falls_back_to_the_application_key():
    env = Runtime(Settings(host="192.0.2.1", app_key="APP")).beat_env()
    assert env == {"HUE_USER": "APP", "HUE_BRIDGE_IP": "192.0.2.1"}


def test_beat_env_uses_the_entertainment_credentials_when_present():
    settings = Settings(
        host="192.0.2.1",
        app_key="APP",
        beat_user="BEAT",
        beat_clientkey="CK",
        beat_area_id="AREA",
    )
    assert Runtime(settings).beat_env() == {
        "HUE_USER": "BEAT",
        "HUE_CLIENTKEY": "CK",
        "HUE_AREA_ID": "AREA",
        "HUE_BRIDGE_IP": "192.0.2.1",
    }


def test_beat_env_is_empty_without_any_credentials():
    assert Runtime(Settings()).beat_env() == {}


def test_beat_section_is_read_from_the_config_file(tmp_path):
    path = tmp_path / "config.json"
    save_config(
        path,
        {
            "bridge_ip": "192.0.2.1",
            "app_key": "APP",
            "beat": {"username": "BEAT", "clientkey": "CK", "area_id": "AREA"},
        },
    )
    settings = load_settings({}, path)
    assert (settings.beat_user, settings.beat_clientkey, settings.beat_area_id) == (
        "BEAT",
        "CK",
        "AREA",
    )


def test_malformed_beat_section_is_ignored(tmp_path):
    path = tmp_path / "config.json"
    save_config(path, {"app_key": "APP", "beat": "not-a-mapping"})
    settings = load_settings({}, path)
    assert settings.beat_user is None
    assert settings.beat_clientkey is None
    assert settings.beat_area_id is None
