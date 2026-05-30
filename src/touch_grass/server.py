"""touch-grass MCP server.

A long-running FastMCP server (streamable HTTP) that owns the ESP32 serial link
and exposes physical keyboard control as typed tools. Designed to run as a
sidecar container that Hermes (and its subagents) connect to over a private
network.

Tools return structured results ({"ok", "state", ...}) so an agent's
verification loop can confirm each action.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from mcp.server.fastmcp import FastMCP

from . import __version__
from .config import Config
from .detect import find_esp32_port, list_ports
from .keyboard import Keyboard
from .link import SerialLink

mcp = FastMCP(
    "touch-grass",
    instructions=(
        "Physical keyboard control via a paired ESP32 Bluetooth keyboard. "
        "Call keyboard_wait_ready first and proceed only when state == 'READY'. "
        "Every tool returns {ok, state, ...}; verify ok after each action."
    ),
)

_kb: Keyboard | None = None


def _keyboard() -> Keyboard:
    if _kb is None:
        raise RuntimeError("serial link not initialized")
    return _kb


# ── Tools ─────────────────────────────────────────────────────────────────────
@mcp.tool()
async def keyboard_status() -> dict:
    """Return the current BLE link state: READY, CONNECTED_NOT_READY, or DISCONNECTED."""
    return await asyncio.to_thread(_keyboard().status)


@mcp.tool()
async def keyboard_wait_ready(timeout_s: float = 30.0) -> dict:
    """Block until the keyboard is READY (host subscribed) or timeout. Returns {ok, ready, state}."""
    return await asyncio.to_thread(_keyboard().wait_ready, timeout_s)


@mcp.tool()
async def keyboard_type(text: str, press_enter: bool = False) -> dict:
    """Type a string on the target machine. Set press_enter=true to append Enter."""
    return await asyncio.to_thread(_keyboard().type, text, press_enter)


@mcp.tool()
async def keyboard_key(name: str) -> dict:
    """Press a single special key.

    Valid names: ENTER RETURN ESC BACKSPACE TAB SPACE MINUS EQUALS CAPS
    PRINTSCREEN SCROLLLOCK PAUSE INSERT HOME PAGEUP DELETE END PAGEDOWN
    RIGHT LEFT DOWN UP NUMLOCK F1-F12.
    """
    return await asyncio.to_thread(_keyboard().key, name)


@mcp.tool()
async def keyboard_combo(combo: str) -> dict:
    """Press a modifier combo, e.g. 'CTRL+C', 'WIN+R', 'CTRL+SHIFT+T'.

    Modifiers: CTRL SHIFT ALT WIN (alias GUI). Final token is the key.
    """
    return await asyncio.to_thread(_keyboard().combo, combo)


@mcp.tool()
async def keyboard_media(name: str) -> dict:
    """Press a media key. Valid names: NEXT PREV STOP PLAY PAUSE MUTE VOLUP VOLDOWN."""
    return await asyncio.to_thread(_keyboard().media, name)


@mcp.tool()
async def keyboard_pair(confirm: bool = False) -> dict:
    """Clear all bonds and re-advertise for fresh pairing. Destructive; requires confirm=true."""
    return await asyncio.to_thread(_keyboard().pair, confirm)


# ── Startup / CLI ───────────────────────────────────────────────────────────────
def _init_link(cfg: Config) -> Keyboard:
    port = cfg.serial or find_esp32_port()
    if not port:
        raise SystemExit(
            "No ESP32 serial port found. Set TOUCH_GRASS_SERIAL, or check the USB "
            "device passthrough. Available ports:\n  " + "\n  ".join(list_ports() or ["(none)"])
        )
    link = SerialLink(port, cfg.baud)
    link.start()
    return Keyboard(link)


def _serve(cfg: Config) -> None:
    global _kb
    _kb = _init_link(cfg)
    mcp.settings.host = cfg.host
    mcp.settings.port = cfg.port
    print(f"touch-grass v{__version__} serving MCP on http://{cfg.host}:{cfg.port}/mcp "
          f"(serial: {_kb.link.port})", file=sys.stderr)
    mcp.run(transport="streamable-http")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="touch-grass",
        description="MCP server exposing a physical ESP32 BLE keyboard to AI agents.",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the MCP server (default)")
    sub.add_parser("status", help="print the current link state and exit")
    sub.add_parser("detect", help="list serial ports / detected ESP32 and exit")

    args = parser.parse_args()
    cfg = Config.from_env()

    if args.command == "detect":
        print("Detected ESP32:", find_esp32_port() or "(none)")
        print("All ports:")
        for line in list_ports() or ["(none)"]:
            print("  " + line)
        return

    if args.command == "status":
        kb = _init_link(cfg)
        print(kb.status())
        kb.link.stop()
        return

    # Default action is to serve.
    _serve(cfg)


if __name__ == "__main__":
    main()
