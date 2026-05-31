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
import json
import os
import sys

from mcp.server.fastmcp import FastMCP

from . import __version__
from .auth import run_server
from .config import DEVICE_KEYBOARD, DEVICE_MOUSE, DEVICES, Config
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
    auth_note = "bearer-token auth ON" if cfg.auth_token else "no auth"
    print(f"touch-grass v{__version__} (keyboard) serving MCP on {cfg.endpoint} "
          f"(serial: {_kb.link.port}; {auth_note})", file=sys.stderr)
    run_server(mcp, cfg)


def _serve(cfg: Config) -> None:
    """Serve the device named by cfg.device."""
    if cfg.device == DEVICE_KEYBOARD:
        _serve_keyboard(cfg)
    else:
        from .mouse_server import serve as serve_mouse
        serve_mouse(cfg)


def _build_device(cfg: Config):
    """Return a started device controller (Keyboard or Mouse) for one-shot use."""
    if cfg.device == DEVICE_KEYBOARD:
        return _init_link(cfg)
    from .mouse_server import init_link as init_mouse
    return init_mouse(cfg)


def _default_device() -> str:
    return os.environ.get("TOUCH_GRASS_DEVICE", DEVICE_KEYBOARD)


def _serve_all(mock: bool) -> None:
    """Convenience launcher: run the keyboard and mouse servers as child processes.

    Uses subprocess (not multiprocessing) so it's robust across platforms and
    avoids the console-script re-import footgun of spawn on Windows.
    """
    import subprocess

    env = dict(os.environ)
    if mock:
        env["TOUCH_GRASS_MOCK_SERIAL"] = "1"

    procs = []
    for device in (DEVICE_KEYBOARD, DEVICE_MOUSE):
        cmd = [sys.executable, "-m", "touch_grass", "serve", "--device", device]
        procs.append(subprocess.Popen(cmd, env=env))
    print(f"touch-grass v{__version__} serve-all: keyboard :8765 + mouse :8766 "
          f"({'mock' if mock else 'live'}). Ctrl+C to stop.", file=sys.stderr)
    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="touch-grass",
        description="MCP servers exposing a physical ESP32 BLE keyboard/mouse to AI agents.",
    )
    sub = parser.add_subparsers(dest="command")

    for name, help_text in (
        ("serve", "run one device's MCP server (default)"),
        ("status", "print the current link state and exit"),
        ("config", "print the resolved config for a device and exit"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument(
            "--device", choices=DEVICES, default=_default_device(),
            help="which device (default: keyboard, or $TOUCH_GRASS_DEVICE)",
        )
        p.add_argument("--mock", action="store_true", help="no-hardware mock serial mode")
        if name in ("status", "config"):
            p.add_argument("--json", action="store_true", help="emit JSON")

    sa = sub.add_parser("serve-all", help="run BOTH device servers (keyboard :8765 + mouse :8766)")
    sa.add_argument("--mock", action="store_true", help="no-hardware mock serial mode")

    dt = sub.add_parser("detect", help="list serial ports / detected ESP32 and exit")
    dt.add_argument("--json", action="store_true", help="emit JSON")

    dr = sub.add_parser("doctor", help="preflight check for MCP discovery and exit")
    dr.add_argument("--mock", action="store_true", help="check assuming no-hardware mock mode")
    dr.add_argument("--json", action="store_true", help="emit JSON")

    args = parser.parse_args()

    # A --mock flag on any subcommand turns on mock mode for that invocation.
    if getattr(args, "mock", False):
        os.environ["TOUCH_GRASS_MOCK_SERIAL"] = "1"

    if args.command == "detect":
        if getattr(args, "json", False):
            print(json.dumps({"detected": find_esp32_port(), "ports": list_ports()}, indent=2))
        else:
            print("Detected ESP32:", find_esp32_port() or "(none)")
            print("All ports:")
            for line in list_ports() or ["(none)"]:
                print("  " + line)
        return

    if args.command == "doctor":
        from . import doctor as _doc

        report = _doc.collect(Config.from_env(DEVICE_KEYBOARD), Config.from_env(DEVICE_MOUSE))
        if getattr(args, "json", False):
            print(json.dumps(report, indent=2))
        else:
            print(_doc.format_human(report))
        raise SystemExit(0 if report["ok"] else 1)

    if args.command == "serve-all":
        _serve_all(getattr(args, "mock", False))
        return

    device = getattr(args, "device", None) or _default_device()
    cfg = Config.from_env(device)

    if args.command == "config":
        if getattr(args, "json", False):
            print(json.dumps(cfg.as_dict(), indent=2))
        else:
            for k, v in cfg.as_dict().items():
                print(f"{k}: {v}")
        return

    if args.command == "status":
        dev = _build_device(cfg)
        res = dev.status()
        print(json.dumps(res) if getattr(args, "json", False) else res)
        dev.link.stop()
        return

    # Default action is to serve the configured device.
    _serve(cfg)


if __name__ == "__main__":
    main()
