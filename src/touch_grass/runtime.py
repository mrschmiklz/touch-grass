"""Shared startup helpers used by both the keyboard and mouse servers."""

from __future__ import annotations

from .config import Config
from .detect import find_esp32_port, list_ports
from .link import MockLink, SerialLink


def build_link(cfg: Config):
    """Resolve the serial port for this device and open a started link.

    Returns a MockLink when mock mode is enabled (no hardware needed). Otherwise
    opens a real SerialLink, raising SystemExit with a helpful message if no port
    can be found — both ESP32 boards look identical to auto-detect and should be
    pinned explicitly.
    """
    if cfg.mock:
        link = MockLink()
        link.start()
        return link

    port = cfg.serial or find_esp32_port()
    if not port:
        env_hint = (
            "TOUCH_GRASS_MOUSE_SERIAL" if cfg.device == "mouse" else "TOUCH_GRASS_KB_SERIAL"
        )
        raise SystemExit(
            f"No ESP32 serial port found for the {cfg.device}. Set {env_hint} "
            f"(or TOUCH_GRASS_SERIAL) to the device path, or run with "
            f"TOUCH_GRASS_MOCK_SERIAL=1 for no-hardware discovery. "
            "Available ports:\n  " + "\n  ".join(list_ports() or ["(none)"])
        )
    link = SerialLink(port, cfg.baud)
    link.start()
    return link
