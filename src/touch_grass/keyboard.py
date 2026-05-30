"""High-level keyboard operations over a SerialLink.

Every method returns a structured dict so an agent's verification loop can check
results programmatically:
    {"ok": bool, "state": "READY"|..., "response": "OK"|"ERR:...", ["detail": str]}
"""

from __future__ import annotations

import time

from .link import STATE_READY, STATES, SerialLink

# Special keys accepted by the firmware's `KEY` command.
KEY_NAMES = (
    "ENTER", "RETURN", "ESC", "BACKSPACE", "TAB", "SPACE", "MINUS", "EQUALS",
    "CAPS", "PRINTSCREEN", "SCROLLLOCK", "PAUSE", "INSERT", "HOME", "PAGEUP",
    "DELETE", "END", "PAGEDOWN", "RIGHT", "LEFT", "DOWN", "UP", "NUMLOCK",
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
)

# Media keys accepted by the firmware's `MEDIA` command.
MEDIA_NAMES = ("NEXT", "PREV", "STOP", "PLAY", "PAUSE", "MUTE", "VOLUP", "VOLDOWN")

# Modifier tokens recognized inside a combo (e.g. "CTRL+SHIFT+T").
MODIFIER_TOKENS = ("CTRL", "SHIFT", "ALT", "WIN", "GUI")


class Keyboard:
    def __init__(self, link: SerialLink):
        self.link = link

    # ── status ───────────────────────────────────────────────────────────────
    def status(self) -> dict:
        resp = self.link.query("STATUS")
        if resp in STATES:
            self.link.state = resp
            return {"ok": True, "state": resp}
        return {"ok": False, "state": self.link.state, "response": resp}

    def wait_ready(self, timeout_s: float = 30.0) -> dict:
        deadline = time.time() + timeout_s
        last = self.status()
        while time.time() < deadline:
            if last.get("state") == STATE_READY:
                return {"ok": True, "ready": True, "state": STATE_READY}
            time.sleep(0.5)
            last = self.status()
        return {"ok": False, "ready": False, "state": last.get("state", "UNKNOWN")}

    # ── input ────────────────────────────────────────────────────────────────
    def type(self, text: str, press_enter: bool = False) -> dict:
        if text == "":
            return {"ok": False, "state": self.link.state, "detail": "text is empty"}
        cmd = f"{'TYPEN' if press_enter else 'TYPE'} {text}"
        return self._command(cmd)

    def key(self, name: str) -> dict:
        upper = name.strip().upper()
        if upper not in KEY_NAMES:
            return {"ok": False, "state": self.link.state,
                    "detail": f"unknown key '{name}'; see KEY_NAMES"}
        return self._command(f"KEY {upper}")

    def combo(self, combo: str) -> dict:
        cleaned = combo.strip().upper()
        if not cleaned:
            return {"ok": False, "state": self.link.state, "detail": "combo is empty"}
        return self._command(f"MOD {cleaned}")

    def media(self, name: str) -> dict:
        upper = name.strip().upper()
        if upper not in MEDIA_NAMES:
            return {"ok": False, "state": self.link.state,
                    "detail": f"unknown media key '{name}'; see MEDIA_NAMES"}
        return self._command(f"MEDIA {upper}")

    # ── management ─────────────────────────────────────────────────────────────
    def pair(self, confirm: bool = False) -> dict:
        """Clear all bonds and re-advertise for fresh pairing. Destructive."""
        if not confirm:
            return {"ok": False, "state": self.link.state,
                    "detail": "refused: clears all bonds. Pass confirm=true to proceed."}
        resp = self.link.query("PAIR")
        return {"ok": resp.startswith("OK"), "state": self.link.state, "response": resp}

    # ── internal ─────────────────────────────────────────────────────────────
    def _command(self, cmd: str) -> dict:
        resp = self.link.query(cmd)
        return {"ok": resp == "OK", "state": self.link.state, "response": resp}
