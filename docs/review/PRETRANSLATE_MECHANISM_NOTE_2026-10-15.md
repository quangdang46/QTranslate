# PreTranslate chain (A3/A4/A8) — mechanism substitution (2026-10-15)

> Read-only note. No row state changed, no port behaviour changed.

## 1. What native does

- `FUN_00455061` (A3): the Win32 message loop — `GetMessageW` → walk the
  PreTranslate **filter array** (`DAT_005491EC`, count `DAT_005491F0`) →
  `TranslateMessage`/`DispatchMessageW`. Each registered filter sees every
  message first and can consume it.
- `FUN_004551D6` (A4): registers a filter pointer into the array
  (grow ×2); `FUN_004552DC` unregisters by index.
- `FUN_00455024` (A8): finds a registered filter by pointer and removes
  it (the "startup seed" books a slot, then releases it once the loop is
  running).

This is MFC `PreTranslateMessage` machinery: a hook chain for keyboard
accelerators, dialog navigation, and global-hotkey dispatch.

## 2. Why there is nothing to port

Tk's mainloop has **no Win32 message-filter chain** — there is no
`DAT_005491EC` to fill. The port replaces the whole mechanism, not the
data structure:

- **In-window keys**: ~20 `root.bind(...)` in `App` (Ctrl+Enter translate,
  Ctrl+N/D/H/I/K, F1, Shift+Esc reset, Ctrl+digit service switch, …).
- **Global hotkeys**: `keyboard.add_hotkey` for all **17/17**
  `HOTKEY_NAMES` (verified 2026-10-15: `_actions` keys == `HOTKEY_NAMES`,
  zero missing, zero extra) — the functional equivalent of native's
  `RegisterHotKey` loop (`FUN_00405A17`).

Registering/unregistering filter *pointers* has no meaning outside MFC;
what matters — every key reaching its action — is covered. Rows A3/A4/A8
stay `ported` as mechanism substitutions, same class as the clipboard
monitor standing in for the WH_MOUSE_LL hook.
