"""touch-grass mouse MCP server.

A FastMCP server (streamable HTTP) that owns the ESP32 *mouse* serial link and
exposes physical pointer control as typed tools. Runs as its own instance,
separate from the keyboard server (its own port + its own serial device), so
Hermes connects to two endpoints — one per device.

Tools return structured results ({"ok", "state", ...}) so an agent's
verification loop can confirm each action.
"""

from __future__ import annotations

import asyncio
import sys

from mcp.server.fastmcp import FastMCP

from . import __version__
from .auth import run_server
from .config import Config
from .mouse import Mouse
from .runtime import build_link

mcp = FastMCP(
    "touch-grass-mouse",
    instructions=(
        "Physical mouse control via a paired ESP32 Bluetooth mouse. "
        "Call mouse_wait_ready first and proceed only when state == 'READY'. "
        "Movement is RELATIVE (dx, dy in pixels; +x right, +y down). "
        "Every tool returns {ok, state, ...}; verify ok after each action."
    ),
)

_mouse: Mouse | None = None


def _m() -> Mouse:
    if _mouse is None:
        raise RuntimeError("serial link not initialized")
    return _mouse


# ── Tools ─────────────────────────────────────────────────────────────────────
@mcp.tool()
async def mouse_status() -> dict:
    """Return the current BLE link state: READY, CONNECTED_NOT_READY, or DISCONNECTED."""
    return await asyncio.to_thread(_m().status)


@mcp.tool()
async def mouse_wait_ready(timeout_s: float = 30.0) -> dict:
    """Block until the mouse is READY (host subscribed) or timeout. Returns {ok, ready, state}."""
    return await asyncio.to_thread(_m().wait_ready, timeout_s)


@mcp.tool()
async def mouse_move(dx: int, dy: int) -> dict:
    """Move the pointer by a RELATIVE offset in pixels (+dx = right, +dy = down).

    Large deltas are auto-chunked by the firmware. There are no absolute
    coordinates; move relative to the current position.
    """
    return await asyncio.to_thread(_m().move, dx, dy)


@mcp.tool()
async def mouse_click(button: str = "LEFT") -> dict:
    """Click a button (press + release). Valid: LEFT, RIGHT, MIDDLE."""
    return await asyncio.to_thread(_m().click, button)


@mcp.tool()
async def mouse_button_down(button: str = "LEFT") -> dict:
    """Press and hold a button (start a drag). Valid: LEFT, RIGHT, MIDDLE. Pair with mouse_button_up."""
    return await asyncio.to_thread(_m().button_down, button)


@mcp.tool()
async def mouse_button_up(button: str = "LEFT") -> dict:
    """Release a held button (end a drag). Valid: LEFT, RIGHT, MIDDLE."""
    return await asyncio.to_thread(_m().button_up, button)


@mcp.tool()
async def mouse_scroll(amount: int) -> dict:
    """Scroll the vertical wheel. Positive = up, negative = down."""
    return await asyncio.to_thread(_m().scroll, amount)


@mcp.tool()
async def mouse_release() -> dict:
    """Release all currently held mouse buttons."""
    return await asyncio.to_thread(_m().release)


@mcp.tool()
async def mouse_pair(confirm: bool = False) -> dict:
    """Clear all bonds and re-advertise for fresh pairing. Destructive; requires confirm=true."""
    return await asyncio.to_thread(_m().pair, confirm)


# ── Startup ─────────────────────────────────────────────────────────────────────
def init_link(cfg: Config) -> Mouse:
    return Mouse(build_link(cfg))


def serve(cfg: Config) -> None:
    global _mouse
    _mouse = init_link(cfg)
    auth_note = "bearer-token auth ON" if cfg.auth_token else "no auth"
    print(f"touch-grass v{__version__} (mouse) serving MCP on {cfg.endpoint} "
          f"(serial: {_mouse.link.port}; {auth_note})", file=sys.stderr)
    run_server(mcp, cfg)
