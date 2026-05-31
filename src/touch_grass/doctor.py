"""`touch-grass doctor` — a boring, clear preflight check.

Verifies the MCP SDK is importable, serial ports are visible, the configured
keyboard/mouse serials resolve, the bind ports are free, and that both servers
can construct their tool sets (MCP discovery). Prints a human report or JSON.
"""

from __future__ import annotations

import socket

from .config import DEVICE_KEYBOARD, DEVICE_MOUSE, Config
from .detect import find_esp32_port, list_ports

EXPECTED_TOOL_COUNTS = {DEVICE_KEYBOARD: 7, DEVICE_MOUSE: 9}


def _check_mcp_sdk() -> tuple[bool, str]:
    try:
        import mcp  # noqa: F401
        from mcp.server.fastmcp import FastMCP  # noqa: F401
        return True, "ok"
    except Exception as e:  # pragma: no cover - only on broken installs
        return False, f"import failed: {e}"


def _discover_tools(device: str) -> tuple[bool, int, str]:
    """Import the device server and count its registered MCP tools."""
    import asyncio

    try:
        if device == DEVICE_KEYBOARD:
            from .server import mcp as dev_mcp
        else:
            from .mouse_server import mcp as dev_mcp
        tools = asyncio.run(dev_mcp.list_tools())
        return True, len(tools), "ok"
    except Exception as e:  # pragma: no cover
        return False, 0, f"discovery failed: {e}"


def _port_is_free(host: str, port: int) -> bool:
    probe_host = "127.0.0.1" if host == "0.0.0.0" else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((probe_host, port))
            return True
        except OSError:
            return False


def _serial_status(cfg: Config, available: list[str]) -> str:
    if cfg.mock:
        return "mock://no-hardware"
    resolved = cfg.serial or find_esp32_port()
    if not resolved:
        return "NOT SET (auto-detect found nothing)"
    devices = {line.split(" | ", 1)[0] for line in available}
    present = resolved in devices
    return f"{resolved} ({'present' if present else 'NOT FOUND among visible ports'})"


def collect(kb: Config, mouse: Config) -> dict:
    available = list_ports()
    sdk_ok, sdk_msg = _check_mcp_sdk()
    kb_disc_ok, kb_tools, kb_disc_msg = _discover_tools(DEVICE_KEYBOARD)
    ms_disc_ok, ms_tools, ms_disc_msg = _discover_tools(DEVICE_MOUSE)

    report = {
        "mode": "mock serial (no hardware)" if (kb.mock or mouse.mock) else "live hardware",
        "mcp_sdk": sdk_msg,
        "serial_ports_visible": available or [],
        "keyboard": {
            "endpoint": kb.endpoint,
            "serial": _serial_status(kb, available),
            "port_free": _port_is_free(kb.host, kb.port),
            "discovery_ok": kb_disc_ok,
            "tools": kb_tools,
            "tools_expected": EXPECTED_TOOL_COUNTS[DEVICE_KEYBOARD],
            "auth": "token" if kb.auth_token else "none",
        },
        "mouse": {
            "endpoint": mouse.endpoint,
            "serial": _serial_status(mouse, available),
            "port_free": _port_is_free(mouse.host, mouse.port),
            "discovery_ok": ms_disc_ok,
            "tools": ms_tools,
            "tools_expected": EXPECTED_TOOL_COUNTS[DEVICE_MOUSE],
            "auth": "token" if mouse.auth_token else "none",
        },
    }

    discovery_ready = (
        sdk_ok
        and kb_disc_ok and kb_tools == EXPECTED_TOOL_COUNTS[DEVICE_KEYBOARD]
        and ms_disc_ok and ms_tools == EXPECTED_TOOL_COUNTS[DEVICE_MOUSE]
    )
    report["result"] = "ready for MCP discovery" if discovery_ready else "NOT ready — see issues above"
    report["ok"] = discovery_ready
    return report


def format_human(report: dict) -> str:
    kb = report["keyboard"]
    ms = report["mouse"]
    lines = [
        f"Mode:              {report['mode']}",
        f"MCP SDK:           {report['mcp_sdk']}",
        f"Serial ports:      {', '.join(report['serial_ports_visible']) or '(none visible)'}",
        "",
        f"Keyboard endpoint: {kb['endpoint']}  (auth: {kb['auth']})",
        f"Keyboard serial:   {kb['serial']}",
        f"Keyboard port:     {'free' if kb['port_free'] else 'in use (already serving?)'}",
        f"Keyboard tools:    {kb['tools']}/{kb['tools_expected']} "
        f"({'ok' if kb['discovery_ok'] else 'FAILED'})",
        "",
        f"Mouse endpoint:    {ms['endpoint']}  (auth: {ms['auth']})",
        f"Mouse serial:      {ms['serial']}",
        f"Mouse port:        {'free' if ms['port_free'] else 'in use (already serving?)'}",
        f"Mouse tools:       {ms['tools']}/{ms['tools_expected']} "
        f"({'ok' if ms['discovery_ok'] else 'FAILED'})",
        "",
        f"Result: {report['result']}",
    ]
    return "\n".join(lines)
