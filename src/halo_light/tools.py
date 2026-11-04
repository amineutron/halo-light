"""MCP tool registration."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from .beat import BeatAdapter
from .colors import color_to_xy, rgb_to_xy
from .presets import effect_body, preset_body
from .runtime import Runtime
from .service import (
    brightness_body,
    power_body,
    require_capability,
    temperature_body,
    xy_body,
)

Ref = str | int

# The bridge is on the local network and every change is reversible: none is destructive.
READ = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
SET = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
ACTION = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)


def _dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def register_tools(mcp: MCPServer, rt: Runtime, beat: BeatAdapter | None = None) -> None:
    beat = beat or BeatAdapter(extra_env=rt.beat_env())

    # ----------------------------------------------------------------- reads

    @mcp.tool(annotations=READ)
    async def get_all_lights() -> str:
        """List every light with room, power, brightness (0-100), color and capabilities."""
        return _dump(await (await rt.service()).lights())

    @mcp.tool(annotations=READ)
    async def get_light(light_id: Ref = "", light_name: str = "") -> str:
        """Get one light, by id or by name (case and accent insensitive)."""
        return _dump(await (await rt.service()).resolve_light(light_id, light_name))

    @mcp.tool(annotations=READ)
    async def find_light_by_name(name: str) -> str:
        """Search lights whose name contains the text (case and accent insensitive)."""
        return _dump(await (await rt.service()).find_lights(name))

    @mcp.tool(annotations=READ)
    async def get_all_groups() -> str:
        """List rooms and zones (plus the whole home) with their lights and state."""
        return _dump(await (await rt.service()).groups())

    @mcp.tool(annotations=READ)
    async def get_group(group_id: Ref = "", group_name: str = "") -> str:
        """Get one room or zone, by id or by name."""
        return _dump(await (await rt.service()).resolve_group(group_id, group_name))

    @mcp.tool(annotations=READ)
    async def get_all_scenes() -> str:
        """List scenes with the room or zone each one belongs to."""
        return _dump(await (await rt.service()).scenes())

    # ------------------------------------------------------- light commands

    @mcp.tool(annotations=SET)
    async def turn_on_light(light_id: Ref = "", light_name: str = "") -> str:
        """Turn a light on, by id or by name."""
        svc = await rt.service()
        light = await svc.resolve_light(light_id, light_name)
        await svc.set_light(light, power_body(True))
        return f"Light '{light['name']}' turned on."

    @mcp.tool(annotations=SET)
    async def turn_off_light(light_id: Ref = "", light_name: str = "") -> str:
        """Turn a light off, by id or by name."""
        svc = await rt.service()
        light = await svc.resolve_light(light_id, light_name)
        await svc.set_light(light, power_body(False))
        return f"Light '{light['name']}' turned off."

    @mcp.tool(annotations=SET)
    async def set_brightness(brightness: int, light_id: Ref = "", light_name: str = "") -> str:
        """Set a light's brightness (0-100, turns it on; 0 turns it off)."""
        body = brightness_body(brightness)
        svc = await rt.service()
        light = await svc.resolve_light(light_id, light_name)
        if brightness > 0:
            require_capability(light, "dimming")
        await svc.set_light(light, body)
        return f"Light '{light['name']}' brightness set to {brightness}%."

    @mcp.tool(annotations=SET)
    async def set_color_rgb(
        red: int, green: int, blue: int, light_id: Ref = "", light_name: str = ""
    ) -> str:
        """Set a light's color from RGB components (0-255)."""
        x, y = rgb_to_xy(red, green, blue)
        return await _light_color(light_id, light_name, x, y)

    @mcp.tool(annotations=SET)
    async def set_color(color: str, light_id: Ref = "", light_name: str = "") -> str:
        """Set a light's color by name (rouge, bleu, orange, ...) or hex (#rrggbb)."""
        x, y = color_to_xy(color)
        return await _light_color(light_id, light_name, x, y)

    @mcp.tool(annotations=SET)
    async def set_color_xy(x: float, y: float, light_id: Ref = "", light_name: str = "") -> str:
        """Set a light's color from CIE 1931 xy coordinates (0-1)."""
        return await _light_color(light_id, light_name, x, y)

    @mcp.tool(annotations=SET)
    async def set_color_temperature(
        temperature: int, light_id: Ref = "", light_name: str = ""
    ) -> str:
        """Set a light's white color temperature in Kelvin (about 2000 warm to 6500 cool)."""
        body = temperature_body(temperature)
        svc = await rt.service()
        light = await svc.resolve_light(light_id, light_name)
        require_capability(light, "color_temperature")
        await svc.set_light(light, body)
        return f"Light '{light['name']}' set to {temperature} K."

    @mcp.tool(annotations=SET)
    async def set_color_preset(preset: str, light_id: Ref = "", light_name: str = "") -> str:
        """Apply a named preset to a light: warm, cool, daylight, concentration, relax, reading,
        energize, red, green, blue, purple, orange."""
        body = preset_body(preset)
        svc = await rt.service()
        light = await svc.resolve_light(light_id, light_name)
        for field, capability in (
            ("color_temperature", "color_temperature"),
            ("color", "color"),
            ("dimming", "dimming"),
        ):
            if field in body:
                require_capability(light, capability)
        await svc.set_light(light, body)
        return f"Light '{light['name']}' set to preset '{preset}'."

    @mcp.tool(annotations=SET)
    async def set_light_effect(effect: str, light_id: Ref = "", light_name: str = "") -> str:
        """Set a dynamic effect on a light: none, candle, fire, prism, sparkle, opal, glisten,
        underwater, cosmos, sunbeam, enchant."""
        body = effect_body(effect)
        svc = await rt.service()
        light = await svc.resolve_light(light_id, light_name)
        await svc.set_light(light, body)
        return f"Light '{light['name']}' effect set to '{effect}'."

    @mcp.tool(annotations=ACTION)
    async def alert_light(light_id: Ref = "", light_name: str = "") -> str:
        """Make a light flash briefly so it can be identified."""
        svc = await rt.service()
        light = await svc.resolve_light(light_id, light_name)
        await svc.alert(light)
        return f"Light '{light['name']}' is flashing."

    async def _light_color(light_id: Ref, light_name: str, x: float, y: float) -> str:
        body = xy_body(x, y)
        svc = await rt.service()
        light = await svc.resolve_light(light_id, light_name)
        require_capability(light, "color")
        await svc.set_light(light, body)
        return f"Light '{light['name']}' color set (xy {x}, {y})."

    # ------------------------------------------------------ group commands

    @mcp.tool(annotations=SET)
    async def turn_on_group(group_id: Ref = "", group_name: str = "") -> str:
        """Turn on a room or zone, by id or by name."""
        svc = await rt.service()
        group = await svc.resolve_group(group_id, group_name)
        await svc.set_group(group, power_body(True))
        return f"Group '{group['name']}' turned on."

    @mcp.tool(annotations=SET)
    async def turn_off_group(group_id: Ref = "", group_name: str = "") -> str:
        """Turn off a room or zone, by id or by name."""
        svc = await rt.service()
        group = await svc.resolve_group(group_id, group_name)
        await svc.set_group(group, power_body(False))
        return f"Group '{group['name']}' turned off."

    @mcp.tool(annotations=SET)
    async def set_group_brightness(
        brightness: int, group_id: Ref = "", group_name: str = ""
    ) -> str:
        """Set the brightness (0-100, turns it on; 0 turns it off) of a room or zone."""
        body = brightness_body(brightness)
        svc = await rt.service()
        group = await svc.resolve_group(group_id, group_name)
        await svc.set_group(group, body)
        return f"Group '{group['name']}' brightness set to {brightness}%."

    @mcp.tool(annotations=SET)
    async def set_group_color_rgb(
        red: int, green: int, blue: int, group_id: Ref = "", group_name: str = ""
    ) -> str:
        """Set the color of a room or zone from RGB components (0-255)."""
        x, y = rgb_to_xy(red, green, blue)
        return await _group_color(group_id, group_name, x, y)

    @mcp.tool(annotations=SET)
    async def set_group_color(color: str, group_id: Ref = "", group_name: str = "") -> str:
        """Set the color of a room or zone by name (rouge, bleu, ...) or hex (#rrggbb)."""
        x, y = color_to_xy(color)
        return await _group_color(group_id, group_name, x, y)

    @mcp.tool(annotations=SET)
    async def set_group_color_temperature(
        temperature: int, group_id: Ref = "", group_name: str = ""
    ) -> str:
        """Set the white color temperature (Kelvin) of a room or zone."""
        body = temperature_body(temperature)
        svc = await rt.service()
        group = await svc.resolve_group(group_id, group_name)
        await svc.set_group(group, body)
        return f"Group '{group['name']}' set to {temperature} K."

    @mcp.tool(annotations=SET)
    async def set_group_color_preset(preset: str, group_id: Ref = "", group_name: str = "") -> str:
        """Apply a named preset to a room or zone: warm, cool, daylight, concentration, relax,
        reading, energize, red, green, blue, purple, orange."""
        body = preset_body(preset)
        svc = await rt.service()
        group = await svc.resolve_group(group_id, group_name)
        await svc.set_group(group, body)
        return f"Group '{group['name']}' set to preset '{preset}'."

    async def _group_color(group_id: Ref, group_name: str, x: float, y: float) -> str:
        body = xy_body(x, y)
        svc = await rt.service()
        group = await svc.resolve_group(group_id, group_name)
        await svc.set_group(group, body)
        return f"Group '{group['name']}' color set (xy {x}, {y})."

    # --------------------------------------------------------------- scenes

    @mcp.tool(annotations=SET)
    async def activate_scene_by_name(
        scene_name: str, group_name: str = "", group_id: Ref = ""
    ) -> str:
        """Activate a scene by name (case and accent insensitive), in the room it belongs to.

        If several rooms have a scene with that name, the error lists them: pass group_name
        (or group_id) to pick one.
        """
        svc = await rt.service()
        scene = await svc.resolve_scene(None, scene_name, group_id, group_name)
        await svc.recall_scene(scene)
        return f"Scene '{scene['name']}' activated in '{scene['group_name']}'."

    @mcp.tool(annotations=SET)
    async def set_scene(scene_id: Ref, group_id: Ref = "") -> str:
        """Activate a scene by id. group_id, if given, must be the scene's own room or zone."""
        svc = await rt.service()
        scene = await svc.resolve_scene(scene_id, "", group_id, "")
        await svc.recall_scene(scene)
        return f"Scene '{scene['name']}' activated in '{scene['group_name']}'."

    # ------------------------------------------------- optional hue_beat

    @mcp.tool(annotations=ACTION)
    async def hue_beat_start(mode: str = "", palette: str = "auto", bass_only: bool = True) -> str:
        """Start the external hue_beat audio sync (optional extension, needs HUE_BEAT_PATH).

        While it runs, REST commands on the lights of its entertainment area may be ignored.
        mode: pulse | ambiant. palette: ironman | fire | neon | cool | sunset | arctic | auto.
        """
        return await beat.start(mode, palette, bass_only)

    @mcp.tool(annotations=SET)
    async def hue_beat_stop() -> str:
        """Stop hue_beat (optional extension)."""
        return await beat.stop()

    @mcp.tool(annotations=READ)
    async def hue_beat_status() -> str:
        """Report whether hue_beat is running, with mode, palette and BPM (optional extension)."""
        return beat.status()

    @mcp.tool(annotations=SET)
    async def hue_beat_set(
        palette: str = "",
        mode: str = "",
        brightness: float = -1.0,
        floor: float = -1.0,
        sensitivity: float = -1.0,
    ) -> str:
        """Change hue_beat settings live. Empty or -1 means unchanged.

        brightness 0.1-1.0 (peak on beats), floor 0.0-0.9 (ambient level between beats),
        sensitivity 0.5-3.0 (beat detection multiplier).
        """
        return beat.set(palette, mode, brightness, floor, sensitivity)
