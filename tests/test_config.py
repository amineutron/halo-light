import json
import os
import stat

import pytest

from hue_bridge_mcp.config import (
    default_config_path,
    load_settings,
    save_config,
    validate_host,
)
from hue_bridge_mcp.errors import InvalidInputError

posix_only = pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")


def mode_of(path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@posix_only
def test_new_config_file_is_0600_even_with_open_umask(tmp_path):
    previous = os.umask(0)
    try:
        path = tmp_path / "sub" / "config.json"
        save_config(path, {"bridge_ip": "192.0.2.1", "app_key": "k"})
    finally:
        os.umask(previous)
    assert mode_of(path) == 0o600
    assert mode_of(path.parent) == 0o700
    assert json.loads(path.read_text())["app_key"] == "k"


@posix_only
def test_existing_loose_file_is_tightened_on_save(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{}")
    path.chmod(0o644)
    save_config(path, {"app_key": "k"})
    assert mode_of(path) == 0o600


def test_save_merges_and_leaves_no_temp_file(tmp_path):
    path = tmp_path / "config.json"
    save_config(path, {"bridge_ip": "192.0.2.1"})
    save_config(path, {"app_key": "k"})
    assert json.loads(path.read_text()) == {"bridge_ip": "192.0.2.1", "app_key": "k"}
    assert [p.name for p in tmp_path.iterdir()] == ["config.json"]


def test_environment_overrides_file(tmp_path):
    path = tmp_path / "config.json"
    save_config(path, {"bridge_ip": "192.0.2.1", "app_key": "from-file"})
    settings = load_settings({"HUE_APP_KEY": "from-env"}, path)
    assert settings.app_key == "from-env"
    assert settings.host == "192.0.2.1"
    settings = load_settings({"HUE_BRIDGE_IP": "192.0.2.9"}, path)
    assert settings.host == "192.0.2.9"
    assert settings.app_key == "from-file"


def test_missing_or_corrupt_file_gives_empty_settings(tmp_path):
    assert load_settings({}, tmp_path / "absent.json").app_key is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert load_settings({}, bad).host is None


@posix_only
def test_loose_permissions_trigger_a_warning(tmp_path, capsys):
    path = tmp_path / "config.json"
    path.write_text('{"app_key": "k"}')
    path.chmod(0o644)
    load_settings({}, path)
    assert "chmod 600" in capsys.readouterr().err


def test_default_path_follows_environment(tmp_path):
    assert default_config_path({"HUE_BRIDGE_CONFIG": str(tmp_path / "x.json")}) == (
        tmp_path / "x.json"
    )
    assert default_config_path({"XDG_CONFIG_HOME": str(tmp_path)}) == (
        tmp_path / "hue-bridge-mcp" / "config.json"
    )


@pytest.mark.parametrize("host", ["https://evil.example/", "a b", "x/y", "", "host?q=1"])
def test_invalid_hosts_rejected(host):
    with pytest.raises(InvalidInputError):
        validate_host(host)


@pytest.mark.parametrize("host", ["192.0.2.5", "hue.local", "[2001:db8::1]"])
def test_valid_hosts_accepted(host):
    assert validate_host(host) == host
