"""Runtime configuration, loaded from environment variables.

All settings are optional; sensible defaults let the server come up on a host
with a single ESP32 attached.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    serial: str | None      # serial device path; None => auto-detect
    baud: int
    host: str               # MCP bind host
    port: int               # MCP bind port

    @classmethod
    def from_env(cls) -> "Config":
        serial = os.environ.get("TOUCH_GRASS_SERIAL") or None
        baud = _int_env("TOUCH_GRASS_BAUD", 115200)
        host = os.environ.get("TOUCH_GRASS_HOST", "127.0.0.1")
        port = _int_env("TOUCH_GRASS_PORT", 8765)
        return cls(serial=serial, baud=baud, host=host, port=port)


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default
