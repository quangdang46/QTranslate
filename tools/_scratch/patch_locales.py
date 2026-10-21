"""Wire the recovered locale packs into the port.

Two places read a hardcoded Windows install path, so off Windows the port
had no locale packs at all and its main window opened with a three-line
stub instead of native's help text:

  * `qtranslate/locale.py` -- `LOCALES_DIR`
  * `qtranslate/app.py`    -- `default_source_text()`

Both now prefer the recovered packs bundled under `qtranslate/assets/`.
"""

from __future__ import annotations

import sys
from pathlib import Path

EDITS: list[tuple[Path, str, str]] = []

EDITS.append((
    Path("qtranslate/locale.py"),
    '''LOCALES_DIR = "C:/Program Files (x86)/QTranslate/Locales"
''',
    '''# The port ships the native locale packs, recovered from the QTranslate
# 6.10.0 installer payload and committed under `qtranslate/assets/locales/`
# (35 `lang.json` files, byte-identical to the installed
# `Locales/<dir>/lang.json`). The Windows install is only a fallback: with
# the path hardcoded to it, the port had NO locales off Windows.
#   docs/review/PAYLOAD_CHUNK_CENSUS_2026-10-15.md §3 (35/35 identical)
_BUNDLED_LOCALES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "assets", "locales")
LOCALES_DIR = (_BUNDLED_LOCALES if os.path.isdir(_BUNDLED_LOCALES)
               else "C:/Program Files (x86)/QTranslate/Locales")
'''))

EDITS.append((
    Path("qtranslate/app.py"),
    '''        lines = ["QTranslate Version  6.10.0", ""]
        try:
            with open("C:/Program Files (x86)/QTranslate/Locales/English/"
                      "help.txt", encoding="utf-8-sig") as f:
                lines.append(f.read().strip())
        except Exception:
            lines.append("Double Ctrl => Show main window\\n"
                         "Ctrl+Q => Translate selected text\\n"
                         "Ctrl+E => Listen to selected text")
        return "\\n".join(lines)
''',
    '''        lines = ["QTranslate Version  6.10.0", ""]
        # The native's own help.txt, recovered from the installer payload and
        # bundled under qtranslate/assets/locales/en/. Reading it from the
        # Windows install only meant the port opened with a three-line stub
        # everywhere else -- and the native opens with the WHOLE help text
        # (Global hotkeys + Main window hotkeys + mouse modes + Actions).
        import os
        for _path in (
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "assets", "locales", "en", "help.txt"),
                "C:/Program Files (x86)/QTranslate/Locales/English/help.txt"):
            try:
                with open(_path, encoding="utf-8-sig") as f:
                    lines.append(f.read().strip())
                return "\\n".join(lines)
            except Exception:
                continue
        lines.append("Double Ctrl => Show main window\\n"
                     "Ctrl+Q => Translate selected text\\n"
                     "Ctrl+E => Listen to selected text")
        return "\\n".join(lines)
'''))


def main() -> int:
    for path, old, new in EDITS:
        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            print(f"{path}: anchor found {count} times (expected 1): "
                  f"{old[:60]!r}", file=sys.stderr)
            return 2
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        print(f"patched {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
