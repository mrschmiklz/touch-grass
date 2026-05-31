"""Runtime configuration, loaded from environment variables.

touch-grass runs as one server *per device* (a keyboard instance and a mouse
instance), so each process is told which device it controls and resolves its own
serial port and default MCP port from that.

Serial-port resolution (both ESP32 boards are CP210x, so auto-detect can't tell
them apart — pin them explicitly on a two-device host):
  * keyboard: TOUCH_GRASS_KB_SERIAL    -> TOUCH_GRASS_SERIAL -> auto-detect
  * mouse:    TOUCH_GRASS_MOUSE_SERIAL -> TOUCH_GRASS_SERIAL -> auto-detect

Set TOUCH_GRASS_MOCK_SERIAL=1 to run with no hardware (safe discovery/CI mode).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

DEVICE_KEYBOARD = "keyboard"
DEVICE_MOUSE = "mouse"
DEVICES = (DEVICE_KEYBOARD, DEVICE_MOUSE)

# Per-device default MCP bind ports (so the two servers don't collide).
_DEFAULT_PORTS = {DEVICE_KEYBOARD: 8765, DEVICE_MOUSE: 8766}

_LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")


@dataclass(frozen=True)
class Config:
    device: str             # "keyboard" | "mouse"
    serial: str | None      # serial device path; None => auto-detect
    baud: int
    host: str               # MCP bind host
    port: int               # MCP bind port
    mock: bool              # mock serial (no hardware) mode
    auth_token: str | None  # bearer token required on the MCP endpoint, if set
    unsafe_no_auth: bool     # allow binding to a non-loopback host with no token

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
        mock = _bool_env("TOUCH_GRASS_MOCK_SERIAL", False)
        auth_token = os.environ.get("TOUCH_GRASS_AUTH_TOKEN") or None
        unsafe_no_auth = _bool_env("TOUCH_GRASS_UNSAFE_NO_AUTH", False)
        return cls(
            device=device, serial=serial, baud=baud, host=host, port=port,
            mock=mock, auth_token=auth_token, unsafe_no_auth=unsafe_no_auth,
        )

    @property
    def endpoint(self) -> str:
        return f"http://{self.host}:{self.port}/mcp"

    @property
    def host_is_loopback(self) -> bool:
        return self.host in _LOOPBACK_HOSTS

    def as_dict(self) -> dict:
        """Resolved config for `touch-grass config`/`doctor --json` (token redacted)."""
        return {
            "device": self.device,
            "serial": "mock://no-hardware" if self.mock else self.serial,
            "baud": self.baud,
            "host": self.host,
            "port": self.port,
            "endpoint": self.endpoint,
            "mock_serial": self.mock,
            "auth": "token" if self.auth_token else "none",
        }


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        print(
            f"[touch-grass] warning: {name}={raw!r} is not an integer; "
            f"using default {default}.",
            file=sys.stderr,
        )
        return default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")
