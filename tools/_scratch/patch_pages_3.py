"""Third Options-page pass: group boxes on Basics/Internet, native's
combo item lists, the icon row, and the button row's order.

Four things this fixes:

1. **Basics (DLG171) and Internet (DLG172) had no group boxes.**
   Native's pages are three and two group boxes respectively
   (1046/1063/1064 and 1049/1048); the port drew a bold Label where
   each frame belongs, so the page had no sunken frames at all.

2. **The Exceptions mode combo showed a raw Python list.** The language
   pack stores a combo's ITEMS as a list of `[index, text]` pairs
   (1162 in the Exceptions page, 1135 in Internet, 1165 in Hotkeys), and
   `_Cw` returns that list verbatim -- so the port put
   `[(0, 'Enabled for these programs:'), ...]` in the combo box.

3. **The Appearance "Icons:" row** used emoji that the Tk font does not
   carry (the document glyph rendered as a speck). Native's four are a
   document, a headphone, two sheets and "b" over "a".

4. **The Options button row read Apply / Cancel / OK.** Native's DLG154
   puts OK first (x 267), then Cancel (321), then Apply (375).
"""

from __future__ import annotations

from pathlib import Path

WIN = Path("qtranslate/windows.py")

EDITS: list[tuple[str, str, str]] = []


def E(old: str, new: str) -> None:
    EDITS.append((old, new))


# --- 1. the combo-items helper -------------------------------------------
E('''        def _group(parent, page, cid, default):''',
  '''        def _combo_items(page, cid, default):
            """A combo's ITEMS from the language pack.

            The pack stores a combo's entries as a list of
            `[index, text]` pairs (1162 in the Exceptions page, 1135 in
            Internet, 1165 in Hotkeys) -- `_Cw` hands that list back
            verbatim, so using it as a label printed the raw Python.
            """
            _raw = _Cw(page, cid, default)
            if isinstance(_raw, (list, tuple)):
                _out = []
                for _it in _raw:
                    if isinstance(_it, (list, tuple)) and len(_it) >= 2:
                        _out.append(str(_it[1]))
                    else:
                        _out.append(str(_it))
                return _out
            return [str(_raw)]

        def _group(parent, page, cid, default):''')

# --- 2. the Exceptions mode combo ----------------------------------------
E('''            _MODE_D = _Cw(15, 1162, "Disabled for these programs:")
            _MODE_E = _Cw(15, 1163, "Enabled for these programs:")
            _mode = tk.StringVar(value=_MODE_D)

            def _pairs():
                return _dis_list if _mode.get() == _MODE_D else _en_list
''',
  '''            # 1162 is the MODE combo. The pack lists its items as
            # [[0, 'Enabled for these programs:'],
            #  [1, 'Disabled for these programs:']] -- index 0 is
            # Enabled, index 1 is Disabled, and native's capture shows
            # the Disabled one selected.
            _modes = _combo_items(
                15, 1162, ["Enabled for these programs:",
                            "Disabled for these programs:"])
            _MODE_E = _modes[0] if _modes else "Enabled for these programs:"
            _MODE_D = _modes[1] if len(_modes) > 1 else _MODE_E
            _mode = tk.StringVar(
                value=_MODE_D if _ex.get("DisabledMode", True) else _MODE_E)

            def _pairs():
                return _dis_list if _mode.get() == _MODE_D else _en_list
''')

E('''            _cb = ttk.Combobox(_r, values=[_MODE_D, _MODE_E], width=48,
                               state="readonly")''',
  '''            _cb = ttk.Combobox(_r, values=list(_modes), width=48,
                               state="readonly")''')

E('''            _cb.set(_MODE_D)
            _cb.bind("<<ComboboxSelected>>",
                     lambda e: (_mode.set(_cb.get()), _refresh()))''',
  '''            _cb.set(_mode.get())
            _cb.bind("<<ComboboxSelected>>",
                     lambda e: (_mode.set(_cb.get()),
                                _ex.__setitem__("DisabledMode",
                                                _mode.get() == _MODE_D),
                                _save_x(), _refresh()))''')

# --- 3. the Options button row order --------------------------------------
E('''        tk.Button(frm, text="OK",
                  command=w.destroy).pack(side="right", padx=4)
        tk.Button(frm, text="Cancel",
                  command=_cancel).pack(side="right", padx=4)
        tk.Button(frm, text="Apply",
                  command=w.destroy).pack(side="right", padx=4)''',
  '''        # Packed right-to-left, so the LAST one packed is the leftmost:
        # DLG154's order is OK (x 267), Cancel (321), Apply (375).
        tk.Button(frm, text="Apply",
                  command=w.destroy).pack(side="right", padx=4)
        tk.Button(frm, text="Cancel",
                  command=_cancel).pack(side="right", padx=4)
        tk.Button(frm, text="OK",
                  command=w.destroy).pack(side="right", padx=4)''')

