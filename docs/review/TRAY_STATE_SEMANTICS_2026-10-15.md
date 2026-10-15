# Tray icon state — semantics re-read (2026-10-15)

> Read-only trace that re-documents the tray icon mapping. No port code
> was changed (the `app._sync_icon` selection stays as-is pending a UI
> decision), and no row state changed.

## 1. Native chain

`FUN_00418B69(this, param_1, param_2)` picks the tray icon index by
`param_2` (decompiled 2026-10-15):

```c
if (param_2 == 0)      uVar4 = 199;    // off (gray)
else if (param_2 == 2) uVar4 = 0x8A;   // partial (orange)
else                   uVar4 = 0x84;   // on (blue)
HICON = LoadIconW(hInst, uVar4);
if (param_1 == '\0') Shell_NotifyIconW(NIM_ADD, ...);     // FUN_00405C42
else                 Shell_NotifyIconW(NIM_MODIFY, ...); // FUN_00405CB2
```

`FUN_00418DA0(param_1, param_2)` computes that `param_2`:

```c
iVar2 = 0;
if (param_2 != '\0') iVar2 = (DAT_005493FC != '\0') + 1;
FUN_00418B69(this, '\x01', iVar2);
```

So the three states are **not** "hotkeys bound / mouse-mode armed" —
they are:

| state | meaning in the chain |
|---|---|
| 0 | `param_2` flag clear |
| 1 | flag set, `DAT_005493FC` clear |
| 2 | flag set, `DAT_005493FC` set |

`DAT_005493FC` is written inside `FUN_00418DA0` itself from
`FUN_004059CF(...)` (the hook available path) and read upstream in
`FUN_00418E85` (mouse-hook toggle / enable branches). The flag that
feeds the tray is the **mouse-capture availability / arm state**, driven
by `DAT_00549168` — not the HotKeys list.

## 2. Port

`app._sync_icon` selects `partial/on/off` from `any(hk) and
_mouse_mode`. That mapping (hotkeys-bound → on) is a port-side choice,
not the native rule. The icon *colors* (off gray, on blue, partial
orange) match `199/0x84/0x8A`.

The pure selection (`qtranslate/tray_state.py`) now documents the native
rule; no UI change is made while the UI is frozen.
