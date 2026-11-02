"""Bridge discovery: Philips cloud endpoint, with an optional mDNS fallback."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from .config import validate_host
from .errors import BridgeError, NotConfiguredError

DISCOVERY_URL = "https://discovery.meethue.com"
MDNS_SERVICE = "_hue._tcp.local."


async def discover_cloud(transport: httpx.AsyncBaseTransport | None = None) -> list[str]:
    """Ask ``discovery.meethue.com`` for the bridges seen from this public IP address."""
    try:
        async with httpx.AsyncClient(timeout=10.0, transport=transport) as http:
            response = await http.get(DISCOVERY_URL)
            response.raise_for_status()
            entries: Any = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise BridgeError(f"Bridge discovery failed ({type(exc).__name__}).") from exc
    hosts: list[str] = []
    for entry in entries if isinstance(entries, list) else []:
        address = entry.get("internalipaddress") if isinstance(entry, dict) else None
        if isinstance(address, str):
            hosts.append(validate_host(address))
    return hosts


def _discover_mdns_blocking(timeout: float) -> list[str]:  # pragma: no cover
    try:
        from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
    except ImportError as exc:
        raise BridgeError("mDNS discovery needs the optional 'zeroconf' package.") from exc

    found: list[str] = []

    class Listener(ServiceListener):
        def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            info = zc.get_service_info(type_, name)
            if info:
                found.extend(info.parsed_addresses())

        def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            pass

        def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            pass

    zc = Zeroconf()
    try:
        ServiceBrowser(zc, MDNS_SERVICE, Listener())
        import time

        time.sleep(timeout)
    finally:
        zc.close()
    return sorted(set(found))


async def discover_mdns(timeout: float = 3.0) -> list[str]:  # pragma: no cover
    return await asyncio.to_thread(_discover_mdns_blocking, timeout)


def pick_single(hosts: list[str]) -> str:
    """Return the only bridge found, or raise with guidance."""
    unique = sorted(set(hosts))
    if len(unique) == 1:
        return unique[0]
    if not unique:
        raise NotConfiguredError(
            "No Hue bridge found. Set HUE_BRIDGE_IP or run 'hue-bridge-mcp discover'."
        )
    raise NotConfiguredError(
        f"Several bridges found ({', '.join(unique)}). Set HUE_BRIDGE_IP to choose one."
    )


async def find_bridge(transport: httpx.AsyncBaseTransport | None = None) -> str:
    """Cloud discovery first, then mDNS when the cloud finds nothing."""
    try:
        hosts = await discover_cloud(transport)
    except BridgeError:
        hosts = []
    if not hosts and transport is None:  # pragma: no cover
        try:
            hosts = await discover_mdns()
        except BridgeError:
            hosts = []
    return pick_single(hosts)
