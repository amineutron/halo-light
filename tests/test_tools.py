import pytest

from conftest import json_of, text_of
from fake_bridge import FakeBridge

EXPECTED_TOOLS = {
    "get_all_lights", "get_light", "find_light_by_name", "get_all_groups", "get_group",
    "get_all_scenes", "turn_on_light", "turn_off_light", "set_brightness", "set_color_rgb",
    "set_color", "set_color_xy", "set_color_temperature", "alert_light", "turn_on_group",
    "turn_off_group", "set_group_brightness", "set_group_color_rgb", "set_group_color",
    "set_group_color_temperature", "activate_scene_by_name", "set_scene", "hue_beat_start",
    "hue_beat_stop", "hue_beat_status", "hue_beat_set", "set_color_preset", "set_light_effect",
    "set_group_color_preset",
}  # fmt: skip


async def call(client, _tool, **args):
    return await client.call_tool(_tool, args)


# ---------------------------------------------------------------- listing


async def test_tool_catalogue_and_annotations(mcp_client):
    tools = {t.name: t for t in (await mcp_client.list_tools()).tools}
    assert set(tools) == EXPECTED_TOOLS
    for name, tool in tools.items():
        assert tool.annotations is not None, name
        assert tool.annotations.destructive_hint is False, name
    reads = {n for n, t in tools.items() if t.annotations.read_only_hint}
    assert reads == {
        "get_all_lights", "get_light", "find_light_by_name", "get_all_groups", "get_group",
        "get_all_scenes", "hue_beat_status",
    }  # fmt: skip
    assert tools["alert_light"].annotations.idempotent_hint is False


async def test_get_all_lights_reports_rooms_and_capabilities(mcp_client):
    lights = json_of(await call(mcp_client, "get_all_lights"))
    by_name = {light["name"]: light for light in lights}
    assert by_name["Salon Plafond"]["room"] == "Salon"
    assert by_name["Chevet"]["room"] == "Chambre"
    assert by_name["Lampe Café"]["supports_color"] is False
    assert by_name["Salon Plafond"]["color_temperature_kelvin"] == 2732


async def test_get_all_groups_includes_rooms_zones_and_home(mcp_client):
    groups = json_of(await call(mcp_client, "get_all_groups"))
    kinds = {g["name"]: g["type"] for g in groups}
    assert kinds["Salon"] == "room" and kinds["Coin lecture"] == "zone" and "home" in kinds.values()
    salon = next(g for g in groups if g["name"] == "Salon")
    assert salon["lights"] == ["Lampe Café", "Salon Lampadaire", "Salon Plafond"]
    assert salon["brightness"] == 40.0


async def test_get_all_scenes_shows_own_room(mcp_client):
    scenes = json_of(await call(mcp_client, "get_all_scenes"))
    nuit = next(s for s in scenes if s["name"] == "Nuit étoilée")
    assert nuit["group_name"] == "Chambre" and nuit["group_type"] == "room"


async def test_find_light_by_name_partial_and_accent_insensitive(mcp_client):
    found = json_of(await call(mcp_client, "find_light_by_name", name="salon"))
    assert {light["name"] for light in found} == {"Salon Plafond", "Salon Lampadaire"}
    assert json_of(await call(mcp_client, "find_light_by_name", name="CAFE"))[0]["id"] == "l-cafe"


# ------------------------------------------------------------ light control


async def test_turn_on_by_name_sends_v2_payload(mcp_client, bridge):
    result = await call(mcp_client, "turn_on_light", light_name="chevet")
    assert not result.is_error
    assert bridge.puts == [("/clip/v2/resource/light/l-chevet", {"on": {"on": True}})]


async def test_turn_off_by_uuid_and_by_legacy_numeric_id(mcp_client, bridge):
    await call(mcp_client, "turn_off_light", light_id="l-cafe")
    await call(mcp_client, "turn_off_light", light_id=2)  # v1 id, matched via id_v1
    assert [p[0] for p in bridge.puts] == [
        "/clip/v2/resource/light/l-cafe",
        "/clip/v2/resource/light/l-lampadaire",
    ]


