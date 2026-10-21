"""Patch app.py: native overlay glyphs and a tool row that cannot overflow.

Two fixes, both measured against `docs/review/native_screens/2131.png`:

1. The source pane's bottom-right overlay buttons were the TEXT "Mic" and a
   music note (U+266B). Native draws a **microphone** and a **headphone**
   icon there — recovered from the EXE's RT_ICON resources and now bundled
   as `qtranslate/assets/ui_icons/`. The native's glyph boxes are at
   x 453..464 (mic) and 474..487 (headphone) in a pane whose right edge is
   at ~500, i.e. 36px and 13px in from the right, and their bottoms sit 9px
   above the pane's bottom.

2. The tool row was packed left to right, so on a 516px window the
   **Translate button was cut off** at the right edge (the port drew it at
   x 481..497, native at 438..510). It is now gridded with weighted
   combobox columns, so the Translate button is always fully visible and the
   two comboboxes share the space the way native's do.
"""

from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path("qtranslate/app.py")

OLD_OVERLAY = '''        # Tahoma glyphs (emoji mic/headphone render blank on win32 Tk)
        _ovl = dict(borderwidth=0, bg="white", font=("Tahoma", 7),
                    relief="flat", highlightthickness=0, takefocus=0)
        for _i, (_txt, _fn) in enumerate((("Mic", self.on_mic),
                                          ("♫", self.on_listen))):
            b = tk.Button(srcfrm, text=_txt, command=_fn, width=4, **_ovl)
            b.place(relx=1.0, rely=1.0, anchor="se",
                    x=-(13 + _i * 26), y=-5)
'''

NEW_OVERLAY = '''        # Native overlays a MICROPHONE and a HEADPHONE on the source pane's
        # bottom-right (native glyph boxes x 453..464 and 474..487 in a pane
        # whose right edge is at ~500, bottoms 9px above the pane's bottom).
        # The icons are native's own, recovered from the EXE's RT_ICON
        # resources and bundled under qtranslate/assets/ui_icons/.
        _ovl = dict(borderwidth=0, bg="white", relief="flat",
                    highlightthickness=0, takefocus=0)
        for _i, (_key, _fn, _dx) in enumerate(
                (("mic", self.on_mic, 36), ("headphone", self.on_listen, 13))):
            _photo = self._ui_icon(_key)
            b = tk.Button(srcfrm, command=_fn, **_ovl)
            if _photo is not None:
                b.config(image=_photo, width=SVC_ICON_PX, height=SVC_ICON_PX)
            else:
                b.config(text="Mic" if _key == "mic" else "Head",
                         font=("Tahoma", 7), width=6)
            b.place(relx=1.0, rely=1.0, anchor="se", x=-_dx, y=-9)
'''

OLD_BAR = '''        bar = tk.Frame(self.root, bg=bg)
        bar.pack(fill="x", padx=4, pady=2)
        # id1021 "New": clears source for a fresh translation
        tk.Button(bar, text="\\U0001f4cb", width=3,
                  command=self.on_new).pack(side="left", padx=1)
        tk.Button(bar, text="⋮", width=3,
                  command=self.show_nav_menu).pack(side="left", padx=1)
        self.src_lang = ttk.Combobox(bar, values=_lang_names(LANGS),
                                     width=13, state="readonly")
        self.src_lang.set(LANG_DISPLAY.get(self.source, "Auto-Detect"))
        self.src_lang.pack(side="left", padx=2)
        tk.Button(bar, text="⇄", width=3, font=("Segoe UI Symbol", 10),
                  command=self.on_swap).pack(side="left", padx=1)
        self.tgt = ttk.Combobox(bar, values=_lang_names(TO_LANGS,
                                                        False),
                                width=13, state="readonly")
        self.tgt.set(LANG_DISPLAY.get(self.target, self.target))
        self.tgt.pack(side="left", padx=2)
'''

NEW_BAR = '''        bar = tk.Frame(self.root, bg=bg)
        bar.pack(fill="x", padx=4, pady=2)
        # GRID, not pack: native's tool row always fits -- the Translate
        # button sits at the right edge (native x 438..510 of 516). Packed
        # left to right, the row overflowed a 516px window and the Translate
        # button was cut off (the port drew it at x 481..497). The two
        # combobox columns carry the weight, so they share whatever is left.
        bar.columnconfigure(2, weight=1)
        bar.columnconfigure(4, weight=1)
        # id1021 "New": clears source for a fresh translation
        tk.Button(bar, text="\\U0001f4cb", width=3,
                  command=self.on_new).grid(row=0, column=0, sticky="w", padx=1)
        tk.Button(bar, text="⋮", width=3,
                  command=self.show_nav_menu).grid(row=0, column=1, sticky="w",
                                                   padx=1)
        self.src_lang = ttk.Combobox(bar, values=_lang_names(LANGS),
                                     width=13, state="readonly")
        self.src_lang.set(LANG_DISPLAY.get(self.source, "Auto-Detect"))
        self.src_lang.grid(row=0, column=2, sticky="ew", padx=2)
        tk.Button(bar, text="⇄", width=3, font=("Segoe UI Symbol", 10),
                  command=self.on_swap).grid(row=0, column=3, sticky="w",
                                             padx=1)
        self.tgt = ttk.Combobox(bar, values=_lang_names(TO_LANGS,
                                                        False),
                                width=13, state="readonly")
        self.tgt.set(LANG_DISPLAY.get(self.target, self.target))
        self.tgt.grid(row=0, column=4, sticky="ew", padx=2)
'''

OLD_GO = '''        tk.Button(bar, text=_Cw(1, 1004, "Translate"),
                  command=self.on_go).pack(side="left", padx=4)
'''

NEW_GO = '''        tk.Button(bar, text=_Cw(1, 1004, "Translate"),
                  command=self.on_go).grid(row=0, column=5, sticky="e", padx=4)
'''

EDITS = [(OLD_OVERLAY, NEW_OVERLAY), (OLD_BAR, NEW_BAR), (OLD_GO, NEW_GO)]


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    for old, new in EDITS:
        count = text.count(old)
        if count != 1:
            print(f"anchor found {count} times (expected 1): {old[:70]!r}",
                  file=sys.stderr)
            return 2
        text = text.replace(old, new, 1)
    TARGET.write_text(text, encoding="utf-8")
    print(f"applied {len(EDITS)} edits to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
