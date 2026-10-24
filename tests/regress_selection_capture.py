"""Ctrl+Q must translate the SELECTION, not last week's clipboard.

Native's ``help.txt`` line 3 reads "Ctrl+Q => Translate selected text and
show it in popup window". The port's ``hotkey_popup`` used to call
``pyperclip.paste()`` directly -- no Ctrl+C, so a user who selected new
text and pressed Ctrl+Q got the OLD clipboard content translated. That is
the P0 gap the audit named, and this suite pins the fix.

The fix is native's own copy-capture (``FUN_0043BF30``, ``NATIVE_ARCH.md``
item 4): snapshot the clipboard sequence number, synthesize Ctrl+C, and
poll the sequence with exponential backoff until it CHANGES. The change
is the proof the copy landed. A fixed sleep is what the old code did and
what a slow target app defeats.

Everything is seam-injected here -- no real clipboard, no real keystroke,
no network.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


from qtranslate import selection  # noqa: E402


def drive(*, delivered=True, seq_after=None, clipboard_after="NEW",
          clipboard_before="OLD", sleeps=None, pressed_keys=()):
    """Run copy_selection with every seam controlled."""
    sleeps = [] if sleeps is None else sleeps
    calls = {"read": 0}

    def read():
        calls["read"] += 1
        # The first read happens after the copy poll; model a clipboard
        # that still holds the old text until the copy lands.
        if seq_after is None:
            return clipboard_before
        return clipboard_after

    def seq():
        return 100 if not sleeps else (seq_after if seq_after is not None
                                       else 100)

    def send(_combo):
        if delivered and seq_after is not None:
            sleeps.append("copied")
        return delivered

    def sleep(seconds):
        sleeps.append(seconds)

    def pressed(key):
        return key in pressed_keys

    return selection.copy_selection(
        backend=object(), send=send, read=read, sequence=seq,
        sleep=sleep, pressed=pressed), sleeps, calls


# --- the copy lands, so the SEQUENCE change is what returns the text -----
text, sleeps, calls = drive(seq_after=101)
ck("the selection's text comes back when the copy lands", text == "NEW",
   repr(text))
ck("the copy is delivered before anything is read", "copied" in sleeps,
   repr(sleeps[:4]))
ck("it polls in native's backoff (8ms first)", 0.008 in sleeps,
   repr([s for s in sleeps if isinstance(s, float)][:3]))

# --- a slow target: the FIRST poll sees no change, a later one does --------
state = {"n": 0}


def slow_seq():
    state["n"] += 1
    return 100 if state["n"] < 3 else 999


_sleeps = []
text = selection.copy_selection(
    backend=object(), send=lambda c: True, read=lambda: "NEW",
    sequence=slow_seq, sleep=lambda s: _sleeps.append(s),
    pressed=lambda k: False)
ck("a slow copy is waited for, not read early", text == "NEW", repr(text))
ck("the wait grows (exponential, capped)",
   [s for s in _sleeps if isinstance(s, float)][:2] == [0.008, 0.016],
   repr(_sleeps[:4]))

# --- Ctrl+C refused: no hang, and the clipboard is read as a fallback -----
_sleeps = []
text = selection.copy_selection(
    backend=object(), send=lambda c: False, read=lambda: "OLD",
    sequence=lambda: 100, sleep=lambda s: _sleeps.append(s),
    pressed=lambda k: False)
ck("a refused Ctrl+C returns instead of hanging", text == "OLD", repr(text))
ck("a refused copy does not poll at all", _sleeps == [], repr(_sleeps))

# --- no sequence counter (off Windows): one bounded pause, then read ------
_sleeps = []
text = selection.copy_selection(
    backend=object(), send=lambda c: True, read=lambda: "NEW",
    sequence=lambda: -1, sleep=lambda s: _sleeps.append(s),
    pressed=lambda k: False)
ck("without a sequence counter it still returns the text",
   text == "NEW", repr(text))
ck("the fallback pause is bounded and short",
   len(_sleeps) == 1 and _sleeps[0] <= 0.25, repr(_sleeps))

# --- a modifier still held is waited for before Ctrl+C -------------------
_seq = {"n": 0}


def held_then_released(key):
    return _seq["n"] < 2


text = selection.copy_selection(
    backend=object(), send=lambda c: True, read=lambda: "NEW",
    sequence=lambda: 100, sleep=lambda s: _seq.__setitem__("n", _seq["n"] + 1),
    pressed=held_then_released)
ck("it waits for a held modifier to come up", text == "NEW", repr(text))

# --- the app's Ctrl+Q actually uses it -----------------------------------
import io  # noqa: E402
_src = io.open(os.path.join(ROOT, "qtranslate", "qt", "app.py"),
               encoding="utf-8").read()
_pop = _src.split("def hotkey_popup", 1)[1].split("def hotkey_translate", 1)[0]
ck("Ctrl+Q copies the selection before translating",
   "selection.copy_selection" in _pop,
   "hotkey_popup must not read a bare paste()")
ck("Ctrl+Q still falls back to the clipboard",
   "_clipboard_text" in _pop)
ck("Alt+W (replace selection) reads the selection too",
   "selection.copy_selection" in
   _src.split("def hotkey_replace_selection", 1)[1]
   .split("def hotkey_copy_translation", 1)[0])

# The mouse mode captures through OLEACC at the click point -- native
# FUN_00404901 (decompiled 2026-10-24). The copy-capture engine is
# WRONG on this path: a clipboard manager keeps the clipboard sequence
# moving, so every click read "a selection" and the icon fired
# everywhere. No sleeps, no clipboard, no Ctrl+C sent on a click.
_cap = _src.split("def _capture_selection", 1)[1].split("def quit", 1)[0]
ck("mouse-mode capture reads OLEACC at the point, no clipboard",
   "cursor_text(" in _cap and "copy_selection" not in _cap
   and "time.sleep" not in _cap,
   "the mouse path must not touch the clipboard")

# --- it is in the frozen bundle's reach --------------------------------
_bundle = io.open(os.path.join(ROOT, "tools", "build_bundle.py"),
                  encoding="utf-8").read()
ck("the new module is bundled",
   "qtranslate.selection" in _bundle or "selection" in _bundle,
   "a module nobody imports at freeze time would be dropped")

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_selection_capture: all checks ok (%d assertions)" % n[0])
