"""A tiny in-memory Hue bridge served through ``httpx.MockTransport``."""

from __future__ import annotations

import copy
import json
from typing import Any

import httpx


def _light(lid: str, v1: int, name: str, device: str, *, color: bool = True) -> dict[str, Any]:
    light: dict[str, Any] = {
        "id": lid,
        "id_v1": f"/lights/{v1}",
        "metadata": {"name": name},
        "owner": {"rid": device, "rtype": "device"},
        "on": {"on": False},
        "dimming": {"brightness": 50.0},
        "color_temperature": {"mirek": 366},
    }
    if color:
        light["color"] = {"xy": {"x": 0.4, "y": 0.4}}
    return light


def default_resources() -> dict[str, list[dict[str, Any]]]:
    return {
        "light": [
            _light("l-plafond", 1, "Salon Plafond", "d1"),
            _light("l-lampadaire", 2, "Salon Lampadaire", "d2"),
            _light("l-cafe", 3, "Lampe Café", "d3", color=False),
            _light("l-chevet", 4, "Chevet", "d4"),
        ],
        "room": [
            {
                "id": "r-salon",
                "id_v1": "/groups/81",
                "metadata": {"name": "Salon"},
                "children": [
                    {"rid": "d1", "rtype": "device"},
                    {"rid": "d2", "rtype": "device"},
                    {"rid": "d3", "rtype": "device"},
                ],
                "services": [{"rid": "gl-salon", "rtype": "grouped_light"}],
            },
            {
                "id": "r-chambre",
                "id_v1": "/groups/82",
                "metadata": {"name": "Chambre"},
                "children": [{"rid": "d4", "rtype": "device"}],
                "services": [{"rid": "gl-chambre", "rtype": "grouped_light"}],
            },
        ],
        "zone": [
            {
                "id": "z-lecture",
                "id_v1": "/groups/90",
                "metadata": {"name": "Coin lecture"},
                "children": [{"rid": "l-cafe", "rtype": "light"}],
                "services": [{"rid": "gl-lecture", "rtype": "grouped_light"}],
            }
        ],
        "bridge_home": [
            {
                "id": "home",
                "id_v1": "/groups/0",
                "children": [],
                "services": [{"rid": "gl-home", "rtype": "grouped_light"}],
            }
        ],
        "grouped_light": [
            {"id": "gl-salon", "on": {"on": False}, "dimming": {"brightness": 40.0}},
            {"id": "gl-chambre", "on": {"on": True}, "dimming": {"brightness": 80.0}},
            {"id": "gl-lecture", "on": {"on": False}},
            {"id": "gl-home", "on": {"on": False}},
        ],
        "scene": [
            _scene("s-relax-salon", "abc1", "Relax", "r-salon"),
            _scene("s-relax-chambre", "abc2", "Relax", "r-chambre"),
            _scene("s-lecture", "abc3", "Lecture", "r-salon"),
            _scene("s-energie", "abc4", "Énergie", "r-salon"),
            _scene("s-nuit", "abc5", "Nuit étoilée", "r-chambre"),
        ],
    }


def _scene(sid: str, v1: str, name: str, room: str) -> dict[str, Any]:
    return {
        "id": sid,
        "id_v1": f"/scenes/{v1}",
        "metadata": {"name": name},
        "group": {"rid": room, "rtype": "room"},
        "status": {"active": "inactive"},
    }


class FakeBridge:
    """Records every request; applies PUT bodies to the stored resources."""

    def __init__(self, resources: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.resources = resources or default_resources()
        self.requests: list[httpx.Request] = []
        self.puts: list[tuple[str, dict[str, Any]]] = []
        self.fail_with: tuple[int, dict[str, Any]] | None = None
        self.raise_error: Exception | None = None

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.raise_error:
            raise self.raise_error
        if request.headers.get("hue-application-key") != "test-key":
            return httpx.Response(403, json={"errors": [{"description": "unauthorized user"}]})
        if self.fail_with:
            return httpx.Response(self.fail_with[0], json=self.fail_with[1])
        parts = request.url.path.removeprefix("/clip/v2/resource/").split("/")
        kind = parts[0]
        if request.method == "GET":
            return httpx.Response(
                200, json={"errors": [], "data": copy.deepcopy(self.resources.get(kind, []))}
            )
        body = json.loads(request.content)
        self.puts.append((request.url.path, body))
        return httpx.Response(200, json={"errors": [], "data": [{"rid": parts[1], "rtype": kind}]})
