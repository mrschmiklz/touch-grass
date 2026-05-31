"""High-level mouse operations over a SerialLink.

Mirrors keyboard.py: every method returns a structured dict so an agent's
verification loop can check results programmatically:
    {"ok": bool, "state": "READY"|..., "response": "OK"|"ERR:...", ["detail": str]}
"""

from __future__ import annotations

import time

from .link import STATE_READY, STATES, SerialLink

# Buttons accepted by the firmware's CLICK / DOWN / UP commands.
BUTTONS = ("LEFT", "RIGHT", "MIDDLE")


class Mouse:
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

    # ── movement ───────────────────────────────────────────────────────────────
    def move(self, dx: int, dy: int) -> dict:
        try:
            dx_i, dy_i = int(dx), int(dy)
        except (TypeError, ValueError):
            return {"ok": False, "state": self.link.state,
                    "detail": "dx and dy must be integers"}
        return self._command(f"MOVE {dx_i} {dy_i}")

    def scroll(self, amount: int) -> dict:
        try:
            amt = int(amount)
        except (TypeError, ValueError):
            return {"ok": False, "state": self.link.state,
                    "detail": "amount must be an integer"}
        return self._command(f"SCROLL {amt}")

    # ── buttons ──────────────────────────────────────────────────────────────
    def click(self, button: str) -> dict:
        b = self._resolve_button(button)
        if b is None:
            return self._bad_button(button)
        return self._command(f"CLICK {b}")

    def button_down(self, button: str) -> dict:
        b = self._resolve_button(button)
        if b is None:
            return self._bad_button(button)
        return self._command(f"DOWN {b}")

    def button_up(self, button: str) -> dict:
        b = self._resolve_button(button)
        if b is None:
            return self._bad_button(button)
        return self._command(f"UP {b}")

    def release(self) -> dict:
        """Release all currently held buttons."""
        return self._command("RELEASE")

    # ── management ─────────────────────────────────────────────────────────────
    def pair(self, confirm: bool = False) -> dict:
        """Clear all bonds and re-advertise for fresh pairing. Destructive."""
        if not confirm:
            return {"ok": False, "state": self.link.state,
                    "detail": "refused: clears all bonds. Pass confirm=true to proceed."}
        resp = self.link.query("PAIR")
        return {"ok": resp.startswith("OK"), "state": self.link.state, "response": resp}

    # ── internal ─────────────────────────────────────────────────────────────
    @staticmethod
    def _resolve_button(button: str) -> str | None:
        if not isinstance(button, str):
            return None
        upper = button.strip().upper()
        aliases = {"L": "LEFT", "R": "RIGHT", "M": "MIDDLE"}
        upper = aliases.get(upper, upper)
        return upper if upper in BUTTONS else None

    def _bad_button(self, button: str) -> dict:
        return {"ok": False, "state": self.link.state,
                "detail": f"unknown button '{button}'; valid: {', '.join(BUTTONS)}"}

    def _command(self, cmd: str) -> dict:
        resp = self.link.query(cmd)
        return {"ok": resp == "OK", "state": self.link.state, "response": resp}
