"""MCP server factory."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .beat import BeatAdapter
from .runtime import Runtime
from .tools import register_tools

SERVER_NAME = "Philips Hue Bridge"


def create_server(runtime: Runtime | None = None, beat: BeatAdapter | None = None) -> MCPServer:
    """Build the server. ``runtime`` and ``beat`` can be injected (tests)."""
    server = MCPServer(SERVER_NAME)
    register_tools(server, runtime or Runtime(), beat)
    return server
