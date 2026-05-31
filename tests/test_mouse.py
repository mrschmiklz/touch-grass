"""Unit tests for the mouse result/command logic using a fake link.

These run without hardware: a FakeLink records the last command and returns a
canned response, so we can assert the structured results and command mapping.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from touch_grass.link import STATE_READY  # noqa: E402
from touch_grass.mouse import Mouse        # noqa: E402


class FakeLink:
    def __init__(self, response="OK", state=STATE_READY):
        self.response = response
        self.state = state
        self.last_cmd = None

    def query(self, cmd, timeout=20.0):
        self.last_cmd = cmd
        return self.response


def test_move_maps_to_MOVE():
    link = FakeLink("OK")
    m = Mouse(link)
    res = m.move(50, -20)
    assert link.last_cmd == "MOVE 50 -20"
    assert res == {"ok": True, "state": STATE_READY, "response": "OK"}


def test_move_rejects_non_integer_without_touching_link():
    link = FakeLink("OK")
    m = Mouse(link)
    res = m.move("left", 0)
    assert res["ok"] is False
    assert link.last_cmd is None


def test_scroll_maps_to_SCROLL():
    link = FakeLink("OK")
    m = Mouse(link)
    m.scroll(-3)
    assert link.last_cmd == "SCROLL -3"


def test_click_validates_and_uppercases_button():
    link = FakeLink("OK")
    m = Mouse(link)
    assert m.click("left")["ok"] is True
    assert link.last_cmd == "CLICK LEFT"
    bad = m.click("scroll")
    assert bad["ok"] is False
    assert "unknown button" in bad["detail"]


def test_button_aliases_resolve():
    link = FakeLink("OK")
    m = Mouse(link)
    m.button_down("r")
    assert link.last_cmd == "DOWN RIGHT"
    m.button_up("M")
    assert link.last_cmd == "UP MIDDLE"


def test_release_maps_to_RELEASE():
    link = FakeLink("OK")
    m = Mouse(link)
    m.release()
    assert link.last_cmd == "RELEASE"


def test_error_response_marks_not_ok():
    link = FakeLink("ERR:NOT_READY")
    m = Mouse(link)
    res = m.click("LEFT")
    assert res["ok"] is False
    assert res["response"] == "ERR:NOT_READY"


def test_pair_requires_confirm():
    link = FakeLink("OK:PAIRING_MODE")
    m = Mouse(link)
    refused = m.pair()
    assert refused["ok"] is False
    assert link.last_cmd is None
    done = m.pair(confirm=True)
    assert done["ok"] is True
    assert link.last_cmd == "PAIR"


def test_status_parses_state():
    link = FakeLink(STATE_READY)
    m = Mouse(link)
    assert m.status() == {"ok": True, "state": STATE_READY}