async def test_id_wins_over_name_and_zero_means_unset(mcp_client, bridge):
    await call(mcp_client, "turn_on_light", light_id=0, light_name="Chevet")
    await call(mcp_client, "turn_on_light", light_id="l-cafe", light_name="Chevet")
    assert [p[0].rsplit("/", 1)[-1] for p in bridge.puts] == ["l-chevet", "l-cafe"]


async def test_set_brightness_turns_on_and_zero_turns_off(mcp_client, bridge):
    await call(mcp_client, "set_brightness", brightness=30, light_name="chevet")
    await call(mcp_client, "set_brightness", brightness=0, light_name="chevet")
    assert bridge.puts[0][1] == {"on": {"on": True}, "dimming": {"brightness": 30.0}}
    assert bridge.puts[1][1] == {"on": {"on": False}}


async def test_color_by_name_rgb_xy_and_temperature(mcp_client, bridge):
    await call(mcp_client, "set_color", color="Rouge", light_name="plafond")
    await call(mcp_client, "set_color_rgb", red=0, green=0, blue=255, light_name="plafond")
    await call(mcp_client, "set_color_xy", x=0.3, y=0.6, light_name="plafond")
    await call(mcp_client, "set_color_temperature", temperature=2700, light_name="plafond")
    red, blue, xy, ct = (body for _, body in bridge.puts)
    assert red["color"]["xy"]["x"] > 0.6
    assert blue["color"]["xy"]["x"] < 0.2
    assert xy["color"]["xy"] == {"x": 0.3, "y": 0.6}
    assert ct["color_temperature"] == {"mirek": 370}


async def test_alert_uses_breathe_action(mcp_client, bridge):
    await call(mcp_client, "alert_light", light_name="chevet")
    assert bridge.puts[0][1] == {"alert": {"action": "breathe"}}


# ----------------------------------------------------------- group control


async def test_group_by_name_targets_grouped_light(mcp_client, bridge):
    await call(mcp_client, "turn_on_group", group_name="salon")
    await call(mcp_client, "set_group_brightness", brightness=60, group_id="r-chambre")
    await call(mcp_client, "turn_off_group", group_id=81)  # legacy id: /groups/81 is Salon
    assert [p[0] for p in bridge.puts] == [
        "/clip/v2/resource/grouped_light/gl-salon",
        "/clip/v2/resource/grouped_light/gl-chambre",
        "/clip/v2/resource/grouped_light/gl-salon",
    ]
    assert bridge.puts[1][1]["dimming"] == {"brightness": 60.0}


async def test_group_color_and_temperature(mcp_client, bridge):
    await call(mcp_client, "set_group_color", color="bleu", group_name="chambre")
    await call(mcp_client, "set_group_color_rgb", red=255, green=0, blue=0, group_name="chambre")
    await call(mcp_client, "set_group_color_temperature", temperature=4000, group_name="chambre")
    assert len(bridge.puts) == 3
    assert bridge.puts[2][1]["color_temperature"] == {"mirek": 250}


# ------------------------------------------------------------------ scenes


async def test_scene_applies_to_its_own_room(mcp_client, bridge):
    result = await call(mcp_client, "activate_scene_by_name", scene_name="nuit etoilee")
    assert not result.is_error and "Chambre" in text_of(result)
    assert bridge.puts == [("/clip/v2/resource/scene/s-nuit", {"recall": {"action": "active"}})]


async def test_scene_with_accent_and_partial_name(mcp_client, bridge):
    await call(mcp_client, "activate_scene_by_name", scene_name="energie")
    await call(mcp_client, "activate_scene_by_name", scene_name="lect")
    assert [p[0].rsplit("/", 1)[-1] for p in bridge.puts] == ["s-energie", "s-lecture"]


