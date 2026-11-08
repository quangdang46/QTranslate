"""Audit the port's UI captions against the locale pack native ships.

Qt-era rewrite (2026-11-09): the tkinter ``_Cw``/``_T``/``_W`` helpers are
gone; the Qt view resolves captions through ``qtranslate.locale``:

  * ``ui_caption(dialog_id, default)``      -- window/dialog titles
  * ``ui_page_caption(page_name)``          -- Options sidebar rows
    (the page name IS the fallback; nothing to drift)
  * ``ui_control_caption(dialog_id, cid, default)`` -- dialog controls
  * ``menu_labels(pack, menu_id)``          -- context menus / tray
    (pack-driven, no literal defaults)

This tool AST-scans ``qtranslate/qt/**/*.py`` for the two call shapes
that carry an English ``default`` and checks each default against the
shipped English pack (``Locales/English/lang.json`` in the installed
copy -- the same file native draws from). Two things can rot:

  1. a default that does not match the pack (the port shows a
     paraphrase where native shows its own string);
  2. a call with no default (an empty label when no pack loads).

Exit codes: 0 = every call matches the pack; 1 = at least one drift;
2 = the pack or the target tree is not present (nothing to compare).
"""
from __future__ import annotations

import ast
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# The pack the app itself resolves: bundled assets first (the 35 recovered
# lang.json files are committed), the installed copy as fallback -- the
# same order locale.LOCALES_DIR uses, so the audit compares against
# exactly what the running app would draw.
from qtranslate import locale as _L  # noqa: E402
EN_PACK = os.path.join(_L.LOCALES_DIR, "English", "lang.json")

TARGETS = sorted(glob.glob(os.path.join(ROOT, "qtranslate", "qt", "**",
                                        "*.py"), recursive=True))


def _pack():
    from qtranslate import locale as L
    return L.load_pack("English")


def _windows(pack):
    """{dialog_id: {"caption": str|None, "controls": {cid: text}}}"""
    wins = {}
    for w in pack.get("Windows", ()):
        if not isinstance(w, dict):
            continue
        ctl = {}
        for c in (w.get("Controls") or ()):
            if isinstance(c, (list, tuple)) and len(c) >= 2:
                ctl[c[0]] = c[1]
        wins[w.get("Id")] = {"caption": w.get("Caption"), "controls": ctl}
    return wins


def _lit(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None


def _rel(path):
    return os.path.relpath(path, ROOT).replace("\\", "/")


def main():
    if not TARGETS:
        print("no qtranslate/qt sources found -- nothing to scan")
        return 2
    if not os.path.exists(EN_PACK):
        print("no English pack at %s -- nothing to compare against"
              % EN_PACK)
        return 2
    wins = _windows(_pack())

    drifts = []
    checked = 0
    for path in TARGETS:
        rel = _rel(path)
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if not isinstance(f, ast.Name):
                continue
            args = node.args
            if f.id == "ui_caption":
                # ui_caption(dialog_id, default)
                if len(args) < 2:
                    continue
                wid, dflt = _lit(args[0]), _lit(args[1])
                if wid is None:
                    continue
                nat = wins.get(wid, {}).get("caption")
                if not nat or isinstance(nat, list):
                    continue
                checked += 1
                if dflt is None:
                    drifts.append("%s:%d ui_caption(%s) has NO default; "
                                  "the English UI shows an empty title "
                                  "(native: %r)"
                                  % (rel, node.lineno, wid, nat))
                elif dflt != nat:
                    drifts.append("%s:%d ui_caption(%s) port=%r native=%r"
                                  % (rel, node.lineno, wid, dflt, nat))
            elif f.id == "ui_control_caption":
                # ui_control_caption(dialog_id, control_id, default)
                if len(args) < 3:
                    continue
                wid, cid, dflt = (_lit(args[0]), _lit(args[1]),
                                  _lit(args[2]))
                if wid is None or cid is None:
                    continue
                nat = wins.get(wid, {}).get("controls", {}).get(cid)
                if nat is None or isinstance(nat, list):
                    continue
                checked += 1
                if dflt is None:
                    drifts.append("%s:%d ui_control_caption(%s,%s) has NO "
                                  "default (native: %r)"
                                  % (rel, node.lineno, wid, cid, nat))
                elif dflt != nat:
                    drifts.append("%s:%d ui_control_caption(%s,%s) "
                                  "port=%r native=%r"
                                  % (rel, node.lineno, wid, cid,
                                     dflt, nat))

    if drifts:
        print("UI-LABEL AUDIT: %d DRIFT(S) of %d checked"
              % (len(drifts), checked))
        for d in drifts:
            print("  -", d)
        return 1
    print("ui-label audit: all checks ok (%d captions)" % checked)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
