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
        ├── touch-grass-keyboard :8765  ← single owner of the keyboard serial port
        │       │  serial @115200 (opened once; never resets the ESP32)
        │   /dev/ttyUSB0 → ESP32 (Logitech K380) → BLE → target machine
        │
        └── touch-grass-mouse    :8766  ← single owner of the mouse serial port
                │  serial @115200 (opened once; never resets the ESP32)
            /dev/ttyUSB1 → ESP32 (Logitech M720) → BLE → target machine
```

One server per device keeps each serial owner simple and isolated: a crash or
re-pair on one device never touches the other, and each gets its own lock for
safe parallel-subagent access. The recommended MCP server names are
**`touch-grass-keyboard`** and **`touch-grass-mouse`** — use them consistently
so generated tool names stay predictable.

> **Safe mode first.** Set `TOUCH_GRASS_MOCK_SERIAL=1` (or pass `--mock`) to run
> with **no hardware**: the servers boot, expose their full tool schemas, report
> `DISCONNECTED`, and return `ERR:NO_HARDWARE` for any real action. This is the
> intended mode for MCP discovery, CI, and agent setup verification — verify the
> wiring before anything can type, click, or re-pair. Run `touch-grass doctor`
> for a one-shot preflight.

---

## Tools

### Keyboard (`touch-grass-keyboard`)

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

## Quick start (local)

Requires Python 3.10+. For real input you also need the ESP32s running the
`esp32-bt-keyboard` / `esp32-bt-mouse` firmware, paired with your target machine
— but you can do the whole setup/verify dance in **mock mode** with no hardware.

```bash
pip install .          # or: make install   (editable, with dev extras)

# 1) Verify everything is wired for MCP discovery — NO hardware needed:
touch-grass doctor --mock

# 2) Run BOTH servers locally in safe mock mode (keyboard :8765 + mouse :8766):
touch-grass serve-all --mock

# --- with real hardware ---
touch-grass detect                              # which serial ports are visible?
TOUCH_GRASS_KB_SERIAL=COM5 TOUCH_GRASS_MOUSE_SERIAL=COM7 touch-grass serve-all

# Or one device at a time:
TOUCH_GRASS_KB_SERIAL=COM5    touch-grass serve --device keyboard
TOUCH_GRASS_MOUSE_SERIAL=COM7 touch-grass serve --device mouse
```

Each MCP endpoint is served at `http://<host>:<port>/mcp`.

### Commands

| Command | What it does |
| --- | --- |
| `touch-grass doctor [--mock] [--json]` | Preflight: SDK import, serial ports, resolved serials, port availability, and that both servers expose their tool sets (7 + 9). Exit 0 = ready. |
| `touch-grass serve --device {keyboard,mouse} [--mock]` | Run one device's server. |
| `touch-grass serve-all [--mock]` | Run **both** servers (child processes). |
| `touch-grass status --device <d> [--mock] [--json]` | One-shot link state. |
| `touch-grass config --device <d> [--mock] [--json]` | Print the **resolved** config (token redacted). |
| `touch-grass detect [--json]` | List serial ports / detected ESP32. |

```text
$ touch-grass doctor --mock
Mode:              mock serial (no hardware)
MCP SDK:           ok
Keyboard endpoint: http://127.0.0.1:8765/mcp  (auth: none)
Keyboard serial:   mock://no-hardware
Keyboard tools:    7/7 (ok)
Mouse endpoint:    http://127.0.0.1:8766/mcp  (auth: none)
Mouse serial:      mock://no-hardware
Mouse tools:       9/9 (ok)
Result: ready for MCP discovery
```

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
| `TOUCH_GRASS_MOCK_SERIAL` | `0` | `1` = no-hardware mock mode (safe discovery/CI). |
| `TOUCH_GRASS_BAUD` | `115200` | Baud rate. |
| `TOUCH_GRASS_HOST` | `127.0.0.1` | MCP bind host. |
| `TOUCH_GRASS_PORT` | `8765` kb / `8766` mouse | MCP bind port. |
| `TOUCH_GRASS_AUTH_TOKEN` | (unset) | If set, clients must send `Authorization: Bearer <token>`. |
| `TOUCH_GRASS_UNSAFE_NO_AUTH` | `0` | `1` = allow binding a non-loopback host with no token. |

