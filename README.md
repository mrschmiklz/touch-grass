# touch-grass

> An MCP server that lets an AI agent type on a **real machine** via a paired
> ESP32 Bluetooth keyboard. After living its whole life in a sandbox, the agent
> finally touches grass.

`touch-grass` is the bridge between an autonomous agent (built for
[Hermes](https://github.com/NousResearch) and any other MCP client) and the
physical world. A long-running [MCP](https://modelcontextprotocol.io) server
owns an ESP32 over USB serial; the ESP32 acts as a Bluetooth HID keyboard paired
with a target computer. The agent calls typed tools (`keyboard_type`,
`keyboard_combo`, …) and real keystrokes land on the target.

It pairs with the [`esp32-bt-keyboard`](https://github.com/mrschmiklz/esp32-bt-keyboard)
firmware and does **not** modify it — this is purely the control/skill layer.

> **Responsible use:** this drives a real keyboard into whatever window the
> target machine has focused. Use it only on hardware and accounts you own or
> are authorized to control.

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
        │  MCP (streamable HTTP)
   touch-grass server         ← single owner of the serial port
        │  serial @115200 (opened once; never resets the ESP32)
   /dev/ttyUSB0 → ESP32 (Logitech K380) → BLE → target machine
```

---

## Tools

| Tool | Description |
| --- | --- |
| `keyboard_status()` | Current link state: `READY` / `CONNECTED_NOT_READY` / `DISCONNECTED`. |
| `keyboard_wait_ready(timeout_s=30)` | Block until `READY`. Call this first. |
| `keyboard_type(text, press_enter=false)` | Type a string; optionally press Enter. |
| `keyboard_key(name)` | Special key: `ENTER` `TAB` `ESC` arrows `F1`–`F12` `HOME` `END` … |
| `keyboard_combo(combo)` | Modifier shortcut, e.g. `CTRL+C`, `WIN+R`, `CTRL+SHIFT+T`. |
| `keyboard_media(name)` | `PLAY` `PAUSE` `NEXT` `PREV` `STOP` `MUTE` `VOLUP` `VOLDOWN`. |
| `keyboard_pair(confirm=false)` | **Destructive**: wipe bonds to re-pair. Requires `confirm=true`. |

Each returns `{"ok": bool, "state": "...", "response": "OK"|"ERR:..."}`.

---

## Quick start (local, for testing)

Requires Python 3.10+ and an ESP32 running the `esp32-bt-keyboard` firmware,
paired with your target machine.

```bash
pip install .

# See what serial ports are visible / which ESP32 was detected:
touch-grass detect

# One-shot state check:
touch-grass status

# Run the MCP server (defaults to 127.0.0.1:8765):
touch-grass serve
```

The MCP endpoint is served at `http://<host>:<port>/mcp`.

### Configuration

| Env var | Default | Purpose |
| --- | --- | --- |
| `TOUCH_GRASS_SERIAL` | auto-detect | Serial device (e.g. `/dev/ttyUSB0`, `COM5`). |
| `TOUCH_GRASS_BAUD` | `115200` | Baud rate. |
| `TOUCH_GRASS_HOST` | `127.0.0.1` | MCP bind host. |
| `TOUCH_GRASS_PORT` | `8765` | MCP bind port. |

---

## Deploying as a Hermes sidecar (recommended)

Run `touch-grass` as its own container with the ESP32 passed through; Hermes and
its subagents connect to it over a private Docker network.

```bash
docker compose up -d --build
```

See [`docker-compose.yml`](docker-compose.yml). Hermes then registers the MCP
server at `http://touch-grass:8765/mcp`.

> **Security note:** the MCP endpoint has no built-in authentication yet. Keep it
> on a private network and do **not** publish the port to the host or the
> internet. Put it behind a reverse proxy with auth/TLS if you must expose it.

The agent-facing usage guide lives in [`skill/SKILL.md`](skill/SKILL.md), with
function schemas in [`skill/tools.json`](skill/tools.json) for non-MCP clients.

---

## Roadmap

- **v1 (now):** keyboard control.
- **v2:** mouse tools (`mouse_move`, `mouse_click`, `mouse_scroll`) on the same
  server, backed by the `esp32-bt-mouse` firmware.

## License

[MIT](LICENSE).
