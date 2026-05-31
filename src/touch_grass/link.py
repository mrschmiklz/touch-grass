"""Persistent, single-owner serial link to the ESP32 keyboard.

Design goals (this is what makes the connection "rock solid"):
  * Open the port exactly ONCE and keep it open. Repeatedly opening/closing a
    serial port resets the ESP32 (the auto-reset circuit), which would drop the
    BLE link on every command.
  * Never assert the auto-reset lines: open with DTR/RTS held low, and on POSIX
    clear the HUPCL termios flag so a future close can't pulse DTR either.
  * Serialize all I/O with a lock so concurrent callers (e.g. parallel agent
    subagents) can't interleave on the single physical keyboard.
  * A background reader thread tracks EVENT: lines to maintain live state, and
    auto-reconnects with backoff if the USB cable drops.
"""

from __future__ import annotations

import sys
import threading
import time

import serial

# Connection states reported by the firmware's STATUS command.
STATE_READY = "READY"
STATE_CONNECTED_NOT_READY = "CONNECTED_NOT_READY"
STATE_DISCONNECTED = "DISCONNECTED"
STATES = (STATE_READY, STATE_CONNECTED_NOT_READY, STATE_DISCONNECTED)

# Sentinel "port" reported by the mock link so logs/diagnostics are unambiguous.
MOCK_PORT = "mock://no-hardware"


class LinkError(RuntimeError):
    """Raised when the serial link cannot be established or used."""


class MockLink:
    """A no-hardware stand-in for SerialLink (enabled by TOUCH_GRASS_MOCK_SERIAL).

    Exposes the same interface the Keyboard/Mouse controllers use, so both
    servers boot and MCP tool discovery works without a real ESP32 attached.
    STATUS always reports DISCONNECTED and every action returns
    ``ERR:NO_HARDWARE`` — the agent can verify the MCP contract but can never
    accidentally drive real keystrokes, clicks, or a destructive re-pair.

    Intended for MCP discovery, CI, and agent setup verification.
    """

    def __init__(self, port: str = MOCK_PORT, baud: int = 115200):
        self.port = port
        self.baud = baud
        self.state = STATE_DISCONNECTED

    def start(self) -> None:  # no-op: nothing to open
        pass

    def stop(self) -> None:   # no-op: nothing to close
        pass

    def query(self, cmd: str, timeout: float = 20.0) -> str:
        token = cmd.strip().upper()
        if token == "STATUS":
            return STATE_DISCONNECTED
        if token == "BONDS":
            return "BONDS:0"
        # Any real action (TYPE/KEY/MOVE/CLICK/PAIR/...) is safely refused.
        return "ERR:NO_HARDWARE"


class SerialLink:
    def __init__(self, port: str, baud: int = 115200):
        self.port = port
        self.baud = baud
        self.ser: serial.Serial | None = None
        self.state = "UNKNOWN"
        self._lock = threading.Lock()        # serializes all serial I/O
        self._running = False
        self._reader: threading.Thread | None = None
        self._in_query = False               # reader yields the port during a query

    # ── lifecycle ────────────────────────────────────────────────────────────
    def start(self) -> None:
        self.ser = self._open()
        self._running = True
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def stop(self) -> None:
        self._running = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass

    def _open(self) -> serial.Serial:
        s = serial.Serial()
        s.port = self.port
        s.baudrate = self.baud
        s.timeout = 0.05
        # Hold the auto-reset lines low so opening doesn't reset the ESP32.
        s.dtr = False
        s.rts = False
        try:
            s.open()
        except (serial.SerialException, OSError) as e:
            raise LinkError(f"cannot open {self.port}: {e}") from e
        self._disable_hupcl(s)
        s.reset_input_buffer()
        return s

    @staticmethod
    def _disable_hupcl(s: serial.Serial) -> None:
        """Clear HUPCL on POSIX so closing the port never pulses DTR (no reset)."""
        if not sys.platform.startswith(("linux", "darwin")):
            return
        try:
            import termios

            fd = s.fileno()
            attrs = termios.tcgetattr(fd)
            attrs[2] &= ~termios.HUPCL          # cflag
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
        except Exception:
            # Best-effort; not fatal if the platform/driver doesn't support it.
            pass

    # ── background reader ────────────────────────────────────────────────────
    def _read_loop(self) -> None:
        buf = b""
        backoff = 1.0
        while self._running:
            if self._in_query:
                time.sleep(0.01)
                continue
            try:
                chunk = self.ser.read(64) if self.ser else b""
                if chunk:
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        self._ingest(line.decode(errors="replace").strip())
            except (serial.SerialException, OSError):
                if not self._running:
                    break
                self.state = STATE_DISCONNECTED
                buf = b""
                self._safe_close()
                time.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
                try:
                    self.ser = self._open()
                    backoff = 1.0
                except LinkError:
                    continue
            except Exception:
                time.sleep(0.05)

    def _ingest(self, line: str) -> None:
        if not line:
            return
        if line.startswith("EVENT:"):
            if "HID_READY" in line:
                self.state = STATE_READY
            elif "HID_UNSUBSCRIBED" in line:
                self.state = STATE_CONNECTED_NOT_READY
            elif "DISCONNECTED" in line:
                self.state = STATE_DISCONNECTED
            elif "CONNECTED" in line:
                self.state = STATE_CONNECTED_NOT_READY
        elif line in STATES:
            self.state = line

    def _safe_close(self) -> None:
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass

    # ── request/response ───────────────────────────────────────────────────────
    def query(self, cmd: str, timeout: float = 20.0) -> str:
        """Send a command and return the first response line (or an ERR string)."""
        with self._lock:
            self._in_query = True
            try:
                if not (self.ser and self.ser.is_open):
                    return "ERR:NO_SERIAL"
                time.sleep(0.02)                # let the reader release the port
                self.ser.reset_input_buffer()
                self.ser.write((cmd + "\n").encode())
                buf = b""
                deadline = time.time() + timeout
                while time.time() < deadline:
                    n = max(1, self.ser.in_waiting)
                    chunk = self.ser.read(n)
                    if chunk:
                        buf += chunk
                        if b"\n" in buf:
                            break
                line = buf.decode(errors="replace").strip().splitlines()
                return line[0] if line else "ERR:TIMEOUT"
            except (serial.SerialException, OSError) as e:
                return f"ERR:SERIAL {e}"
            finally:
                self._in_query = False
