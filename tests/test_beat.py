import json
import os
import sys
import textwrap

import pytest

from conftest import text_of
from halo_light.beat import BeatAdapter
from halo_light.errors import BeatUnavailableError, InvalidInputError


def adapter(tmp_path, **extra):
    env = {
        "HUE_BEAT_PID_FILE": str(tmp_path / "beat.pid"),
        "HUE_BEAT_STATE_FILE": str(tmp_path / "beat.state.json"),
        "HUE_BEAT_CTRL_FILE": str(tmp_path / "beat.ctrl"),
        **extra,
    }
    return BeatAdapter(env=env)


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("hue_beat_start", {}),
        ("hue_beat_stop", {}),
        ("hue_beat_status", {}),
        ("hue_beat_set", {"palette": "neon"}),
    ],
)
async def test_tools_without_script_answer_with_a_clear_error(mcp_client, tool, args):
    result = await mcp_client.call_tool(tool, args)
    if tool == "hue_beat_stop":
        assert not result.is_error  # stopping something that never ran is harmless
        return
    assert result.is_error
    assert "HUE_BEAT_PATH" in text_of(result)


def test_missing_script_file_is_reported(tmp_path):
    beat = adapter(tmp_path, HUE_BEAT_PATH=str(tmp_path / "nope.py"))
    with pytest.raises(BeatUnavailableError, match="not found"):
        beat.status()


FAKE_SCRIPT = textwrap.dedent(
    """
    import json, os, signal, sys, time
    pid_file, state_file = os.environ["HUE_BEAT_PID_FILE"], os.environ["HUE_BEAT_STATE_FILE"]
    open(pid_file, "w").write(str(os.getpid()))
    palette = next(a.split("=")[1] for a in sys.argv if a.startswith("--palette="))
    json.dump({"mode": "pulse", "palette": palette, "bpm": 120.0}, open(state_file, "w"))
    def stop(*_):
        os.remove(pid_file)
        sys.exit(0)
    signal.signal(signal.SIGTERM, stop)
    while True:
        time.sleep(0.05)
    """
)


@pytest.mark.skipif(os.name != "posix", reason="POSIX signals")
async def test_full_lifecycle_with_a_fake_script(tmp_path):
    script = tmp_path / "fake_beat.py"
    script.write_text(FAKE_SCRIPT)
    env_files = {
        "HUE_BEAT_PID_FILE": str(tmp_path / "beat.pid"),
        "HUE_BEAT_STATE_FILE": str(tmp_path / "beat.state.json"),
        "HUE_BEAT_CTRL_FILE": str(tmp_path / "beat.ctrl"),
    }
    os.environ.update(env_files)  # the child inherits them
    try:
        beat = BeatAdapter(env={**env_files, "HUE_BEAT_PATH": str(script)})
        assert json.loads(beat.status()) == {"running": False}
        assert "started" in await beat.start(palette="fire", mode="pulse")
        assert "already running" in await beat.start()
        status = json.loads(beat.status())
        assert status["running"] is True and status["palette"] == "fire" and status["bpm"] == 120.0
        assert "updated" in beat.set(palette="neon", brightness=0.8)
        assert json.loads((tmp_path / "beat.ctrl").read_text()) == {
            "palette": "neon",
            "brightness": 0.8,
        }
        assert "stopped" in await beat.stop()
        assert json.loads(beat.status()) == {"running": False}
    finally:
        for key in env_files:
            os.environ.pop(key, None)


async def test_start_reports_a_script_that_dies_immediately(tmp_path):
    script = tmp_path / "crash.py"
    script.write_text("raise SystemExit(3)")
    beat = adapter(tmp_path, HUE_BEAT_PATH=str(script))
    with pytest.raises(BeatUnavailableError, match="code 3"):
        await beat.start()


async def test_validation(tmp_path):
    script = tmp_path / "x.py"
    script.write_text("")
    beat = adapter(tmp_path, HUE_BEAT_PATH=str(script))
    with pytest.raises(InvalidInputError):
        await beat.start(palette="rainbow")
    with pytest.raises(InvalidInputError):
        await beat.start(mode="disco")
    assert sys.executable  # sanity: the adapter relies on it to launch scripts


def test_default_file_names_are_overridable(tmp_path):
    custom = BeatAdapter(
        env={
            "HUE_BEAT_PID_FILE": str(tmp_path / "a.pid"),
            "HUE_BEAT_STATE_FILE": str(tmp_path / "b.json"),
            "HUE_BEAT_CTRL_FILE": str(tmp_path / "c.ctrl"),
        }
    )
    assert custom._pid_file == tmp_path / "a.pid"
    assert custom._state_file == tmp_path / "b.json"
    assert custom._ctrl_file == tmp_path / "c.ctrl"
    assert BeatAdapter(env={})._pid_file.name == "hue_beat.pid"
