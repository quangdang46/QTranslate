"""Regression: the virtual keyboard and the history window, against native's DLGs.

Native's **virtual keyboard** (DLG 162) declares only the language combo
(1064) and a small static (1155) -- the key grid is built at run time --
so the layout is transcribed from native's own capture
(`docs/review/native_screens/2134.png`):

    Esc | F1 F2 F3 F4 | F5 F6 F7 F8 | F9 F10 F11 F12
    ` 1 2 3 4 5 6 7 8 9 0 - = | BkSp
    Tab | q w e r t y u i o p [ ] \\
    Caps | a s d f g h j k l ; ' | Enter
    Shift | z x v b n m , . / | Shift
    Ctrl Win Alt | (space) | AltGr Apps ^ v < >
    [language combo]

The port had three rows of letters and a space bar: no digits, no
capitals, no punctuation, and nothing to type a URL with.

Native's **history window** (DLG 164) declares six controls: the filter
edit (1170), the tree (1163) and the bottom row -- 1067 'Clear', 1160
'Save as...', 1173 (a radio carrying a star) and 1 'OK' (a
DEFPUSHBUTTON). The port had a wide 'Favorite' TEXT button where native
has a 15x14 star, and no OK button at all.

Every assertion here calls the real code and reads the real widget tree;
none of them greps source text.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(f"{name} -- {detail}")


import tkinter as tk  # noqa: E402
from qtranslate import app as A  # noqa: E402

root = tk.Tk()
root.withdraw()
app = A.App(root)
root.update_idletasks()
root.update()

# --- the virtual keyboard ---------------------------------------------------
kb = app.open_keyboard()
root.update_idletasks()
root.update()
ck("the virtual keyboard opens", kb is not None)

if kb is not None:
    labels = []
    for row in kb.winfo_children():
        if row.winfo_class() != "Frame":
            continue
        row_labels = []
        for child in row.winfo_children():
            if child.winfo_class() == "Label":
                row_labels.append(str(child.cget("text")))
        if row_labels:
            labels.append(row_labels)
    ck("the keyboard has native's six key rows", len(labels) == 6,
       str(len(labels)))
    _flat = " ".join(" ".join(r) for r in labels)
    for _key in ("Esc", "F1", "F12", "Tab", "Caps", "Enter", "Shift",
                 "Ctrl", "Win", "Alt", "AltGr", "Apps", "Space", "BkSp"):
        ck(f"the keyboard has the {_key!r} key", _key in _flat, _flat[:80])
    for _d in "0123456789":
        ck(f"the keyboard has the digit {_d!r}", _d in _flat, _flat[:80])
    for _p in "`-=[]\\;',./":
        ck(f"the keyboard has the punctuation {_p!r}", _p in _flat, _flat[:80])
    for _letter in "abcdefghijklmnopqrstuvwxyz":
        ck(f"the keyboard has the letter {_letter!r}", _letter in _flat)
    ck("the keyboard has the four arrow keys",
       all(a in _flat for a in ("^", "v", "<", ">")), _flat[:80])

    # The language combo (1064) shows the language at
    # General.LanguageKeyboard -- 17 is English in native's table.
    _combos = [c for c in kb.winfo_children() if c.winfo_class() == "TFrame"]
    _combo = None
    for _row in kb.winfo_children():
        if _row.winfo_class() != "Frame":
            continue
        for _c in _row.winfo_children():
            if _c.winfo_class() == "TCombobox":
                _combo = _c
    ck("the keyboard has the language combo (1064)", _combo is not None)
    if _combo is not None:
        ck("the keyboard's combo shows English (index 17 in native's table)",
           str(_combo.get()) == "English", repr(_combo.get()))

    # A key types into the source pane.
    app.src.delete("1.0", "end")
    _digit = None
    for _row in kb.winfo_children():
        if _row.winfo_class() != "Frame":
            continue
        for _child in _row.winfo_children():
            if _child.winfo_class() == "Label" \
                    and str(_child.cget("text")) == "7":
                _digit = _child
    ck("the keyboard has a '7' key", _digit is not None)
    if _digit is not None:
        _digit.event_generate("<Button-1>")
        root.update()
        ck("clicking a digit types it into the source pane",
           app.src.get("1.0", "end-1c") == "7", repr(app.src.get("1.0", "end-1c")))
        # ...and the backspace removes it.
        _bs = None
        for _row in kb.winfo_children():
            if _row.winfo_class() != "Frame":
                continue
            for _child in _row.winfo_children():
                if _child.winfo_class() == "Label" \
                        and str(_child.cget("text")) == "BkSp":
                    _bs = _child
        ck("the keyboard has a BkSp key", _bs is not None)
        if _bs is not None:
            _bs.event_generate("<Button-1>")
            root.update()
            ck("clicking BkSp deletes the last character",
               app.src.get("1.0", "end-1c") == "", repr(app.src.get("1.0", "end-1c")))
    app.src.delete("1.0", "end")

# --- the history window -----------------------------------------------------
hist = app.open_history_window()
root.update_idletasks()
root.update()
ck("the history window opens", hist is not None)

if hist is not None:
    buttons = []
    for row in hist.winfo_children():
        if row.winfo_class() != "Frame":
            continue
        for child in row.winfo_children():
            if child.winfo_class() == "Button":
                buttons.append((str(child.cget("text")),
                                str(child.cget("image"))))
    _texts = [t for t, _i in buttons]
    ck("the history window has native's 'Clear' (1067)",
       "Clear" in _texts, str(_texts))
    ck("the history window has native's 'Save as...' (1160)",
       "Save as..." in _texts, str(_texts))
    ck("the history window has native's 'OK' (control 1)",
       "OK" in _texts, str(_texts))
    ck("native's 1173 is a star, not a wide text button",
       not any("Favorite" in t for t in _texts), str(_texts))
    _star = [i for _t, i in buttons if i not in ("", "none")]
    ck("the favourites button carries the bundled star icon",
       bool(_star), str(buttons))

root.destroy()

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_aux_windows_fidelity: all checks ok (%d assertions)" % n[0])
