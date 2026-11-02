"""Configuration: environment variables first, then a JSON file created with mode 0600.

Environment variables:
    HUE_BRIDGE_IP      address of the bridge (optional: discovered when absent)
    HUE_APP_KEY        application key (the ``hue-application-key`` header)
    HUE_BRIDGE_CA_CERT path of a PEM file used to verify the bridge certificate (optional)
    HUE_BRIDGE_CONFIG  path of the JSON configuration file (optional)
"""

from __future__ import annotations

import json
import logging
import os
import re
import stat
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import InvalidInputError

logger = logging.getLogger("hue-bridge-mcp")

ENV_HOST = "HUE_BRIDGE_IP"
ENV_KEY = "HUE_APP_KEY"
ENV_CA = "HUE_BRIDGE_CA_CERT"
ENV_CONFIG = "HUE_BRIDGE_CONFIG"

_HOST_RE = re.compile(r"^[A-Za-z0-9._:\-\[\]]+$")


@dataclass(frozen=True)
class Settings:
    host: str | None = None
    app_key: str | None = None
    ca_cert: str | None = None
    timeout: float = 10.0


def default_config_path(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    explicit = env.get(ENV_CONFIG)
    if explicit:
        return Path(explicit).expanduser()
    base = env.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "hue-bridge-mcp" / "config.json"


def validate_host(host: str) -> str:
    """Reject anything that is not a plain hostname or IP address (no scheme, path, space)."""
    cleaned = host.strip()
    if not cleaned or not _HOST_RE.match(cleaned):
        raise InvalidInputError("Invalid bridge address: give a hostname or an IP address.")
    return cleaned


def _read_file(path: Path) -> dict[str, Any]:
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return {}
    if os.name == "posix" and mode & 0o077:
        print(
            f"warning: {path} is readable by other users (mode {mode:o}); run chmod 600.",
            file=sys.stderr,
        )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Invalid JSON in %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def load_settings(env: Mapping[str, str] | None = None, path: Path | None = None) -> Settings:
    """Merge file and environment; the environment wins."""
    env = os.environ if env is None else env
    data = _read_file(path or default_config_path(env))
    host = env.get(ENV_HOST) or data.get("bridge_ip") or None
    return Settings(
        host=validate_host(host) if host else None,
        app_key=env.get(ENV_KEY) or data.get("app_key") or None,
        ca_cert=env.get(ENV_CA) or data.get("ca_cert") or None,
    )


def save_config(path: Path, values: Mapping[str, Any]) -> None:
    """Write the JSON file atomically, always with mode 0600 (and 0700 for a new directory)."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    existing = _read_file(path)
    merged = {**existing, **values}
    tmp = path.with_name(path.name + ".tmp")
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(merged, handle, indent=2)
            handle.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
