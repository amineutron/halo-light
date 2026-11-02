"""Pairing with the bridge: the user presses the link button, we get an application key."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from .config import validate_host
from .errors import BridgeError

LINK_BUTTON_NOT_PRESSED = 101
DEVICE_TYPE = "hue-bridge-mcp#server"


async def pair(
    host: str,
    *,
    timeout: float = 60.0,
    interval: float = 2.0,
    transport: httpx.AsyncBaseTransport | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, str]:
    """Poll the bridge until the link button is pressed.

    Returns ``{"app_key": ..., "client_key": ...}``. Raises ``BridgeError`` on timeout or on any
    answer other than "link button not pressed".
    """
    host = validate_host(host)
    deadline = clock() + timeout
    body = {"devicetype": DEVICE_TYPE, "generateclientkey": True}
    async with httpx.AsyncClient(verify=False, timeout=10.0, transport=transport) as http:
        while True:
            try:
                response = await http.post(f"https://{host}/api", json=body)
                payload: Any = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise BridgeError(f"Cannot reach the bridge ({type(exc).__name__}).") from exc
            entry = payload[0] if isinstance(payload, list) and payload else {}
            success = entry.get("success") if isinstance(entry, dict) else None
            if isinstance(success, dict) and success.get("username"):
                return {
                    "app_key": str(success["username"]),
                    "client_key": str(success.get("clientkey", "")),
                }
            error = entry.get("error", {}) if isinstance(entry, dict) else {}
            if error.get("type") != LINK_BUTTON_NOT_PRESSED:
                raise BridgeError(f"Pairing refused: {error.get('description', 'unknown error')}.")
            if clock() >= deadline:
                raise BridgeError("Timed out: the link button was not pressed.")
            await sleep(interval)
