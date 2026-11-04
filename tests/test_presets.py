"""Named presets and light effects: bodies sent to the bridge and rejected inputs."""

import pytest

from halo_light.errors import InvalidInputError
from halo_light.presets import EFFECTS, PRESETS, effect_body, preset_body
from test_tools import call

# ------------------------------------------------------------------ pure


def test_white_presets_use_kelvin_converted_to_mirek():
    assert preset_body("warm")["color_temperature"] == {"mirek": 400}
    assert preset_body("daylight")["color_temperature"] == {"mirek": 154}
    assert "dimming" not in preset_body("warm")


def test_activity_presets_set_brightness_and_temperature():
    relax = preset_body("relax")
    assert relax["color_temperature"] == {"mirek": 370}
    assert relax["dimming"] == {"brightness": 57.0}
    assert preset_body("concentration")["dimming"] == {"brightness": 100.0}


def test_color_presets_use_xy():
    red = preset_body("red")
    assert red["color"]["xy"]["x"] > 0.6
    assert "color_temperature" not in red


def test_every_preset_turns_the_light_on():
    for name in PRESETS:
        assert preset_body(name)["on"] == {"on": True}


def test_preset_names_ignore_case_and_accents():
    assert preset_body(" Warm ") == preset_body("warm")


def test_unknown_preset_lists_the_choices():
    with pytest.raises(InvalidInputError, match="warm"):
        preset_body("nope")


def test_effects_map_to_the_bridge_vocabulary():
    assert effect_body("none") == {"effects": {"effect": "no_effect"}}
    assert effect_body("Fire") == {"effects": {"effect": "fire"}}
    assert set(EFFECTS) >= {"no_effect", "candle", "fire", "prism"}


def test_unknown_effect_is_rejected_with_the_choices():
    with pytest.raises(InvalidInputError, match="candle"):
        effect_body("colorloop")


# ------------------------------------------------------------------ tools


async def test_set_color_preset_sends_the_body_to_the_light(mcp_client, bridge):
    await call(mcp_client, "set_color_preset", preset="warm", light_name="plafond")
    _, body = bridge.puts[-1]
    assert body["color_temperature"] == {"mirek": 400}


async def test_set_group_color_preset_sends_the_body_to_the_group(mcp_client, bridge):
    await call(mcp_client, "set_group_color_preset", preset="relax", group_name="Salon")
    path, body = bridge.puts[-1]
    assert "grouped_light" in path
    assert body["dimming"] == {"brightness": 57.0}


async def test_set_color_preset_rejects_a_light_without_color(mcp_client, bridge):
    result = await call(mcp_client, "set_color_preset", preset="red", light_name="Café")
    assert result.is_error
    assert not bridge.puts


async def test_set_light_effect_sends_the_effect(mcp_client, bridge):
    await call(mcp_client, "set_light_effect", effect="candle", light_name="plafond")
    _, body = bridge.puts[-1]
    assert body["effects"] == {"effect": "candle"}


async def test_set_light_effect_rejects_an_unknown_effect(mcp_client, bridge):
    result = await call(mcp_client, "set_light_effect", effect="colorloop", light_name="plafond")
    assert result.is_error
    assert not bridge.puts
