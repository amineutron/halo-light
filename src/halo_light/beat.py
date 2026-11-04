"""Optional hue_beat extension: drive an external audio-sync script.

The script itself is NOT part of this project. Point ``HUE_BEAT_PATH`` at it. Contract:

* started as ``python <script> [--mode=M] [--palette=P] [--bass-only]`` in the background;
* writes its PID to ``HUE_BEAT_PID_FILE`` and a JSON state to ``HUE_BEAT_STATE_FILE``;
* reads JSON control messages from ``HUE_BEAT_CTRL_FILE`` (keys palette, mode, brightness,
  floor, sensitivity);
* stops cleanly on SIGTERM.

The file paths default to files in the system temporary directory.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .errors import BeatUnavailableError, InvalidInputError

ENV_PATH = "HUE_BEAT_PATH"
ENV_PYTHON = "HUE_BEAT_PYTHON"
PALETTES = ("ironman", "fire", "neon", "cool", "sunset", "arctic", "auto")
MODES = ("pulse", "ambiant")


def _file_setting(env: Mapping[str, str], var: str, default_name: str) -> Path:
    explicit = env.get(var)
    return Path(explicit) if explicit else Path(tempfile.gettempdir()) / default_name


def _in_range(name: str, value: float, low: float, high: float) -> float:
    if not low <= value <= high:
        raise InvalidInputError(f"{name} must be between {low} and {high}.")
    return value


class BeatAdapter:
    def __init__(
        self,
        env: Mapping[str, str] | None = None,
        extra_env: Mapping[str, str] | None = None,
    ) -> None:
        self._env = os.environ if env is None else env
        self._extra_env = dict(extra_env or {})
        self._pid_file = _file_setting(self._env, "HUE_BEAT_PID_FILE", "hue_beat.pid")
        self._state_file = _file_setting(self._env, "HUE_BEAT_STATE_FILE", "hue_beat.state.json")
        self._ctrl_file = _file_setting(self._env, "HUE_BEAT_CTRL_FILE", "hue_beat.ctrl")
        self._proc: subprocess.Popen[bytes] | None = None

    # ------------------------------------------------------------------ helpers

    def _interpreter(self) -> str:
        """Interpreter used to run the script: HUE_BEAT_PYTHON, else this server's own.

        The beat script often needs packages (numpy, audio libraries) that are not installed in
        the server's environment, so it can be run by another interpreter.
        """
        raw = self._env.get(ENV_PYTHON, "").strip()
        if not raw:
            return sys.executable
        path = Path(raw).expanduser()
        if not path.is_file() or not os.access(path, os.X_OK):
            raise BeatUnavailableError(f"{ENV_PYTHON}='{raw}' is not an executable file.")
        return str(path)

    def _script(self) -> Path:
        raw = self._env.get(ENV_PATH, "").strip()
        if not raw:
            raise BeatUnavailableError(
                f"hue_beat is an optional extension: set {ENV_PATH} to the script path."
            )
        path = Path(raw).expanduser()
        if not path.is_file():
            raise BeatUnavailableError(f"hue_beat script not found at {ENV_PATH}='{raw}'.")
        return path

    def _pid(self) -> int | None:
        if self._proc is not None and self._proc.poll() is not None:
            self._proc = None
        try:
            pid = int(self._pid_file.read_text().strip())
            os.kill(pid, 0)
        except (OSError, ValueError):
            return None
        try:  # a zombie answers to kill(pid, 0) but is not running
            state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        except (OSError, IndexError):
            return pid
        return None if state == "Z" else pid

    # ---------------------------------------------------------------- operations

    async def start(self, mode: str = "", palette: str = "auto", bass_only: bool = True) -> str:
        script = self._script()
        if palette not in PALETTES:
            raise InvalidInputError(f"Invalid palette. Choose from: {', '.join(PALETTES)}.")
        if mode and mode not in MODES:
            raise InvalidInputError(f"Invalid mode. Choose from: {', '.join(MODES)}.")
        if self._pid() is not None:
            return "hue_beat is already running."
        args = [self._interpreter(), str(script), f"--palette={palette}"]
        if mode:
            args.append(f"--mode={mode}")
        if bass_only:
            args.append("--bass-only")
        env = {**os.environ, **{k: v for k, v in self._extra_env.items() if k not in os.environ}}
        self._proc = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
            args,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        await asyncio.sleep(1.0)
        code = self._proc.poll()
        if code is not None:
            self._proc = None
            raise BeatUnavailableError(f"hue_beat exited immediately (code {code}).")
        return f"hue_beat started (pid {self._proc.pid}, palette {palette})."

    async def stop(self) -> str:
        pid = self._pid()
        if pid is None:
            return "hue_beat is not running."
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            await asyncio.sleep(0.1)
            if self._pid() is None:
                return "hue_beat stopped."
        return "hue_beat was asked to stop but is still shutting down."

    def status(self) -> str:
        self._script()
        pid = self._pid()
        if pid is None:
            return json.dumps({"running": False})
        state: dict[str, Any] = {}
        try:
            loaded = json.loads(self._state_file.read_text())
            state = loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError):
            pass
        keys = ("mode", "layout", "palette", "bpm")
        return json.dumps(
            {"running": True, "pid": pid, **{k: state[k] for k in keys if k in state}}
        )

    def set(
        self,
        palette: str = "",
        mode: str = "",
        brightness: float = -1.0,
        floor: float = -1.0,
        sensitivity: float = -1.0,
    ) -> str:
        self._script()
        if self._pid() is None:
            return "hue_beat is not running. Start it first."
        cmd: dict[str, Any] = {}
        if palette:
            if palette not in PALETTES:
                raise InvalidInputError(f"Invalid palette. Choose from: {', '.join(PALETTES)}.")
            cmd["palette"] = palette
        if mode:
            if mode not in MODES:
                raise InvalidInputError(f"Invalid mode. Choose from: {', '.join(MODES)}.")
            cmd["mode"] = mode
        if brightness >= 0:
            cmd["brightness"] = _in_range("brightness", brightness, 0.1, 1.0)
        if floor >= 0:
            cmd["floor"] = _in_range("floor", floor, 0.0, 0.9)
        if sensitivity >= 0:
            cmd["sensitivity"] = _in_range("sensitivity", sensitivity, 0.5, 3.0)
        if not cmd:
            return "Nothing to change."
        tmp = self._ctrl_file.with_name(self._ctrl_file.name + ".tmp")
        tmp.write_text(json.dumps(cmd))
        os.replace(tmp, self._ctrl_file)
        return "hue_beat updated: " + ", ".join(f"{k}={v}" for k, v in cmd.items()) + "."
