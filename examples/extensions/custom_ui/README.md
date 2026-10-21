# Custom UI — an example UI-contribution extension

The app publishes UI slots derived from the **native** UI surface rather
than invented ones: the menu slots are the native `Menus[].Id` values
a locale pack declares, and the panel slots are the three `Show*Pane`
toggles the Options page reads.

This example contributes one entry to the system-tray menu (the slot the
native calls `5`) and one to the main window's top pane.

## Install it

Copy this whole folder into the per-user extensions directory and
restart QTranslate:

| Platform | Extensions directory |
|---|---|
| Windows | `%APPDATA%\QTranslate\extensions` |
| macOS | `~/.config/QTranslate/extensions` |

## The contract

- `manifest.json` — the capability is `ui`.
- `ext.py` — the callable calls `api.register_ui(kind, slot,
  contribution)`, where `kind` is `"menu"`, `"panel"` or `"popup"` and
  `slot` names one of the published slots (`qtranslate/ui_slots.py`).
- A contribution is anything the host can call.
