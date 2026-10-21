# Custom Theme — an example theme extension

It registers one theme, `paper`: a warm-grey caption and border with a
soft paper background. A theme is a record of colour slots, and a
theme may set only the slots it cares about — the rest are inherited.

## Install it

Copy this whole folder into the per-user extensions directory and
restart QTranslate:

| Platform | Extensions directory |
|---|---|
| Windows | `%APPDATA%\QTranslate\extensions` |
| macOS | `~/.config/QTranslate/extensions` |

The theme then appears in the Options page's **Appearance** list.
Enabling it is your decision, not the extension's.

## The contract

- `manifest.json` — the schema is `docs/EXTENSION_SDK.md` §4; the
  capability is `theme`.
- `ext.py` — the `entrypoint` names `module:callable`; the callable
  receives the SDK's API object and calls `api.register_theme(name,
  record)`.
- The record's shape is the one `qtranslate.theme.load_theme_at`
  returns: `{"Common": {...}, "Window": {...}}`.
