import httpx
import pytest

from halo_light.discovery import discover_cloud, find_bridge, pick_single
from halo_light.errors import BridgeError, NotConfiguredError
from halo_light.pairing import pair


def transport_returning(*responses):
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    return httpx.MockTransport(handler)


async def no_sleep(_):
    return None


async def test_pairing_waits_for_the_button_then_returns_keys():
    pending = httpx.Response(200, json=[{"error": {"type": 101, "description": "link button"}}])
    done = httpx.Response(200, json=[{"success": {"username": "KEY", "clientkey": "CK"}}])
    keys = await pair("192.0.2.1", transport=transport_returning(pending, pending, done),
                      sleep=no_sleep)  # fmt: skip
    assert keys == {"app_key": "KEY", "client_key": "CK"}


async def test_pairing_times_out():
    pending = httpx.Response(200, json=[{"error": {"type": 101, "description": "x"}}])
    ticks = iter(range(0, 1000, 30))
    with pytest.raises(BridgeError, match="link button"):
        await pair("192.0.2.1", timeout=60, transport=transport_returning(pending),
                   sleep=no_sleep, clock=lambda: next(ticks))  # fmt: skip


async def test_pairing_surfaces_other_errors_and_bad_host():
    refused = httpx.Response(200, json=[{"error": {"type": 7, "description": "invalid value"}}])
    with pytest.raises(BridgeError, match="invalid value"):
        await pair("192.0.2.1", transport=transport_returning(refused), sleep=no_sleep)
    from halo_light.errors import InvalidInputError

    with pytest.raises(InvalidInputError):
        await pair("http://evil/")


async def test_cloud_discovery_and_single_bridge_rule():
    ok = httpx.Response(200, json=[{"id": "abc", "internalipaddress": "192.0.2.7"}])
    assert await discover_cloud(transport_returning(ok)) == ["192.0.2.7"]
    assert await find_bridge(transport_returning(ok)) == "192.0.2.7"


async def test_discovery_failure_and_ambiguity():
    with pytest.raises(BridgeError):
        await discover_cloud(transport_returning(httpx.Response(500)))
    with pytest.raises(NotConfiguredError, match="HUE_BRIDGE_IP"):
        await find_bridge(transport_returning(httpx.Response(200, json=[])))
    with pytest.raises(NotConfiguredError, match="Several"):
        pick_single(["192.0.2.1", "192.0.2.2"])
