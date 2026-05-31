"""Runtime configuration, loaded from environment variables.

touch-grass runs as one server *per device* (a keyboard instance and a mouse
instance), so each process is told which device it controls and resolves its own
serial port and default MCP port from that.

Serial-port resolution (both ESP32 boards are CP210x, so auto-detect can't tell
them apart — pin them explicitly on a two-device host):
  * keyboard: TOUCH_GRASS_KB_SERIAL    -> TOUCH_GRASS_SERIAL -> auto-detect
  * mouse:    TOUCH_GRASS_MOUSE_SERIAL -> TOUCH_GRASS_SERIAL -> auto-detect
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEVICE_KEYBOARD = "keyboard"
DEVICE_MOUSE = "mouse"
DEVICES = (DEVICE_KEYBOARD, DEVICE_MOUSE)

# Per-device default MCP bind ports (so the two servers don't collide).
_DEFAULT_PORTS = {DEVICE_KEYBOARD: 8765, DEVICE_MOUSE: 8766}


@dataclass(frozen=True)
class Config:
    device: str             # "keyboard" | "mouse"
    serial: str | None      # serial device path; None => auto-detect
    baud: int
    host: str               # MCP bind host
    port: int               # MCP bind port

    @classmethod
    def from_env(cls, device: str = DEVICE_KEYBOARD) -> "Config":
        device = (device or DEVICE_KEYBOARD).lower()
        if device not in DEVICES:
            raise ValueError(f"unknown device '{device}'; expected one of {DEVICES}")

        if device == DEVICE_MOUSE:
            serial = os.environ.get("TOUCH_GRASS_MOUSE_SERIAL")
        else:
            serial = os.environ.get("TOUCH_GRASS_KB_SERIAL")
        # Generic fallback (handy for a single-device host) then auto-detect.
        serial = serial or os.environ.get("TOUCH_GRASS_SERIAL") or None

        baud = _int_env("TOUCH_GRASS_BAUD", 115200)
        host = os.environ.get("TOUCH_GRASS_HOST", "127.0.0.1")
        port = _int_env("TOUCH_GRASS_PORT", _DEFAULT_PORTS[device])
        return cls(device=device, serial=serial, baud=baud, host=host, port=port)


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default
