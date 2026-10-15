# Tray balloon (`FUN_00405D0C`) — noted, not implemented (2026-10-15)

> Read-only trace. UI is frozen per user decision ("về vấn đề UI tôi
> chốt đã có phần ổn rồi") — no new window, browser, or Tk work follows.

## 1. What native does

`FUN_00405D0C(this, unused, text)` sets `NIF_INFO (0x10)` on the tray
`NOTIFYICONDATA`, timeout `5000` ms, title `"QTranslate"`, and sends
`NIM_MODIFY (1)` via `Shell_NotifyIconW`. It is the tray-balloon
notification primitive. `FUN_00405D62` is its sibling `NIM_DELETE (2)`.

## 2. When native shows it

The only caller found is through main-WndProc message `0x80DC` →
`FUN_00418812(this, ?, 1, 0x1)`: when `param_2 == 1` and `param_3 == 1`
and a menu-string lookup (`FUN_00451D23(..., 0xB5)`) succeeds, the
formatted string is passed to `FUN_00405D0C`. The WndProc path
(`FUN_00415EED` case `0x80DC`) routes it the same way.

## 3. Why not implemented

- The port's tray (`pystray.Icon`) has no balloon equivalent wired, and
  the only balloon trigger found is inside the OCR-region flow — which
  the user froze along with the rest of the UI.
- pystray's `notify()` exists but wiring it to a new trigger would be
  inventing UX, not porting it: the trigger conditions of `0x80DC`
  beyond the `1, 0x1` pattern were not traced.

Recorded so a future UI slice can wire it in one place.
