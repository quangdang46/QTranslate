"""Audit the port's UI labels against the locale pack native ships.

The port resolves every Options-dialog caption through ``_Cw(window_id,
control_id, default)``. The third argument is the ENGLISH text shown when
no pack is loaded -- and the pack IS shipped, at
``Locales/English/lang.json`` in the installed copy, with the exact
captions native draws.

Two things can therefore rot, and this tool catches both:

  1. a default that does not match the shipped English pack (the port
     shows a paraphrase where native shows its own string);
  2. a call with no default at all (the label is empty in English).

It also checks ``_T`` (the Strings/Menus sections) and ``_W`` (dialog
titles) the same way.

The comparison is AST-based, so a call split across lines is still read.

Exit codes: 0 = every call matches the pack; 1 = at least one drift;
2 = the pack is not installed (nothing to compare against).
"""
from __future__ import annotations

import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

INSTALLED = os.environ.get(
    "QTRANSLATE_DIR", r"C:\Program Files (x86)\QTranslate")
EN_PACK = os.path.join(INSTALLED, "Locales", "English", "lang.json")

TARGETS = ("qtranslate/windows.py", "qtranslate/app.py")


def _pack():
    from qtranslate import locale as L
    return L.load_pack("English")


def _index(pack):
    """{dialog_id: {control_id: caption}} and the Strings/Menus tables."""
    wins = {}
    for w in pack.get("Windows", ()):
        if isinstance(w, dict):
            ctl = {}
            for c in (w.get("Controls") or ()):
                if isinstance(c, (list, tuple)) and len(c) >= 2:
                    ctl[c[0]] = c[1]
            wins[w.get("Id")] = ctl
    strings = {}
    for s in pack.get("Strings", ()):
        if isinstance(s, (list, tuple)) and len(s) >= 2:
            strings[s[0]] = s[1]
    menus = {}
    for m in pack.get("Menus", ()):
        if isinstance(m, dict):
            items = {}
            for it in (m.get("Items") or ()):
                if isinstance(it, (list, tuple)) and len(it) >= 2:
                    items[it[0]] = it[1]
            menus[m.get("Id")] = items
    return wins, strings, menus


def _lit(node):
    """The literal value of an AST node, or None if it is not a literal."""
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None


def main():
    if not os.path.exists(EN_PACK):
        print("no English pack at %s -- nothing to compare against"
              % EN_PACK)
        return 2
    pack = _pack()
    wins, strings, menus = _index(pack)

    drifts = []
    checked = 0
    for rel in TARGETS:
        path = os.path.join(ROOT, rel)
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if not isinstance(f, ast.Name) or f.id not in ("_Cw", "_T", "_W"):
                continue
            args = node.args
            if f.id == "_Cw":
                if len(args) < 2:
                    continue
                wid, cid = _lit(args[0]), _lit(args[1])
                if wid is None or cid is None:
                    continue
                dflt = _lit(args[2]) if len(args) > 2 else None
                nat = wins.get(wid, {}).get(cid)
                if nat is None or isinstance(nat, list):
                    continue
                checked += 1
                if dflt is None:
                    drifts.append("%s:%d _Cw(%s,%s) has NO default; the "
                                  "English UI shows an empty label (native: "
                                  "%r)" % (rel, node.lineno, wid, cid, nat))
                elif dflt != nat:
                    drifts.append("%s:%d _Cw(%s,%s) port=%r native=%r"
                                  % (rel, node.lineno, wid, cid, dflt, nat))
            elif f.id == "_T":
                if len(args) < 2:
                    continue
                sect, sid = _lit(args[0]), _lit(args[1])
                if sect is None or sid is None:
                    continue
                dflt = _lit(args[2]) if len(args) > 2 else None
                menu = _lit(args[3]) if len(args) > 3 else None
                if sect == "Strings":
                    nat = strings.get(sid)
                elif sect == "Menus":
                    nat = menus.get(menu, {}).get(sid) if menu is not None \
                        else None
                else:
                    nat = None
                if nat is None:
                    continue
                checked += 1
                if dflt is None:
                    drifts.append("%s:%d _T(%r,%s) has NO default (native: %r)"
                                  % (rel, node.lineno, sect, sid, nat))
                elif dflt != nat:
                    drifts.append("%s:%d _T(%r,%s) port=%r native=%r"
                                  % (rel, node.lineno, sect, sid, dflt, nat))
            else:  # _W
                if len(args) < 1:
                    continue
                wid = _lit(args[0])
                if wid is None:
                    continue
                dflt = _lit(args[1]) if len(args) > 1 else None
                nat = None
                for w in pack.get("Windows", ()):
                    if isinstance(w, dict) and w.get("Id") == wid:
                        nat = w.get("Caption")
                if not nat:
                    continue
                checked += 1
                if dflt is None:
                    drifts.append("%s:%d _W(%s) has NO default (native: %r)"
                                  % (rel, node.lineno, wid, nat))
                elif dflt != nat:
                    drifts.append("%s:%d _W(%s) port=%r native=%r"
                                  % (rel, node.lineno, wid, dflt, nat))

    if drifts:
        print("UI-LABEL AUDIT: %d DRIFT(S) of %d checked" % (len(drifts),
                                                             checked))
        for d in drifts:
            print("  -", d)
        return 1
    print("ui-label audit: all checks ok (%d captions)" % checked)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
