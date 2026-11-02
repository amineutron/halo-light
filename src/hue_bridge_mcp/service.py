"""Hue operations: read state, resolve lights/groups/scenes by id or name, send commands."""

from __future__ import annotations

import asyncio
from typing import Any

from .client import HueClient
from .colors import check_xy, kelvin_to_mirek, mirek_to_kelvin
from .errors import InvalidInputError, NotFoundError
from .matching import find_matches, resolve_by_name

Ref = str | int


def _unset(value: Ref | None) -> bool:
    return value is None or value == "" or value == 0


def _id_matches(ref: Ref, item: dict[str, Any]) -> bool:
    """A reference is a v2 UUID, or a legacy v1 numeric id (matched against ``id_v1``)."""
    text = str(ref).strip()
    if text == item.get("id"):
        return True
    legacy = item.get("id_v1") or ""
    return bool(legacy) and legacy.rsplit("/", 1)[-1] == text


def _light_summary(raw: dict[str, Any], room: str | None) -> dict[str, Any]:
    ct = raw.get("color_temperature") or {}
    mirek = ct.get("mirek")
    return {
        "id": raw["id"],
        "id_v1": raw.get("id_v1"),
        "name": (raw.get("metadata") or {}).get("name", ""),
        "room": room,
        "on": (raw.get("on") or {}).get("on", False),
        "brightness": (raw.get("dimming") or {}).get("brightness"),
        "color_temperature_kelvin": mirek_to_kelvin(mirek) if mirek else None,
        "color_xy": (raw.get("color") or {}).get("xy"),
        "supports_color": "color" in raw,
        "supports_color_temperature": "color_temperature" in raw,
        "supports_dimming": "dimming" in raw,
    }


