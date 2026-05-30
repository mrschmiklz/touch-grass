"""Auto-detect the ESP32 serial port across Linux / macOS / Windows.

Search order:
  1. A port whose description/hwid matches a known USB-UART chip
     (CP210x, CH340/CH910x, FTDI, or a generic USB serial / ACM device).
  2. If exactly one serial port is present, use it.
Returns the device path (e.g. ``/dev/ttyUSB0`` or ``COM5``) or ``None``.
"""

from __future__ import annotations

import serial.tools.list_ports

# Substrings (lowercased) that strongly suggest an ESP32 dev-board USB bridge.
_KNOWN_SIGNATURES = (
    "cp210",        # Silicon Labs CP210x (very common on ESP32 dev boards)
    "ch340",
    "ch910",
    "ch343",
    "ftdi",
    "ft232",
    "usb serial",
    "usb-serial",
    "usb to uart",
    "espressif",
    "esp32",
)


def find_esp32_port() -> str | None:
    """Return the best-guess ESP32 serial device, or None if none found."""
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        return None

    for p in ports:
        haystack = f"{p.description} {p.hwid} {p.manufacturer or ''}".lower()
        if any(sig in haystack for sig in _KNOWN_SIGNATURES):
            return p.device

    # Fall back to the sole serial port, if there's exactly one.
    if len(ports) == 1:
        return ports[0].device

    return None


def list_ports() -> list[str]:
    """Return a human-readable list of available serial ports."""
    return [f"{p.device} | {p.description}" for p in serial.tools.list_ports.comports()]
