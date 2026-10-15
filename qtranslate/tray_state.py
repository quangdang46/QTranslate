"""Tray icon state selection — port of `FUN_00418B69` (row G Tray).

Native (decompiled 2026-10-15): `FUN_00418B69(param_1, param_2)` picks
the tray icon index by `param_2` — `0 → 199`, `2 → 0x8A`, else `0x84`.
The wrapper `FUN_00418DA0(param_1, param_2)` computes `param_2` as
`0` when its flag is clear, else `(DAT_005493FC != 0) + 1`; upstream
`FUN_00418E85` derives the flag from the **mouse-hook state**. So the
tray icon reflects whether mouse capture is available/armed, not
whether hotkeys are bound.

This module is the pure selection (`0/1/2 → "off"/"on"/"partial"`),
testable without pystray or Tk. The `param_1 == 0` branch (NIM_ADD vs
NIM_MODIFY, `FUN_00405C42` vs `FUN_00405CB2`) is a caller concern, not
state selection.
"""
from __future__ import annotations

# Native icon indices, for reference (the port draws its own glyphs).
ICON_OFF = 199
ICON_ON = 0x84
ICON_PARTIAL = 0x8A


def select_state(hook_flag: bool, hook_available: bool) -> int:
    """`0/1/2` from the `FUN_00418DA0` rule.

    ``hook_flag`` clear → `0`; set → `(available != 0) + 1`, i.e. `1`
    when the hook is off/unavailable, `2` when it is on.
    """
    if not hook_flag:
        return 0
    return (1 if hook_available else 0) + 1


def state_name(index: int) -> str:
    """Port-side name for the icon: `0 → off`, `1 → on`, `2 → partial`."""
    return {0: "off", 1: "on", 2: "partial"}.get(int(index), "off")


def native_icon(index: int) -> int:
    """Native icon index for a state: `0 → 199`, `2 → 0x8A`, else `0x84`."""
    if int(index) == 0:
        return ICON_OFF
    if int(index) == 2:
        return ICON_PARTIAL
    return ICON_ON