class HueService:
    def __init__(self, client: HueClient) -> None:
        self._client = client

    # ------------------------------------------------------------------ reads

    async def lights(self) -> list[dict[str, Any]]:
        raw_lights, rooms = await asyncio.gather(
            self._client.get("/resource/light"), self._client.get("/resource/room")
        )
        room_of_device = {
            child["rid"]: (room.get("metadata") or {}).get("name", "")
            for room in rooms
            for child in room.get("children", [])
            if child.get("rtype") == "device"
        }
        return [
            _light_summary(light, room_of_device.get((light.get("owner") or {}).get("rid")))
            for light in raw_lights
        ]

    async def groups(self) -> list[dict[str, Any]]:
        rooms, zones, grouped, raw_lights, homes = await asyncio.gather(
            self._client.get("/resource/room"),
            self._client.get("/resource/zone"),
            self._client.get("/resource/grouped_light"),
            self._client.get("/resource/light"),
            self._client.get("/resource/bridge_home"),
        )
        grouped_by_id = {g["id"]: g for g in grouped}
        light_name = {lt["id"]: (lt.get("metadata") or {}).get("name", "") for lt in raw_lights}
        lights_of_device: dict[str, list[str]] = {}
        for light in raw_lights:
            owner = (light.get("owner") or {}).get("rid")
            lights_of_device.setdefault(owner, []).append(light["id"])

        def members(item: dict[str, Any]) -> list[str]:
            ids: list[str] = []
            for child in item.get("children", []):
                if child.get("rtype") == "device":
                    ids.extend(lights_of_device.get(child["rid"], []))
                elif child.get("rtype") == "light":
                    ids.append(child["rid"])
            return ids

        result: list[dict[str, Any]] = []
        for kind, items in (("room", rooms), ("zone", zones), ("home", homes)):
            for item in items:
                gl_id = next(
                    (
                        s["rid"]
                        for s in item.get("services", [])
                        if s.get("rtype") == "grouped_light"
                    ),
                    None,
                )
                gl = grouped_by_id.get(gl_id, {})
                names = (
                    sorted(light_name.get(i, "") for i in members(item))
                    if kind != "home"
                    else sorted(light_name.values())
                )
                result.append(
                    {
                        "id": item["id"],
                        "id_v1": item.get("id_v1"),
                        "type": kind,
                        "name": (item.get("metadata") or {}).get("name", "Home"),
                        "grouped_light_id": gl_id,
                        "lights": names,
                        "on": (gl.get("on") or {}).get("on"),
                        "brightness": (gl.get("dimming") or {}).get("brightness"),
                    }
                )
        return result

    async def scenes(self) -> list[dict[str, Any]]:
        raw_scenes, groups = await asyncio.gather(
            self._client.get("/resource/scene"), self.groups()
        )
        group_by_id = {g["id"]: g for g in groups}
        result = []
        for scene in raw_scenes:
            group = group_by_id.get((scene.get("group") or {}).get("rid"), {})
            result.append(
                {
                    "id": scene["id"],
                    "id_v1": scene.get("id_v1"),
                    "name": (scene.get("metadata") or {}).get("name", ""),
                    "group_id": group.get("id"),
                    "group_name": group.get("name"),
                    "group_type": group.get("type"),
                    "active": (scene.get("status") or {}).get("active", "inactive") != "inactive",
                }
            )
        return result

    # ------------------------------------------------------------- resolution

    async def resolve_light(self, light_id: Ref | None, light_name: str) -> dict[str, Any]:
        lights = await self.lights()
        if not _unset(light_id):
            for light in lights:
                if _id_matches(light_id, light):  # type: ignore[arg-type]
                    return light
            raise NotFoundError(f"No light has the id '{light_id}'.")
        if not light_name.strip():
            raise InvalidInputError("Give a light_id or a light_name.")
        return resolve_by_name(light_name, lights, lambda x: x["name"], "light")

    async def resolve_group(self, group_id: Ref | None, group_name: str) -> dict[str, Any]:
        groups = await self.groups()
        if not _unset(group_id):
            for group in groups:
                if _id_matches(group_id, group):  # type: ignore[arg-type]
                    return group
            raise NotFoundError(f"No group has the id '{group_id}'.")
        if not group_name.strip():
            raise InvalidInputError("Give a group_id or a group_name (room or zone).")
        return resolve_by_name(group_name, groups, lambda x: x["name"], "group")

    async def find_lights(self, name: str) -> list[dict[str, Any]]:
        return find_matches(name, await self.lights(), lambda x: x["name"])

    async def resolve_scene(
        self,
        scene_id: Ref | None,
        scene_name: str,
        group_id: Ref | None = None,
        group_name: str = "",
    ) -> dict[str, Any]:
        scenes = await self.scenes()
        if not _unset(group_id) or group_name.strip():
            group = await self.resolve_group(group_id, group_name)
            scenes = [s for s in scenes if s["group_id"] == group["id"]]
        if not _unset(scene_id):
            for scene in scenes:
                if _id_matches(scene_id, scene):  # type: ignore[arg-type]
                    return scene
            raise NotFoundError(f"No scene has the id '{scene_id}' in the requested scope.")
        return resolve_by_name(
            scene_name,
            scenes,
            lambda x: x["name"],
            "scene",
            label=lambda x: f"{x['name']} ({x['group_name']})",
        )

    # --------------------------------------------------------------- commands

    async def set_light(self, light: dict[str, Any], body: dict[str, Any]) -> None:
        await self._client.put(f"/resource/light/{light['id']}", body)

    async def set_group(self, group: dict[str, Any], body: dict[str, Any]) -> None:
        if not group.get("grouped_light_id"):
            raise NotFoundError(f"Group '{group['name']}' cannot be controlled as a whole.")
        await self._client.put(f"/resource/grouped_light/{group['grouped_light_id']}", body)

    async def recall_scene(self, scene: dict[str, Any]) -> None:
        await self._client.put(f"/resource/scene/{scene['id']}", {"recall": {"action": "active"}})

    async def alert(self, light: dict[str, Any]) -> None:
        await self._client.put(f"/resource/light/{light['id']}", {"alert": {"action": "breathe"}})


# ------------------------------------------------------------ payload builders


def power_body(on: bool) -> dict[str, Any]:
    return {"on": {"on": on}}


def brightness_body(percent: float) -> dict[str, Any]:
    if not 0 <= percent <= 100:
        raise InvalidInputError("Brightness must be between 0 and 100.")
    if percent == 0:
        return power_body(False)
    return {**power_body(True), "dimming": {"brightness": float(percent)}}


def xy_body(x: float, y: float) -> dict[str, Any]:
    check_xy(x, y)
    return {**power_body(True), "color": {"xy": {"x": x, "y": y}}}


def temperature_body(kelvin: int) -> dict[str, Any]:
    return {**power_body(True), "color_temperature": {"mirek": kelvin_to_mirek(kelvin)}}


def require_capability(light: dict[str, Any], capability: str) -> None:
    if not light.get(f"supports_{capability}"):
        label = capability.replace("_", " ")
        raise InvalidInputError(f"Light '{light['name']}' does not support {label}.")
