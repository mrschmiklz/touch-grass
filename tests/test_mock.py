"""Mock-mode + MCP-discovery tests — the contract CI should guard.

These run with no hardware: they assert the mock link refuses real actions
safely, the device controllers behave, and both servers expose their tool sets.
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from touch_grass.keyboard import Keyboard            # noqa: E402
from touch_grass.link import MOCK_PORT, MockLink, STATE_DISCONNECTED  # noqa: E402
from touch_grass.mouse import Mouse                  # noqa: E402


# ── Mock link safety ──────────────────────────────────────────────────────────
def test_mock_status_is_disconnected():
    link = MockLink()
    assert link.port == MOCK_PORT
    assert link.query("STATUS") == STATE_DISCONNECTED


def test_mock_refuses_real_actions():
    link = MockLink()
    assert link.query("TYPE hello") == "ERR:NO_HARDWARE"
    assert link.query("MOVE 10 10") == "ERR:NO_HARDWARE"
    assert link.query("PAIR") == "ERR:NO_HARDWARE"


def test_keyboard_type_is_safe_in_mock():
    kb = Keyboard(MockLink())
    res = kb.type("rm -rf /")            # would be catastrophic on real hardware
    assert res["ok"] is False
    assert res["response"] == "ERR:NO_HARDWARE"


def test_mouse_click_is_safe_in_mock():
    m = Mouse(MockLink())
    res = m.click("LEFT")
    assert res["ok"] is False
    assert res["response"] == "ERR:NO_HARDWARE"


def test_status_ok_in_mock():
    assert Keyboard(MockLink()).status() == {"ok": True, "state": STATE_DISCONNECTED}
    assert Mouse(MockLink()).status() == {"ok": True, "state": STATE_DISCONNECTED}


def test_pair_still_requires_confirm_in_mock():
    kb = Keyboard(MockLink())
    assert kb.pair()["ok"] is False          # refused without confirm
    assert kb.pair(confirm=True)["ok"] is False  # confirm passes guard, hardware refuses


# ── MCP discovery contract ──────────────────────────────────────────────────────
def test_keyboard_server_exposes_7_tools():
    from touch_grass.server import mcp as kb_mcp

    tools = asyncio.run(kb_mcp.list_tools())
    names = {t.name for t in tools}
    assert len(names) == 7
    assert "keyboard_type" in names and "keyboard_pair" in names


def test_mouse_server_exposes_9_tools():
    from touch_grass.mouse_server import mcp as ms_mcp

    tools = asyncio.run(ms_mcp.list_tools())
    names = {t.name for t in tools}
    assert len(names) == 9
    assert "mouse_move" in names and "mouse_click" in names


# ── Auth policy ──────────────────────────────────────────────────────────────
def test_auth_required_on_non_loopback(monkeypatch):
    from touch_grass.auth import auth_policy_error
    from touch_grass.config import Config

    for k in ("TOUCH_GRASS_AUTH_TOKEN", "TOUCH_GRASS_UNSAFE_NO_AUTH"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("TOUCH_GRASS_HOST", "0.0.0.0")
    cfg = Config.from_env("keyboard")
    assert auth_policy_error(cfg) is not None        # refuses

    monkeypatch.setenv("TOUCH_GRASS_AUTH_TOKEN", "secret")
    assert auth_policy_error(Config.from_env("keyboard")) is None  # token allows

    monkeypatch.delenv("TOUCH_GRASS_AUTH_TOKEN")
    monkeypatch.setenv("TOUCH_GRASS_UNSAFE_NO_AUTH", "1")
    assert auth_policy_error(Config.from_env("keyboard")) is None  # explicit opt-in allows


def test_loopback_needs_no_auth(monkeypatch):
    from touch_grass.auth import auth_policy_error
    from touch_grass.config import Config

    for k in ("TOUCH_GRASS_AUTH_TOKEN", "TOUCH_GRASS_UNSAFE_NO_AUTH"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("TOUCH_GRASS_HOST", "127.0.0.1")
    assert auth_policy_error(Config.from_env("keyboard")) is None
