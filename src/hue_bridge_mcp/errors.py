"""Exceptions of the project.

All of them derive from ``ToolError`` so that a failure raised inside a tool reaches the MCP
client as a tool result with ``isError`` set, with a message the model can act on.
"""

from mcp.server.mcpserver.exceptions import ToolError


class HueError(ToolError):
    """Base class of every anticipated failure."""


class NotConfiguredError(HueError):
    """No application key (or no reachable bridge) is configured."""


class InvalidInputError(HueError):
    """A tool argument is out of range or unusable."""


class NotFoundError(HueError):
    """No resource matches the requested identifier or name."""


class AmbiguousNameError(HueError):
    """Several resources match a partial name."""


class BridgeError(HueError):
    """The bridge is unreachable or answered with an error."""


class BeatUnavailableError(HueError):
    """The optional hue_beat extension is not installed or not configured."""
