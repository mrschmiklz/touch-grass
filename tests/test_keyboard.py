"""Unit tests for the keyboard result/command logic using a fake link.

These run without hardware: a FakeLink records the last command and returns a
canned response, so we can assert the structured results and command mapping.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from touch_grass.keyboard import Keyboard  # noqa: E402
from touch_grass.link import STATE_READY   # noqa: E402


class FakeLink:
    def __init__(self, response="OK", state=STATE_READY):
        self.response = response
        self.state = state
        self.last_cmd = None

    def query(self, cmd, timeout=20.0):
        self.last_cmd = cmd
        return self.response


def test_type_maps_to_TYPE():
    link = FakeLink("OK")
    kb = Keyboard(link)
    res = kb.type("hello")
    assert link.last_cmd == "TYPE hello"
    assert res == {"ok": True, "state": STATE_READY, "response": "OK"}


def test_type_with_enter_maps_to_TYPEN():
    link = FakeLink("OK")
    kb = Keyboard(link)
    kb.type("hello", press_enter=True)
    assert link.last_cmd == "TYPEN hello"


def test_empty_type_is_rejected_without_touching_link():
    link = FakeLink("OK")
    kb = Keyboard(link)
    res = kb.type("")
    assert res["ok"] is False
    assert link.last_cmd is None


def test_key_validates_name():
    link = FakeLink("OK")
    kb = Keyboard(link)
    assert kb.key("enter")["ok"] is True
    assert link.last_cmd == "KEY ENTER"
    bad = kb.key("banana")
    assert bad["ok"] is False
    assert "unknown key" in bad["detail"]


def test_combo_uppercases():
    link = FakeLink("OK")
    kb = Keyboard(link)
    kb.combo("ctrl+c")
    assert link.last_cmd == "MOD CTRL+C"


def test_media_validates_name():
    link = FakeLink("OK")
    kb = Keyboard(link)
    assert kb.media("play")["ok"] is True
    assert link.last_cmd == "MEDIA PLAY"
    assert kb.media("nope")["ok"] is False


def test_error_response_marks_not_ok():
    link = FakeLink("ERR:NOT_READY")
    kb = Keyboard(link)
    res = kb.key("ENTER")
    assert res["ok"] is False
    assert res["response"] == "ERR:NOT_READY"


def test_pair_requires_confirm():
    link = FakeLink("OK:PAIRING_MODE")
    kb = Keyboard(link)
    refused = kb.pair()
    assert refused["ok"] is False
    assert link.last_cmd is None
    done = kb.pair(confirm=True)
    assert done["ok"] is True
    assert link.last_cmd == "PAIR"


def test_status_parses_state():
    link = FakeLink(STATE_READY)
    kb = Keyboard(link)
    res = kb.status()
    assert res == {"ok": True, "state": STATE_READY}
