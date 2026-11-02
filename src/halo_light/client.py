"""Thin asynchronous client for the Hue CLIP v2 API."""

from __future__ import annotations

from typing import Any

import httpx

from .errors import BridgeError

API_PREFIX = "/clip/v2"
KEY_HEADER = "hue-application-key"


def _describe_errors(errors: Any) -> str:
    if isinstance(errors, list):
        parts = [e.get("description", "") for e in errors if isinstance(e, dict)]
        text = "; ".join(p for p in parts if p)
        if text:
            return text
    return "unknown error"


class HueClient:
    """GET/PUT helper bound to one bridge.

    The bridge presents a certificate signed by a private Signify CA, so by default the
    certificate is not verified; pass ``ca_cert`` (PEM path) to pin it.
    """

    def __init__(
        self,
        host: str,
        app_key: str,
        *,
        ca_cert: str | None = None,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.host = host
        verify: Any = ca_cert if ca_cert else False
        self._http = httpx.AsyncClient(
            base_url=f"https://{host}{API_PREFIX}",
            headers={KEY_HEADER: app_key},
            verify=verify,
            timeout=timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get(self, path: str) -> list[dict[str, Any]]:
        return await self._request("GET", path)

    async def put(self, path: str, body: dict[str, Any]) -> list[dict[str, Any]]:
        return await self._request("PUT", path, json=body)

    async def _request(self, method: str, path: str, **kwargs: Any) -> list[dict[str, Any]]:
        try:
            response = await self._http.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise BridgeError("The Hue bridge did not answer in time.") from exc
        except httpx.HTTPError as exc:
            raise BridgeError(f"Cannot reach the Hue bridge ({type(exc).__name__}).") from exc
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        if response.status_code in (401, 403):
            raise BridgeError("The bridge rejected the application key (re-run the pairing).")
        errors = payload.get("errors")
        if response.status_code >= 400 or errors:
            raise BridgeError(
                f"The bridge returned an error (HTTP {response.status_code}): "
                f"{_describe_errors(errors)}."
            )
        data = payload.get("data", [])
        return data if isinstance(data, list) else []
