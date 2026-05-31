---
name: touch-grass
description: Type and move a mouse on a real machine via paired ESP32 Bluetooth HID devices. Use when you need to send physical keystrokes, shortcuts, pointer moves, clicks, or scrolls to the target computer the ESP32s are paired with.
---

# touch-grass — physical keyboard + mouse control

This skill lets you operate a **real Bluetooth keyboard and mouse** on a target
machine. Two ESP32s (a keyboard advertising as "Logitech K380" and a mouse as
"Logitech M720") are paired with the target over BLE. touch-grass runs **one MCP
server per device** (keyboard and mouse on separate endpoints), each owning its
ESP32 and exposing the tools below.

## When to use

- You need to send keystrokes/shortcuts or move/click/scroll on the **physical
  target computer** (e.g. open the Run dialog, click a button, drag, scroll).

## When NOT to use

- For anything you can deliver through a normal API/file. These drive real HID
  input into whatever window currently has focus on the target.

## Golden rule: verify before and after

1. Call `keyboard_wait_ready` / `mouse_wait_ready` first. Proceed only if
   `state == "READY"`.
2. After every action, check `ok == true`. The result is
   `{"ok": bool, "state": "READY"|"CONNECTED_NOT_READY"|"DISCONNECTED", "response": "OK"|"ERR:..."}`.
3. If `state` is `DISCONNECTED`, wait and retry — the devices auto-reconnect to
   their bonded host; they do not need re-pairing.

## Keyboard tools

| Tool | Use |
| --- | --- |
| `keyboard_status()` | Current link state. |
| `keyboard_wait_ready(timeout_s=30)` | Block until READY. Call this first. |
| `keyboard_type(text, press_enter=false)` | Type a string; optionally press Enter. |
| `keyboard_key(name)` | One special key (ENTER, TAB, ESC, ARROWS, F1–F12, …). |
| `keyboard_combo(combo)` | Modifier shortcut, e.g. `CTRL+C`, `WIN+R`, `CTRL+SHIFT+T`. |
| `keyboard_media(name)` | Media key: PLAY PAUSE NEXT PREV STOP MUTE VOLUP VOLDOWN. |
| `keyboard_pair(confirm=false)` | DESTRUCTIVE: wipes bonds to re-pair. Needs `confirm=true`. |

## Mouse tools

Movement is **relative** (pixels): `+dx` = right, `+dy` = down. There are no
absolute coordinates — move relative to the current pointer position, and read
back the on-screen result if you need to confirm position.

| Tool | Use |
| --- | --- |
| `mouse_status()` | Current link state. |
| `mouse_wait_ready(timeout_s=30)` | Block until READY. Call this first. |
| `mouse_move(dx, dy)` | Relative move in pixels. |
| `mouse_click(button="LEFT")` | Click LEFT / RIGHT / MIDDLE. |
| `mouse_button_down(button)` / `mouse_button_up(button)` | Hold / release for drags. |
| `mouse_scroll(amount)` | Vertical wheel; positive = up. |
| `mouse_release()` | Release all held buttons. |
| `mouse_pair(confirm=false)` | DESTRUCTIVE: wipes bonds to re-pair. Needs `confirm=true`. |

## Example: open Notepad and click in it

```
keyboard_wait_ready()                        # -> {"ok": true, "ready": true, "state": "READY"}
keyboard_combo("WIN+R")                      # -> {"ok": true, "state": "READY", "response": "OK"}
keyboard_type("notepad", press_enter=true)   # -> {"ok": true, ...}

mouse_wait_ready()                           # -> {"ok": true, "ready": true, "state": "READY"}
mouse_move(200, 150)                         # -> {"ok": true, "state": "READY", "response": "OK"}
mouse_click("LEFT")                          # -> {"ok": true, ...}
keyboard_type("Hello from the sandbox.")     # -> {"ok": true, ...}
```

## Agent safety contract

Recommended flow for any hardware action:

1. Call `keyboard_status` / `mouse_status` to see the link state.
2. Proceed **only if the user explicitly requested a hardware action.**
3. Call `*_wait_ready`; continue only when `state == "READY"`.
4. Perform **one small action**, then verify `ok == true` before the next.
5. Never call the destructive `*_pair` tools unless the user explicitly says so.

**Danger zone** — these cause real-world side effects; require explicit user
intent and verify each result:

- `keyboard_type`, `keyboard_combo` (can run commands, e.g. via `WIN+R`)
- `mouse_click`, `mouse_button_down` (activates whatever is under the cursor)
- `keyboard_pair`, `mouse_pair` (destructive: wipes bonds)

If a user only wants discovery/status (no input), restrict the exposed tools to
`*_status` / `*_wait_ready`, or run the servers in **mock mode**
(`TOUCH_GRASS_MOCK_SERIAL=1`) so every action safely returns `ERR:NO_HARDWARE`.

## Safety

- These drive whatever the target machine has focused / whatever is under the
  pointer — treat them as remote physical input. Only use on machines you own or
  are authorized to control.
- A stray `mouse_click` can activate whatever is under the cursor. Move
  deliberately and verify before clicking.
- Mock mode (`TOUCH_GRASS_MOCK_SERIAL=1`) exposes the tool schemas and returns
  `ERR:NO_HARDWARE` for actions — safe for setup verification while people sleep
  or the wrong window has focus.
