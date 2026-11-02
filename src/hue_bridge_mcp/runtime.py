"""Lazy runtime: builds the bridge client on first use so the server always starts."""

from __future__ import annotations

import asyncio

import httpx

from .client import HueClient
from .config import Settings, load_settings
from .discovery import find_bridge
from .errors import NotConfiguredError
from .service import HueService


class Runtime:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: HueClient | None = None,
        discovery_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._service = HueService(client) if client else None
        self._discovery_transport = discovery_transport
        self._lock = asyncio.Lock()

    @property
    def settings(self) -> Settings:
        if self._settings is None:
            self._settings = load_settings()
        return self._settings

    async def service(self) -> HueService:
        if self._service is not None:
            return self._service
        async with self._lock:
            if self._service is None:
                self._service = await self._build()
        return self._service

    async def _build(self) -> HueService:
        settings = self.settings
        if not settings.app_key:
            raise NotConfiguredError(
                "No Hue application key. Run 'hue-bridge-mcp pair' (press the bridge link "
                "button) or set HUE_APP_KEY."
            )
        host = settings.host or await find_bridge(self._discovery_transport)
        client = HueClient(
            host, settings.app_key, ca_cert=settings.ca_cert, timeout=settings.timeout
        )
        return HueService(client)

    def beat_env(self) -> dict[str, str]:
        """Credentials handed (without overriding) to the external hue_beat script."""
        settings = self.settings
        env: dict[str, str] = {}
        if settings.app_key:
            env["HUE_USER"] = settings.app_key
        if settings.host:
            env["HUE_BRIDGE_IP"] = settings.host
        return env
