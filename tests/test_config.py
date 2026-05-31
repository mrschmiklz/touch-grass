"""Unit tests for per-device config resolution (serial port + default MCP port)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from touch_grass.config import Config  # noqa: E402

_ENV_KEYS = (
    "TOUCH_GRASS_SERIAL", "TOUCH_GRASS_KB_SERIAL", "TOUCH_GRASS_MOUSE_SERIAL",
    "TOUCH_GRASS_PORT", "TOUCH_GRASS_HOST", "TOUCH_GRASS_BAUD",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in _ENV_KEYS:
        monkeypatch.delenv(k, raising=False)


def test_default_ports_differ_per_device():
    assert Config.from_env("keyboard").port == 8765
    assert Config.from_env("mouse").port == 8766


def test_per_device_serial_env(monkeypatch):
    monkeypatch.setenv("TOUCH_GRASS_KB_SERIAL", "COM5")
    monkeypatch.setenv("TOUCH_GRASS_MOUSE_SERIAL", "COM7")
    assert Config.from_env("keyboard").serial == "COM5"
    assert Config.from_env("mouse").serial == "COM7"


def test_generic_serial_is_fallback(monkeypatch):
    monkeypatch.setenv("TOUCH_GRASS_SERIAL", "/dev/ttyUSB9")
    assert Config.from_env("keyboard").serial == "/dev/ttyUSB9"
    # A device-specific var wins over the generic fallback.
    monkeypatch.setenv("TOUCH_GRASS_MOUSE_SERIAL", "/dev/ttyUSB1")
    assert Config.from_env("mouse").serial == "/dev/ttyUSB1"


def test_explicit_port_overrides_default(monkeypatch):
    monkeypatch.setenv("TOUCH_GRASS_PORT", "9000")
    assert Config.from_env("mouse").port == 9000


def test_unknown_device_rejected():
    with pytest.raises(ValueError):
        Config.from_env("trackball")