async def test_scene_name_shared_by_two_rooms_is_ambiguous_then_disambiguated(mcp_client, bridge):
    result = await call(mcp_client, "activate_scene_by_name", scene_name="relax")
    assert result.is_error
    message = text_of(result)
    assert "Relax (Salon)" in message and "Relax (Chambre)" in message
    assert bridge.puts == []
    await call(mcp_client, "activate_scene_by_name", scene_name="relax", group_name="chambre")
    assert bridge.puts[0][0].endswith("s-relax-chambre")


async def test_set_scene_by_id_and_group_check(mcp_client, bridge):
    await call(mcp_client, "set_scene", scene_id="s-lecture")
    await call(mcp_client, "set_scene", scene_id="abc4", group_id="r-salon")  # id_v1 suffix
    assert [p[0].rsplit("/", 1)[-1] for p in bridge.puts] == ["s-lecture", "s-energie"]
    wrong = await call(mcp_client, "set_scene", scene_id="s-lecture", group_id="r-chambre")
    assert wrong.is_error
    assert len(bridge.puts) == 2


# ------------------------------------------------------------------ errors


@pytest.mark.parametrize(
    ("tool", "args", "needle"),
    [
        ("turn_on_light", {}, "light_id or a light_name"),
        ("turn_on_light", {"light_name": "grenier"}, "Available"),
        ("turn_on_light", {"light_name": "salon"}, "Salon Lampadaire"),
        ("turn_on_light", {"light_id": "nope"}, "No light has the id"),
        ("set_brightness", {"brightness": 101, "light_name": "chevet"}, "between 0 and 100"),
        ("set_color", {"color": "caca", "light_name": "chevet"}, "Unknown color"),
        ("set_color_temperature", {"temperature": 100, "light_name": "chevet"}, "out of range"),
        ("set_color", {"color": "rouge", "light_name": "cafe"}, "does not support color"),
        ("turn_on_group", {}, "group_id or a group_name"),
        ("activate_scene_by_name", {"scene_name": "inconnue"}, "No scene matches"),
    ],
)
async def test_failures_are_mcp_errors_and_send_nothing(mcp_client, bridge, tool, args, needle):
    result = await call(mcp_client, tool, **args)
    assert result.is_error is True
    assert needle in text_of(result)
    assert bridge.puts == []


async def test_bridge_http_error_becomes_mcp_error(mcp_client, bridge: FakeBridge):
    bridge.fail_with = (
        200,
        {"errors": [{"description": "device (light) is unreachable"}], "data": []},
    )
    result = await call(mcp_client, "get_all_lights")
    assert result.is_error and "unreachable" in text_of(result)


async def test_unreachable_bridge_becomes_mcp_error(mcp_client, bridge: FakeBridge):
    import httpx

    bridge.raise_error = httpx.ConnectError("boom")
    result = await call(mcp_client, "turn_on_light", light_name="chevet")
    assert result.is_error and "Cannot reach" in text_of(result)


async def test_unauthorized_key_is_explained(bridge: FakeBridge):
    from conftest import Client, create_server
    from halo_light.client import HueClient
    from halo_light.runtime import Runtime

    client = HueClient("192.0.2.10", "wrong", transport=bridge.transport())
    async with Client(create_server(Runtime(client=client))) as mcp:
        result = await mcp.call_tool("get_all_lights", {})
    assert result.is_error and "application key" in text_of(result)


async def test_missing_configuration_is_a_clear_error(tmp_path):
    from conftest import Client, create_server
    from halo_light.config import Settings
    from halo_light.runtime import Runtime

    async with Client(create_server(Runtime(Settings()))) as mcp:
        result = await mcp.call_tool("get_all_lights", {})
    assert result.is_error and "halo-light pair" in text_of(result)
    assert "test-key" not in text_of(result)
