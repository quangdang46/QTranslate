"""Rewrite the Options pages to native's DLGs (2026-10-21).

Native's Options window is DLG154 -- a shell with a nav list (1078) and
OK/Cancel/Apply -- hosting NINE page dialogs, one per nav entry. The
mapping is fixed by the templates (`tools/dlg_parse.py`):

    Basics     171     Hotkeys    179     Internet   172
    Services   173     Languages  174     Appearance 175
    Exceptions 176     Advanced   185     Updates    205

and the page's controls are in the template, in a fixed order, with a
fixed widget CLASS (ComboBox vs Edit vs group box). The port's pages had
drifted from all three: the group boxes had become bold Labels, the
ComboBoxes had become Entries, and one page (Languages) was a page
native does not have at all.

DLG190 ("Languages") is a SEPARATE top-level dialog -- the language-pair
manager -- not the Options "Languages" page; the page is DLG174, the
language checkbox grid.

Every control id below is native's. The label text comes from the
English language pack via `_Cw`, which is native's runtime string; the
fallback in `_Cw` is only used when the pack has no entry for the id.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

WIN = Path("qtranslate/windows.py")

# ---------------------------------------------------------------- helpers

HELPERS = '''
        def _group(parent, page, cid, default):
            """A native GROUP BOX as a LabelFrame.

            Native's groups are DLGITEMTEMPLATEEX `Button(AUTORADIOBUTTON)`
            -- a Win32 group box: a sunken frame with the caption inset
            into its top edge. The Tk equivalent is a LabelFrame, and the
            port's bold Label was the wrong control (it drew a caption
            with no frame at all).
            """
            lf = tk.LabelFrame(parent, text=_Cw(page, cid, default),
                               bg=_COLORS["back"], fg=_COLORS["text"],
                               font=("Segoe UI", 9, "bold"),
                               highlightthickness=1, borderwidth=1)
            lf.pack(fill="x", pady=(6, 2))
            return lf

        def _row(parent, page, cid, default, value="", width=22,
                 values=None, label_width=22):
            """One label + control row, the shape native uses throughout:
            a fixed-width Static on the left, the control on the right."""
            r = tk.Frame(parent, bg=_COLORS["back"])
            r.pack(fill="x", pady=1)
            tk.Label(r, text=_Cw(page, cid, default), width=label_width,
                     anchor="w", bg=_COLORS["back"],
                     fg=_COLORS["text"]).pack(side="left")
            if values is not None:
                w = ttk.Combobox(r, values=values, width=width,
                                 state="readonly")
                w.pack(side="left")
                if value:
                    w.set(str(value))
            else:
                w = tk.Entry(r, width=width)
                w.pack(side="left")
                w.insert(0, "" if value is None else str(value))
            return w

        def _check(parent, page, cid, default, var, command=None):
            tk.Checkbutton(parent, text=_Cw(page, cid, default),
                           variable=var, bg=_COLORS["back"],
                           fg=_COLORS["text"], selectcolor=_COLORS["back"],
                           command=command).pack(anchor="w")

'''

# ------------------------------------------------------------- Appearance

APPEARANCE = '''        def show_appearance():
            # Native DLG 175 -- Options page 14 ("Appearance").
            #
            # Two group boxes (1076 "General", 1124 "Popup window") and a
            # fixed control order inside them:
            #
            #   1076 General       1123 'Enable window style'
            #                       1169 'Theme:'            1168 ComboBox
            #   1124 Popup window  1158 'Enable auto size'
            #                       1160 'Enable auto position'
            #                       1159 'Activate when opened'
            #                       1161 'Pin when dragging'
            #                       1147 'Auto-hide delay:'   1171 ComboBox
            #                                                       1194 'seconds'
            #                       1145 'Transparency (0 - 90):' 1144 Edit
            #                       1146 'Frame thickness:'   1170 ComboBox
            #                       1137 'Icons:'             1138-1141
            #                       1092 'Background color:' 1091 'Text color:'
            #                       1090 'Frame color:'
            #
            # The port had the four popup checkboxes in the GENERAL group,
            # used Entries where native has ComboBoxes, and drew the
            # colour fields as text entries instead of swatches.
            for c in body.winfo_children():
                c.destroy()
            _ap = cfg.get("Appearance", {})
            self.app._opt_vars = getattr(self, "_opt_vars", {})

            def _save(key, value):
                try:
                    from qtranslate import config as _CAF
                    import json as _jaf
                    full = _CAF.load()
                    full.setdefault("Appearance", {})[key] = value
                    with open(_CAF.DEFAULT_PATH, "w",
                              encoding="utf-8") as fh:
                        _jaf.dump(full, fh, ensure_ascii=False, indent=1)
                    _ap[key] = value
                except Exception:
                    pass

            # --- 1076 "General" ------------------------------------------
            gen = _group(body, 14, 1076, "General")
            _ws = tk.BooleanVar(value=bool(_ap.get("EnableWindowStyle",
                                                    False)))
            self.app._opt_vars["EnableWindowStyle"] = _ws
            _check(gen, 14, 1123, "Enable window style", _ws,
                   lambda: _save("EnableWindowStyle", _ws.get()))
            _r = tk.Frame(gen, bg=_COLORS["back"])
            _r.pack(fill="x", pady=1)
            tk.Label(_r, text=_Cw(14, 1169, "Theme:"), width=22,
                     anchor="w", bg=_COLORS["back"],
                     fg=_COLORS["text"]).pack(side="left")
            # 1168 is a ComboBox. Native's first entry is the default
            # theme ("--- Default ---"), and an empty ThemeName IS that
            # entry -- native stores the empty string for it.
            _tv = ["--- Default ---"] + [t for t in _THEMES]
            _th = ttk.Combobox(_r, values=_tv, width=26, state="readonly")
            _th.pack(side="left")
            _cur = _ap.get("ThemeName") or ""
            _th.set(_cur if _cur in _THEMES else "--- Default ---")

            def _theme_pick(e=None):
                _name = "" if _th.get() == "--- Default ---" else _th.get()
                _save("ThemeName", _name)
                try:
                    self.app.apply_theme(_name)
                except Exception:
                    pass
            _th.bind("<<ComboboxSelected>>", _theme_pick)

            # --- 1124 "Popup window" -------------------------------------
            pop = _group(body, 14, 1124, "Popup window")
            for cid, key in ((1158, "PopupAutoSize"),
                             (1160, "PopupAutoPos"),
                             (1159, "PopupAutoFocus"),
                             (1161, "PopupPinWhenDragging")):
                _v = tk.BooleanVar(value=bool(_ap.get(key, False)))
                self.app._opt_vars[key] = _v
                _check(pop, 14, cid, "", _v,
                       lambda k=key, v=_v: _save(k, v.get()))

            # 1147 'Auto-hide delay:' + 1171 ComboBox + 1194 'seconds'
            _r = tk.Frame(pop, bg=_COLORS["back"])
            _r.pack(fill="x", pady=1)
            tk.Label(_r, text=_Cw(14, 1147, "Auto-hide delay:"), width=22,
                     anchor="w", bg=_COLORS["back"],
                     fg=_COLORS["text"]).pack(side="left")
            _to = ttk.Combobox(_r, values=[str(i) for i in range(0, 121)],
                               width=6, state="readonly")
            _to.pack(side="left")
            _to.set(str(int(_ap.get("PopupTimeout", 0) or 0)))
            _to.bind("<<ComboboxSelected>>",
                     lambda e: _save("PopupTimeout", int(_to.get())))
            tk.Label(_r, text=_Cw(14, 1194, "seconds"), bg=_COLORS["back"],
                     fg=_COLORS["text"]).pack(side="left", padx=(4, 0))

            # 1145 'Transparency (0 - 90):' + 1144 Edit
            _tr = _row(pop, 14, 1145, "Transparency (0 - 90):",
                       value=_ap.get("Transparency", 0), width=26)
            _tr.bind("<FocusOut>",
                     lambda e: _save("Transparency", _tr.get()))

            # 1146 'Frame thickness:' + 1170 ComboBox
            _r = tk.Frame(pop, bg=_COLORS["back"])
            _r.pack(fill="x", pady=1)
            tk.Label(_r, text=_Cw(14, 1146, "Frame thickness:"), width=22,
                     anchor="w", bg=_COLORS["back"],
                     fg=_COLORS["text"]).pack(side="left")
            _ft = ttk.Combobox(_r, values=[str(i) for i in range(0, 9)],
                               width=6, state="readonly")
            _ft.pack(side="left")
            _ft.set(str(int(_ap.get("PopupWindowFrameThickness", 2) or 0)))
            _ft.bind("<<ComboboxSelected>>",
                     lambda e: _save("PopupWindowFrameThickness",
                                     int(_ft.get())))

            # 1137 'Icons:' + 1138-1141. Native draws these as four
            # icon buttons with NO text; the glyphs are a document
            # (dictionary), a headphone (listen), two sheets (copy) and
            # "b" over "a" (romanization). The port drew four labelled
            # checkboxes, which is a different control and a different
            # shape.
            _r = tk.Frame(pop, bg=_COLORS["back"])
            _r.pack(fill="x", pady=1)
            tk.Label(_r, text=_Cw(14, 1137, "Icons:"), width=22, anchor="w",
                     bg=_COLORS["back"],
                     fg=_COLORS["text"]).pack(side="left")
            _icons = tk.Frame(_r, bg=_COLORS["back"])
            _icons.pack(side="left")
            _cur_mask = int(_ap.get("PopupIcons", 30) or 0)
            for cid, bit, glyph in ((1138, 2, "\\U0001F4C4"),
                                    (1139, 4, "\\U0001F3A7"),
                                    (1140, 8, "\\u29c9"),
                                    (1141, 16, "b\\u2090")):
                _on = bool(_cur_mask & bit)
                _b = tk.Button(_icons, text=glyph, width=3, height=1,
                               relief="sunken" if _on else "raised",
                               bg=_COLORS["back"], fg=_COLORS["text"],
                               font=("Segoe UI", 9))
                _b.pack(side="left", padx=1)

                def _flip(b=bit, btn=_b, cid=cid):
                    nonlocal _cur_mask
                    _cur_mask = (_cur_mask | b) if not (_cur_mask & b) \\
                        else (_cur_mask & ~b)
                    btn.configure(relief="sunken" if (_cur_mask & b)
                                  else "raised")
                    _save("PopupIcons", _cur_mask)
                _b.configure(command=_flip)
                self.app._opt_vars["PopupIcons_%d" % bit] = _b

            # 1092 / 1091 / 1090 -- native draws a colour SWATCH next to
            # each caption, not a text field.
            _r = tk.Frame(pop, bg=_COLORS["back"])
            _r.pack(fill="x", pady=2)
            for cid, key, default in ((1092, "ColorBack", 15790320),
                                      (1091, "ColorText", 0),
                                      (1090, "ColorFrame", 8023133)):
                _c = tk.Label(_r, text=_Cw(14, cid, ""), bg=_COLORS["back"],
                              fg=_COLORS["text"])
                _c.pack(side="left", padx=(0, 2))
                _sw = tk.Frame(_r, width=86, height=16,
                               bg="#%06x" % int(_ap.get(key, default)),
                               relief="sunken", borderwidth=2)
                _sw.pack(side="left", padx=(0, 8))
                self.app._opt_vars[key] = _sw

                def _pick(k=key, w=_sw, d=default):
                    try:
                        from tkinter import colorchooser as _cc
                        _rgb = _cc.askcolor(title=_Cw(14, 1092, "Color"))
                    except Exception:
                        return
                    if not _rgb or _rgb[0] is None:
                        return
                    _val = (_rgb[0] << 16) | (_rgb[1] << 8) | _rgb[2]
                    w.configure(bg="#%06x" % _val)
                    _save(k, _val)
                _sw.bind("<Button-1>", lambda e, f=_pick: f())

'''

# -------------------------------------------------------------- Languages

LANGUAGES = '''        def show_languages():
            # Native DLG 174 -- Options page 13 ("Languages").
            #
            #   1089  SysListView32   the language checklist
            #   1099  Button          'Check / Uncheck all'
            #
            # That is the WHOLE page: a four-column grid of checkboxes,
            # one per language, and one button. The port's page was a
            # different page entirely -- "Default languages" with
            # Translate from/to, Dictionary, Virtual keyboard, Always
            # detect, Smart detection, Language pairs and a Disabled
            # languages list. None of that is native's Languages page.
            #
            # The per-slot defaults the port put here belong to the MAIN
            # window's language combos, and the language-pair editor is
            # native's DLG190 -- a separate top-level "Languages" dialog,
            # opened from the main window's language combo (see
            # `open_language_pairs`).
            #
            # The checklist is native's own list (qtranslate/screens.py
            # LANGUAGE_COLUMNS, transcribed from the capture): 72
            # languages, alphabetical, four columns. The port's language
            # table has two more (Welsh, Yiddish) that native does not
            # list here.
            for c in body.winfo_children():
                c.destroy()
            try:
                from qtranslate.services.google_translate import (
                    SUPPORTED_LANGS as _SL)
                _table = list(_SL)
            except Exception:
                _table = [-1, "auto", "en", "vi"]
            _gen = cfg.get("General", {})
            _dis = set(cfg.get("DisabledLanguages", []))
            self.app._opt_vars = getattr(self, "_opt_vars", {})

            def _save():
                try:
                    from qtranslate import config as C3
                    import json as _j
                    full = C3.load()
                    full["DisabledLanguages"] = sorted(_dis)
                    with open(C3.DEFAULT_PATH, "w",
                              encoding="utf-8") as f:
                        _j.dump(full, f, ensure_ascii=False, indent=1)
                    cfg["DisabledLanguages"] = sorted(_dis)
                except Exception:
                    pass

            # Native's list, in native's order, mapped to the port's
            # language-table index (the index is what the config stores).
            _names = []
            for _col in _LANGUAGE_COLUMNS:
                for _n in _col.split(" "):
                    _names.append(_n.replace("_", " "))
            _idx_of = {}
            for _i, _code in enumerate(_table):
                _d = LANG_DISPLAY.get(_code, _code)
                _idx_of.setdefault(_d, _i)
            _rows = []
            for _n in _names:
                _i = _idx_of.get(_n)
                if _i is not None:
                    _rows.append((_n, _i))

            _frame = tk.Frame(body, bg=_COLORS["back"])
            _frame.pack(fill="both", expand=True)
            _vars = {}
            for _n, _i in _rows:
                _v = tk.BooleanVar(value=_i not in _dis)
                _vars[_i] = _v
                self.app._opt_vars["Lang_%d" % _i] = _v

            def _toggle(_i):
                if _vars[_i].get():
                    _dis.discard(_i)
                else:
                    _dis.add(_i)
                _save()

            # Four columns, as native lays the list out. The columns are
            # filled top-to-bottom (column-major), which is what native's
            # list view does.
            _cols = 4
            _nrows = (len(_rows) + _cols - 1) // _cols
            for _c in range(_cols):
                _colf = tk.Frame(_frame, bg=_COLORS["back"])
                _colf.grid(row=0, column=_c, sticky="nw")
                for _r in range(_nrows):
                    _k = _c * _nrows + _r
                    if _k >= len(_rows):
                        break
                    _n, _i = _rows[_k]
                    _cb = tk.Checkbutton(
                        _colf, text=_n, variable=_vars[_i],
                        bg=_COLORS["back"], fg=_COLORS["text"],
                        selectcolor=_COLORS["back"], anchor="w",
                        command=lambda i=_i: _toggle(i))
                    _cb.grid(row=_r, column=0, sticky="w")

            def _check_all():
                # 1099 'Check / Uncheck all': enable all if any language
                # is disabled, else disable them all.
                if _dis:
                    _dis.clear()
                else:
                    _dis.update(_i for _n, _i in _rows)
                for _i, _v in _vars.items():
                    _v.set(_i not in _dis)
                _save()
            tk.Button(body, text=_Cw(13, 1099, "Check / Uncheck all"),
                      command=_check_all).pack(anchor="w", pady=(8, 0))

'''


def replace_block(text: str, start: str, end: str, new: str) -> str:
    i = text.index(start)
    j = text.index(end, i)
    return text[:i] + new + text[j:]


def main() -> int:
    src = WIN.read_text(encoding="utf-8")
    before = src

    # The helpers go in right after the body frame is created.
    anchor = "        def show_basics():"
    assert src.count(anchor) == 1, "show_basics anchor"
    src = src.replace(anchor, HELPERS.lstrip("\n") + anchor, 1)

    src = replace_block(src, "        def show_appearance():",
                        "        def show_hotkeys():", APPEARANCE)
    src = replace_block(src, "        def show_languages():",
                        "        def show_internet():", LANGUAGES)

    WIN.write_text(src, encoding="utf-8")
    print("patched", WIN, len(before), "->", len(src))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
