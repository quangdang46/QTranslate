# Hello Provider — the smallest working extension

It registers one provider, `hello`, which needs no network: it
prefixes the source text with "Hello, ". The point is the **plumbing**
— how an extension is discovered, validated, loaded and called.

## Install it

Copy this whole folder into the per-user extensions directory and
restart QTranslate:

| Platform | Extensions directory |
|---|---|
| Windows | `%APPDATA%\QTranslate\extensions` |
| macOS | `~/.config/QTranslate/extensions` |

Nothing is rebuilt and nothing is installed system-wide: the folder is
read at startup, and the app keeps running if the extension is broken.

## Use it

The provider appears in the main window's service list as `hello`.
Select it and translate; the result is "Hello, <your text>".

## Break it on purpose

Rename `ext.py` (or make `register` raise) and restart. The app
starts normally and the built-in providers still work — a broken
extension is **disabled with a reason**, never fatal.

## The contract

- `manifest.json` — the schema is `docs/EXTENSION_SDK.md` §4.
- `ext.py` — the `entrypoint` names `module:callable`; the callable
  receives the SDK's API object and registers providers, themes or UI
  contributions with it.
- The provider's signature is the registry's: `fn(text, src, tgt)`.
