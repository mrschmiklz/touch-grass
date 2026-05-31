# touch-grass

> MCP servers that let an AI agent type and move a mouse on a **real machine**
> via paired ESP32 Bluetooth HID devices. After living its whole life in a
> sandbox, the agent finally touches grass.

`touch-grass` is the bridge between an autonomous agent (built for
[Hermes](https://github.com/NousResearch) and any other MCP client) and the
physical world. Long-running [MCP](https://modelcontextprotocol.io) servers own
ESP32s over USB serial; the ESP32s act as Bluetooth HID devices (a keyboard and
a mouse) paired with a target computer. The agent calls typed tools
(`keyboard_type`, `mouse_move`, …) and real input lands on the target.

It runs **one server instance per device** — a keyboard server and a mouse
server, each owning its own ESP32 and listening on its own port — so the agent
connects to two endpoints. It pairs with the
[`esp32-bt-keyboard`](https://github.com/mrschmiklz/esp32-bt-keyboard) and
[`esp32-bt-mouse`](https://github.com/mrschmiklz/esp32-bt-mouse) firmware and
does **not** modify them — this is purely the control/skill layer.

> **Responsible use:** this drives a real keyboard and mouse into whatever the
> target machine has focused / under the pointer. Use it only on hardware and
> accounts you own or are authorized to control.

---

## Why an MCP server (and not a CLI)?

The server is also the **persistent serial owner**, which is what makes the link
reliable and agent-friendly:

- **One open port, forever.** Re-opening a serial port resets the ESP32 (its
  auto-reset circuit), which would drop the BLE link on every command. The
  server opens once, holds DTR/RTS low, and clears `HUPCL` on Linux so closing
  can't pulse a reset either.
- **Safe for parallel subagents.** Hermes spawns isolated subagents; they all
  connect to the one server, whose lock serializes access to the single
  physical keyboard (no "port busy" collisions).
- **Verifiable.** Every tool returns `{ok, state, response}` so an agent's
  evaluation loop can confirm each action and crystallize reliable skills.

---

## Architecture

```
Hermes (+ parallel subagents)
        │  MCP (streamable HTTP) — two endpoints
        ├── touch-grass-kb    :8765   ← single owner of the keyboard serial port
        │       │  serial @115200 (opened once; never resets the ESP32)
        │   /dev/ttyUSB0 → ESP32 (Logitech K380) → BLE → target machine
        │
        └── touch-grass-mouse :8766   ← single owner of the mouse serial port
                │  serial @115200 (opened once; never resets the ESP32)
            /dev/ttyUSB1 → ESP32 (Logitech M720) → BLE → target machine
```

One server per device keeps each serial owner simple and isolated: a crash or
re-pair on one device never touches the other, and each gets its own lock for
safe parallel-subagent access.

---

## Tools

### Keyboard (`touch-grass-kb`)

| Tool | Description |
| --- | --- |
| `keyboard_status()` | Current link state: `READY` / `CONNECTED_NOT_READY` / `DISCONNECTED`. |
| `keyboard_wait_ready(timeout_s=30)` | Block until `READY`. Call this first. |
| `keyboard_type(text, press_enter=false)` | Type a string; optionally press Enter. |
| `keyboard_key(name)` | Special key: `ENTER` `TAB` `ESC` arrows `F1`–`F12` `HOME` `END` … |
| `keyboard_combo(combo)` | Modifier shortcut, e.g. `CTRL+C`, `WIN+R`, `CTRL+SHIFT+T`. |
| `keyboard_media(name)` | `PLAY` `PAUSE` `NEXT` `PREV` `STOP` `MUTE` `VOLUP` `VOLDOWN`. |
| `keyboard_pair(confirm=false)` | **Destructive**: wipe bonds to re-pair. Requires `confirm=true`. |

### Mouse (`touch-grass-mouse`)

| Tool | Description |
| --- | --- |
| `mouse_status()` | Current link state. |
| `mouse_wait_ready(timeout_s=30)` | Block until `READY`. Call this first. |
| `mouse_move(dx, dy)` | **Relative** move in pixels (`+dx` right, `+dy` down). |
| `mouse_click(button="LEFT")` | Click `LEFT` / `RIGHT` / `MIDDLE`. |
| `mouse_button_down(button)` / `mouse_button_up(button)` | Hold / release (drags). |
| `mouse_scroll(amount)` | Vertical wheel; positive = up. |
| `mouse_release()` | Release all held buttons. |
| `mouse_pair(confirm=false)` | **Destructive**: wipe bonds to re-pair. Requires `confirm=true`. |

Each returns `{"ok": bool, "state": "...", "response": "OK"|"ERR:..."}`.

---

## Quick start (local, for testing)

Requires Python 3.10+ and the ESP32s running the `esp32-bt-keyboard` /
`esp32-bt-mouse` firmware, paired with your target machine.

```bash
pip install .

# See what serial ports are visible / which ESP32 was detected:
touch-grass detect

# One-shot state checks (pin the port; both boards are CP210x):
TOUCH_GRASS_KB_SERIAL=COM5    touch-grass status --device keyboard
TOUCH_GRASS_MOUSE_SERIAL=COM7 touch-grass status --device mouse

# Run a server (one per device). Keyboard defaults to :8765, mouse to :8766:
TOUCH_GRASS_KB_SERIAL=COM5    touch-grass serve --device keyboard
TOUCH_GRASS_MOUSE_SERIAL=COM7 touch-grass serve --device mouse
```

Each MCP endpoint is served at `http://<host>:<port>/mcp`.

### Configuration

`--device {keyboard,mouse}` (or `TOUCH_GRASS_DEVICE`) selects which device an
instance controls. Because both ESP32 boards are CP210x, auto-detect can't tell
them apart — **pin each port explicitly** with the per-device vars:

| Env var | Default | Purpose |
| --- | --- | --- |
| `TOUCH_GRASS_DEVICE` | `keyboard` | Which device this instance controls. |
| `TOUCH_GRASS_KB_SERIAL` | (fallback below) | Keyboard serial device (e.g. `COM5`, `/dev/ttyUSB0`). |
| `TOUCH_GRASS_MOUSE_SERIAL` | (fallback below) | Mouse serial device (e.g. `COM7`, `/dev/ttyUSB1`). |
| `TOUCH_GRASS_SERIAL` | auto-detect | Generic fallback if the per-device var is unset. |
| `TOUCH_GRASS_BAUD` | `115200` | Baud rate. |
| `TOUCH_GRASS_HOST` | `127.0.0.1` | MCP bind host. |
| `TOUCH_GRASS_PORT` | `8765` kb / `8766` mouse | MCP bind port. |

---

## Deploying as a Hermes sidecar (recommended)

Run two `touch-grass` containers — one per device — with each ESP32 passed
through; Hermes and its subagents connect over a private Docker network.

```bash
docker compose up -d --build
```

See [`docker-compose.yml`](docker-compose.yml). Hermes then registers both MCP
servers: `http://touch-grass-kb:8765/mcp` and
`http://touch-grass-mouse:8766/mcp`.

> **Tip:** on Linux, use `/dev/serial/by-id/...` symlinks (stable per board) to
> pin each device, in case `/dev/ttyUSB*` ordering shifts on reboot.

> **Security note:** the MCP endpoints have no built-in authentication yet. Keep
> them on a private network and do **not** publish the ports to the host or the
> internet. Put them behind a reverse proxy with auth/TLS if you must expose.

The agent-facing usage guide lives in [`skill/SKILL.md`](skill/SKILL.md), with
function schemas in [`skill/tools.json`](skill/tools.json) for non-MCP clients.

---

## Roadmap

- **v0.1:** keyboard control.
- **v0.2 (now):** mouse tools (`mouse_move`, `mouse_click`, `mouse_scroll`, …)
  via a second server instance, backed by the `esp32-bt-mouse` firmware.
- **Later:** optional bearer-token auth on the MCP endpoints; a firmware
  `WHOAMI` identity command so a single host can auto-assign each board.

## License

[MIT](LICENSE).
