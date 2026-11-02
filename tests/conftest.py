from __future__ import annotations

import json

import pytest
from mcp import Client

from fake_bridge import FakeBridge
from halo_light.beat import BeatAdapter
from halo_light.client import HueClient
from halo_light.runtime import Runtime
from halo_light.server import create_server


@pytest.fixture
def bridge() -> FakeBridge:
    return FakeBridge()


@pytest.fixture
def runtime(bridge: FakeBridge) -> Runtime:
    client = HueClient("192.0.2.10", "test-key", transport=bridge.transport())
    return Runtime(client=client)


class Session:
    """Opens an in-process MCP client per call (anyio scopes cannot span pytest fixtures)."""

    def __init__(self, server) -> None:
        self._server = server

    async def call_tool(self, name: str, arguments: dict | None = None):
        async with Client(self._server) as client:
            return await client.call_tool(name, arguments or {})

    async def list_tools(self):
        async with Client(self._server) as client:
            return await client.list_tools()


@pytest.fixture
def mcp_client(runtime: Runtime) -> Session:
    beat = BeatAdapter(env={})  # no HUE_BEAT_PATH: the extension is absent
    return Session(create_server(runtime, beat))


def text_of(result) -> str:
    return "".join(part.text for part in result.content if part.type == "text")


def json_of(result):
    return json.loads(text_of(result))