# --- 4. the Appearance icon row ------------------------------------------
E('''            for cid, bit, glyph in ((1138, 2, "\\U0001F4C4"),
                                    (1139, 4, "\\U0001F3A7"),
                                    (1140, 8, "\\u29c9"),
                                    (1141, 16, "b\\u2090")):
                _on = bool(_cur_mask & bit)
                _b = tk.Button(_icons, text=glyph, width=3, height=1,
                               relief="sunken" if _on else "raised",
                               bg=_COLORS["back"], fg=_COLORS["text"],
                               font=("Segoe UI", 9))
                _b.pack(side="left", padx=1)''',
  '''            # The four glyphs, as native draws them (measured off the
            # native capture 2138): a document (dictionary), a
            # headphone (listen), two sheets (copy) and "b" over "a"
            # (romanization). The document and headphone come from the
            # recovered RT_ICON set; the other two have no image, so
            # they are drawn with characters the Tk font carries.
            _doc_icon = ""
            try:
                import os as _os
                _p = _os.path.join(_os.path.dirname(
                    _os.path.abspath(__file__)), "assets", "ui_icons",
                    "headphone.png")
                if _os.path.exists(_p):
                    _doc_icon = tk.PhotoImage(file=_p)
                    _keep.append(_doc_icon)
            except Exception:
                _doc_icon = ""
            for cid, bit, glyph in ((1138, 2, "\\u25a4"),
                                    (1139, 4, None),
                                    (1140, 8, "\\u29c9"),
                                    (1141, 16, "b\\u2090")):
                _on = bool(_cur_mask & bit)
                if glyph is None:
                    _b = tk.Button(_icons, image=_doc_icon, width=3,
                                   height=1,
                                   relief="sunken" if _on else "raised",
                                   bg=_COLORS["back"], fg=_COLORS["text"])
                else:
                    _b = tk.Button(_icons, text=glyph, width=3, height=1,
                                   relief="sunken" if _on else "raised",
                                   bg=_COLORS["back"], fg=_COLORS["text"],
                                   font=("Segoe UI", 9))
                _b.pack(side="left", padx=1)''')

E('''            _cur_mask = int(_ap.get("PopupIcons", 30) or 0)''',
  '''            _cur_mask = int(_ap.get("PopupIcons", 30) or 0)
            _keep = []''')

# --- 5. Basics: the three group boxes -------------------------------------
E('''            tk.Label(body, text=_Cw(10, 1046, "General"), bg=_COLORS["back"],
                     fg=_COLORS["text"],
                     font=("Segoe UI", 10, "bold")).pack(anchor="w")
            self.app._opt_vars = getattr(self, "_opt_vars", {})''',
  '''            gen = _group(body, 10, 1046, "General")
            self.app._opt_vars = getattr(self, "_opt_vars", {})''')

E('''            tk.Checkbutton(body, text=_Cw(10, 1045, "Start with Windows"),
                           variable=_sv, command=_toggle_startup,
                           bg=_COLORS["back"], fg=_COLORS["text"],
                           selectcolor=_COLORS["back"]).pack(anchor="w")''',
  '''            tk.Checkbutton(gen, text=_Cw(10, 1045, "Start with Windows"),
                           variable=_sv, command=_toggle_startup,
                           bg=_COLORS["back"], fg=_COLORS["text"],
                           selectcolor=_COLORS["back"]).pack(anchor="w")''')

E('''                    (_Cw(10, 1074, "Text size:"), ["9"],
                     str(_gen.get("TextSize", 9)), "TextSize")):
                r = tk.Frame(body, bg=_COLORS["back"])''',
  '''                    (_Cw(10, 1074, "Text size:"), ["9"],
                     str(_gen.get("TextSize", 9)), "TextSize")):
                r = tk.Frame(gen, bg=_COLORS["back"])''')

E('''            tk.Label(body, text=_Cw(10, 1063, "Auto-detect languages"),
                     bg=_COLORS["back"], fg=_COLORS["text"],
                     font=("Segoe UI", 10, "bold")).pack(anchor="w",
                                                         pady=(8, 0))''',
  '''            adg = _group(body, 10, 1063, "Auto-detect languages")''')

E('''                             (_Cw(10, 1071, "Speech input:"),
                              "LanguageSpeechRecognition")):
                r = tk.Frame(body, bg=_COLORS["back"])''',
  '''                             (_Cw(10, 1071, "Speech input:"),
                              "LanguageSpeechRecognition")):
                r = tk.Frame(adg, bg=_COLORS["back"])''')

E('''            tk.Label(body, text=_Cw(10, 1064, "History"), bg=_COLORS["back"],
                     fg=_COLORS["text"],
                     font=("Segoe UI", 10, "bold")).pack(anchor="w",
                                                         pady=(8, 0))''',
  '''            hist = _group(body, 10, 1064, "History")''')

E('''                tk.Checkbutton(
                    body, text=lab, variable=v, bg=_COLORS["back"],
                    fg=_COLORS["text"], selectcolor=_COLORS["back"],
                    command=lambda k=key, vv=v: _save_history_flag(
                        k, vv)).pack(anchor="w")''',
  '''                tk.Checkbutton(
                    hist, text=lab, variable=v, bg=_COLORS["back"],
                    fg=_COLORS["text"], selectcolor=_COLORS["back"],
                    command=lambda k=key, vv=v: _save_history_flag(
                        k, vv)).pack(anchor="w")''')

# --- 6. Internet: the two group boxes -------------------------------------
E('''            tk.Label(body, text=_Cw(11, 1049, "Connection"), bg=_COLORS["back"],
                     fg=_COLORS["text"],
                     font=("Segoe UI", 10, "bold")).pack(anchor="w")''',
  '''            con = _group(body, 11, 1049, "Connection")''')

E('''            tk.Label(body, text=_Cw(11, 1048, "Proxy"), bg=_COLORS["back"],
                     fg=_COLORS["text"],
                     font=("Segoe UI", 10, "bold")).pack(anchor="w",
                                                         pady=(8, 0))''',
  '''            px = _group(body, 11, 1048, "Proxy")''')


def main() -> int:
    src = WIN.read_text(encoding="utf-8")
    for old, new in EDITS:
        n = src.count(old)
        if n != 1:
            print("anchor found %d times (expected 1): %r" % (n, old[:70]))
            return 2
        src = src.replace(old, new, 1)
    WIN.write_text(src, encoding="utf-8")
    print("patched", WIN, len(EDITS), "edits")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
