"""touch-grass MCP server (keyboard) + shared CLI entry point.

A long-running FastMCP server (streamable HTTP) that owns the ESP32 keyboard
serial link and exposes physical keyboard control as typed tools. The CLI here
also launches the *mouse* server (see mouse_server.py) — touch-grass runs one
instance per device, so `serve --device mouse` starts that one instead.

Tools return structured results ({"ok", "state", ...}) so an agent's
verification loop can confirm each action.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from mcp.server.fastmcp import FastMCP

from . import __version__
from .config import DEVICE_KEYBOARD, DEVICES, Config
from .detect import find_esp32_port, list_ports
from .keyboard import Keyboard
from .runtime import build_link

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
    return Keyboard(build_link(cfg))


def _serve_keyboard(cfg: Config) -> None:
    global _kb
    _kb = _init_link(cfg)
    mcp.settings.host = cfg.host
    mcp.settings.port = cfg.port
    print(f"touch-grass v{__version__} (keyboard) serving MCP on "
          f"http://{cfg.host}:{cfg.port}/mcp (serial: {_kb.link.port})", file=sys.stderr)
    mcp.run(transport="streamable-http")


def _build_device(cfg: Config):
    """Return a started device controller (Keyboard or Mouse) for one-shot use."""
    if cfg.device == DEVICE_KEYBOARD:
        return _init_link(cfg)
    from .mouse_server import init_link as init_mouse
    return init_mouse(cfg)


def _default_device() -> str:
    return os.environ.get("TOUCH_GRASS_DEVICE", DEVICE_KEYBOARD)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="touch-grass",
        description="MCP server exposing a physical ESP32 BLE keyboard/mouse to AI agents.",
    )
    sub = parser.add_subparsers(dest="command")
    for name, help_text in (
        ("serve", "run the MCP server (default)"),
        ("status", "print the current link state and exit"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument(
            "--device", choices=DEVICES, default=_default_device(),
            help="which device this instance controls (default: keyboard, or $TOUCH_GRASS_DEVICE)",
        )
    sub.add_parser("detect", help="list serial ports / detected ESP32 and exit")

    args = parser.parse_args()

    if args.command == "detect":
        print("Detected ESP32:", find_esp32_port() or "(none)")
        print("All ports:")
        for line in list_ports() or ["(none)"]:
            print("  " + line)
        return

    device = getattr(args, "device", None) or _default_device()
    cfg = Config.from_env(device)

    if args.command == "status":
        dev = _build_device(cfg)
        print(dev.status())
        dev.link.stop()
        return

    # Default action is to serve the configured device.
    if cfg.device == DEVICE_KEYBOARD:
        _serve_keyboard(cfg)
    else:
        from .mouse_server import serve as serve_mouse
        serve_mouse(cfg)


if __name__ == "__main__":
    main()
