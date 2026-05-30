---
name: touch-grass
description: Type on a real machine via a paired ESP32 Bluetooth keyboard. Use when you need to send physical keystrokes, special keys, or modifier shortcuts to the target computer the ESP32 is paired with.
---

# touch-grass — physical keyboard control

This skill lets you operate a **real Bluetooth keyboard** on a target machine.
An ESP32 (advertising as "Logitech K380") is paired with the target over BLE; a
`touch-grass` MCP server owns the ESP32 and exposes the tools below.

## When to use

- You need to send keystrokes or shortcuts to the **physical target computer**
  (e.g. open the Run dialog, switch windows, type into an app, control media).

## When NOT to use

- For text you can deliver through a normal API/file. This drives a real
  keyboard into whatever window currently has focus on the target.

## Golden rule: verify before and after

1. Call `keyboard_wait_ready` first. Proceed only if `state == "READY"`.
2. After every action, check `ok == true`. The result is
   `{"ok": bool, "state": "READY"|"CONNECTED_NOT_READY"|"DISCONNECTED", "response": "OK"|"ERR:..."}`.
3. If `state` is `DISCONNECTED`, wait and retry — the keyboard auto-reconnects
   to its bonded host; it does not need re-pairing.

## Tools

| Tool | Use |
| --- | --- |
| `keyboard_status()` | Current link state. |
| `keyboard_wait_ready(timeout_s=30)` | Block until READY. Call this first. |
| `keyboard_type(text, press_enter=false)` | Type a string; optionally press Enter. |
| `keyboard_key(name)` | One special key (ENTER, TAB, ESC, ARROWS, F1–F12, …). |
| `keyboard_combo(combo)` | Modifier shortcut, e.g. `CTRL+C`, `WIN+R`, `CTRL+SHIFT+T`. |
| `keyboard_media(name)` | Media key: PLAY PAUSE NEXT PREV STOP MUTE VOLUP VOLDOWN. |
| `keyboard_pair(confirm=false)` | DESTRUCTIVE: wipes bonds to re-pair. Needs `confirm=true`. |

## Example: open Notepad on the target

```
keyboard_wait_ready()                       # -> {"ok": true, "ready": true, "state": "READY"}
keyboard_combo("WIN+R")                      # -> {"ok": true, "state": "READY", "response": "OK"}
keyboard_type("notepad", press_enter=true)   # -> {"ok": true, "state": "READY", "response": "OK"}
keyboard_type("Hello from the sandbox.")     # -> {"ok": true, ...}
```

## Safety

- This types into whatever the target machine has focused — treat it as remote
  physical input. Only use it on machines you own or are authorized to control.
- Never call `keyboard_pair` unless you intend to re-pair the device.