> Bad integer values (e.g. `TOUCH_GRASS_PORT=eightyeight`) warn on stderr and
> fall back to the default rather than failing silently.

---

## Using with Hermes

The servers are alive and discoverable once running, but Hermes still needs MCP
entries. The most reliable path is to add them to your Hermes config directly:

```yaml
mcp_servers:
  touch-grass-keyboard:
    url: http://127.0.0.1:8765/mcp
    connect_timeout: 30
    timeout: 120
  touch-grass-mouse:
    url: http://127.0.0.1:8766/mcp
    connect_timeout: 30
    timeout: 120
```

Or from a **real terminal session**:

```bash
hermes mcp add touch-grass-keyboard --url http://127.0.0.1:8765/mcp
hermes mcp add touch-grass-mouse    --url http://127.0.0.1:8766/mcp
hermes mcp test touch-grass-keyboard
hermes mcp test touch-grass-mouse
```

> **Footgun:** interactive `hermes mcp add` may prompt (auth? enable all
> tools?). Run from a real terminal, **not** from inside a gateway/Telegram
> agent turn, where the prompt can't be answered and the add cancels. From a
> gateway, prefer editing `mcp_servers` in config (or `hermes config set ...`).

**Recommended bring-up:** start in mock mode, register both servers, run
`hermes mcp test ...` to confirm discovery, then switch to real hardware:

```bash
TOUCH_GRASS_MOCK_SERIAL=1 docker compose -f docker-compose.hermes.yml up -d --build
# (register + `hermes mcp test ...`), then for real:
TOUCH_GRASS_MOCK_SERIAL=0 TOUCH_GRASS_KB_SERIAL=/dev/ttyUSB0 \
  TOUCH_GRASS_MOUSE_SERIAL=/dev/ttyUSB1 \
  docker compose -f docker-compose.hermes.yml up -d --build
```

### Installing the skill

The agent-facing guide ([`skill/SKILL.md`](skill/SKILL.md)) + function schemas
([`skill/tools.json`](skill/tools.json)) can be dropped into Hermes' skills dir:

```bash
mkdir -p ~/.hermes/skills/touch-grass
cp -r skill/* ~/.hermes/skills/touch-grass/
```

---

## Deploying with Docker

Two compose files for the two common topologies:

- **Hermes on the host** (e.g. a Telegram/Discord gateway):
  [`docker-compose.hermes.yml`](docker-compose.hermes.yml) publishes both servers
  on **loopback** (`127.0.0.1:8765` / `:8766`) and defaults to **mock mode**.

  ```bash
  make serve-mock        # TOUCH_GRASS_MOCK_SERIAL=1 docker compose -f docker-compose.hermes.yml up -d --build
  make logs              # follow logs
  ```

- **Hermes in Docker**: [`docker-compose.yml`](docker-compose.yml) runs both on a
  private network (no host publishing); Hermes reaches
  `http://touch-grass-keyboard:8765/mcp` and `http://touch-grass-mouse:8766/mcp`.

> **Tip:** on Linux, use `/dev/serial/by-id/...` symlinks (stable per board) to
> pin each device, in case `/dev/ttyUSB*` ordering shifts on reboot.

### Security / auth

These endpoints are effectively "remote control this machine," so:

- Setting `TOUCH_GRASS_AUTH_TOKEN` enables bearer auth — every request must send
  `Authorization: Bearer <token>` (else `401`).
- Binding to a **non-loopback** host (e.g. `0.0.0.0`) with **no** token is
  refused unless you set `TOUCH_GRASS_UNSAFE_NO_AUTH=1`. Loopback needs no token.
- Keep these on a trusted/private network; add TLS via a reverse proxy if you
  must expose them beyond that.

---

## Roadmap

- **v0.1:** keyboard control.
- **v0.2:** mouse tools via a second server instance (`esp32-bt-mouse`).
- **v0.3 (now):** mock mode, `doctor`/`config`/`serve-all`, JSON output,
  optional bearer-token auth, CI MCP-discovery tests, Hermes setup docs.
- **Later:** a firmware `WHOAMI` identity command so a single host can
  auto-assign each board without explicit per-device serial vars.

## License

[MIT](LICENSE).
