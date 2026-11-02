"""Command line: serve (default), pair, discover."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence

from .config import default_config_path, load_settings, save_config, validate_host
from .discovery import discover_cloud, pick_single
from .errors import HueError
from .pairing import pair
from .server import create_server


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="halo-light", description="Hue MCP server")
    sub = parser.add_subparsers(dest="command")
    serve = sub.add_parser("serve", help="run the MCP server (default)")
    serve.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    pair_cmd = sub.add_parser("pair", help="pair with the bridge (press its link button)")
    pair_cmd.add_argument("--host", help="bridge address (default: HUE_BRIDGE_IP or discovery)")
    pair_cmd.add_argument("--timeout", type=float, default=60.0)
    sub.add_parser("discover", help="list bridges found by the Philips discovery service")
    return parser


async def _pair(host: str | None, timeout: float) -> None:
    settings = load_settings()
    address = validate_host(host) if host else settings.host
    if not address:
        address = pick_single(await discover_cloud())
    print(f"Press the link button on the bridge ({address}) now...", file=sys.stderr)
    keys = await pair(address, timeout=timeout)
    path = default_config_path()
    save_config(path, {"bridge_ip": address, **keys})
    print(f"Paired. Configuration saved to {path} (mode 600).")


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    try:
        if args.command == "pair":
            asyncio.run(_pair(args.host, args.timeout))
        elif args.command == "discover":
            for host in asyncio.run(discover_cloud()):
                print(host)
        else:
            create_server().run(transport=getattr(args, "transport", "stdio"))
    except HueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
