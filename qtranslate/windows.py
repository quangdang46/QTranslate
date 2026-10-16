"""Phase 7's window classes — the `App` split, extracted one at a time.

Phase 7 asks for *"Split `App` into `MainWindow`, `OptionsDialog`,
`HistoryView`, `DictionaryView`, `TrayController`, `PopupHost`"*. This
module holds the extracted classes; `qtranslate/app.py` keeps a thin
delegating method for each so every existing suite still exercises the
same behavior through the same entry point.

**A split is a MOVE, not a rewrite.** The first attempt at `HistoryView`
below rewrote the window while "moving" it: it invented menu labels the
locale packs do not have, dropped the per-entry ``state=`` disabling,
changed the filter to search the translation as well as the source, and
turned `_sel_entry` into a different helper. All four tests went red —
which is the only reason it was caught. So every class in this module is a
**transcription** of the app.py body, with exactly three mechanical
substitutions and nothing else:

  ``self``        -> ``self.app``   (for the live App's attributes/methods)
  ``w``           -> ``self.win``   (the window is now an instance field)
  ``self.X``      -> ``self.app.X`` (same rule, spelled out)

Anything beyond that is a behavior change and belongs in its own commit.

**Why the shared state is passed in.** These windows all read and write
the same live objects:

* ``root``   -- the single `tk.Tk` (native has one main window; the rest
  are `Toplevel`s off it). A second `Tk()` would break the tray, the
  clipboard monitor and every `after()` loop.
* ``app``    -- the live `App` instance, for callbacks exactly as the old
  `self.` calls did.
* ``history``-- the live history list, shared **by reference**. Native's
  history window deletes and re-favourites the same entries the main
  window recorded, so a copy would silently desynchronize them.

No window is created on import (pinned by `tests/regress_windows.py`).
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# `_Cw`/`_W` (locale lookup), `_T` (menu strings) and `_COLORS` (theme)
# live in app.py, so they are re-exported rather than duplicated.
# `_place_aux`/`_save_placement` come from where they are DEFINED
# (placement.py) — importing them through app.py would be a
# `from X import <name>` that also hides them from a static import walk.
# app.py imports THIS module lazily (inside the method), so the cycle
# resolves at call time either way.
from qtranslate.app import (  # noqa: E402
    _COLORS, _Cw, _T, _W, speak,
)
from qtranslate.placement import place_aux as _place_aux  # noqa: E402


class HistoryView:
    """The History window (native DLG 164) — `App.open_history_window`.

    A filterable list of recorded translations with a favourites column
    and the per-plugin export dialog. The list is the SAME list object the
    main window appends to, so delete/favourite/clear are visible both
    ways.
    """

    def __init__(self, root, app, history):
        self.root = root
        self.app = app
        self.history = history
        self.win = None

    def open(self):
        """Build (or raise) the window."""
        if self.win is not None:
            try:
                self.win.lift()
                return self.win
            except Exception:
                self.win = None
        w = self.win = tk.Toplevel(self.root)
        w.title(_W(3, "History"))
        w.configure(bg=_COLORS["back"])
        _place_aux(w, "WindowHistoryPlacement", "500x280")
        # Favorites: 4th tuple slot (native strings 201/202 +
        # Application.HistoryFilterFavorites filter toggle).
        tv = ttk.Treeview(w, columns=("fav", "svc"),
                          show="tree headings", height=12)
        tv.heading("#0", text="Translation")
        tv.heading("fav", text="★")
        tv.heading("svc", text="Service")
        tv.column("fav", width=30, stretch=False)
        # Application.HistoryFilter: native substring filter on the history
        # list. An Entry persists it back to Options.json.
        _ff = tk.Frame(w, bg=_COLORS["back"])
        _ff.pack(fill="x", padx=8)
        tk.Label(_ff, text=_Cw(3, 1162, "Filter:"), bg=_COLORS["back"],
                 fg=_COLORS["text"]).pack(side="left")
        _flt = tk.Entry(_ff, width=30)
        _flt.pack(side="left", padx=4)
        try:
            from qtranslate import config as _CF
            _flt.insert(0, str(_CF.load().get(
                "Application", {}).get("HistoryFilter", "")))
        except Exception:
            pass

        def _save_filter(*_a):
            try:
                from qtranslate import config as _C2
                import json as _j2
                full = _C2.load()
                full.setdefault("Application", {})[
                    "HistoryFilter"] = _flt.get()
                with open(_C2.DEFAULT_PATH, "w",
                          encoding="utf-8") as fh:
                    _j2.dump(full, fh, ensure_ascii=False, indent=1)
            except Exception:
                pass
        _flt.bind("<KeyRelease>", lambda e: (_save_filter(), _paint()))
        tv.pack(fill="both", expand=True, padx=8, pady=8)

        def _paint():
            for i in tv.get_children():
                tv.delete(i)
            try:
                from qtranslate import config as _C
                _ac = _C.load().get("Application", {})
                _fav_only = bool(_ac.get("HistoryFilterFavorites", False))
                _text = str(_ac.get("HistoryFilter", "")).lower()
                # General.ExpandHistoryItems: show the translation inline
                # as a child row instead of requiring a selection/click.
                _expand = bool(_C.load().get(
                    "General", {}).get("ExpandHistoryItems", False))
            except Exception:
                _fav_only, _text, _expand = False, "", False
            for idx, item in enumerate(self.history):
                svc, src = item[0], item[1]
                res = item[2] if len(item) > 2 else ""
                fav = len(item) > 3 and item[3]
                if _fav_only and not fav:
                    continue
                if _text and _text not in src.lower():
                    continue
                tv.insert("", "end", iid=str(idx),
                          text=src[:70],
                          values=("★" if fav else "", svc))
                if _expand and res:
                    tv.insert(str(idx), "end", iid=f"{idx}-tr",
                              text="→ " + res[:120], values=("", ""))
            if _expand:
                for i in list(tv.get_children()):
                    tv.item(i, open=True)

        _paint()

        def load_sel(_e=None):
            try:
                sel = tv.selection()[0]
                idx = int(sel)
                _, src, res = self.history[idx][:3]
                self.app.src.delete("1.0", "end")
                self.app.src.insert("1.0", src)
                self.app.render(res)
            except Exception:
                pass

        tv.bind("<Double-1>", load_sel)

        def _sel_entry():
            try:
                idx = int(tv.selection()[0])
                return idx, self.history[idx]
            except Exception:
                return None, None

        def _hist_menu(_e=None):
            # Native history-item menu I6 (FUN_004287B6, builder FUN_00404055
            # LoadMenuW): Open 0x8028, Copy text 0x806E, Copy translation
            # 0x8026, Delete 0x8027, Listen 0x8099. Each handler below is
            # the same operation the window already performs elsewhere
            # (load_sel / clipboard / history-list splice / speak thread),
            # so no new semantics are invented — only the menu entry point.
            idx, _ent = _sel_entry()
            m = tk.Menu(w, tearoff=False)
            m.add_command(
                label=_T("Menus", 10, "Open", menu=3),
                command=load_sel, state="normal" if _ent else "disabled")
            m.add_command(
                label=_T("Menus", 30, "Copy text", menu=3),
                command=lambda: (_pcopy(_ent[1]) if _ent else None),
                state="normal" if _ent else "disabled")
            m.add_command(
                label=_T("Menus", 20, "Copy translation", menu=3),
                command=lambda: (_pcopy(_ent[2]) if _ent else None),
                state="normal" if _ent else "disabled")
            m.add_command(
                label=_T("Menus", 50, "Delete", menu=3),
                command=lambda: (_hdel(idx) if _ent else None),
                state="normal" if _ent else "disabled")
            m.add_command(
                label=_T("Menus", 40, "Listen to text", menu=3),
                command=lambda: (_hear(_ent[1]) if _ent else None),
                state="normal" if _ent else "disabled")
            try:
                m.tk_popup(w.winfo_pointerx(), w.winfo_pointery())
            finally:
                m.grab_release()

        def _pcopy(_t):
            try:
                import pyperclip as _pc
                _pc.copy((_t or "").strip())
            except Exception:
                pass

        def _hdel(_i):
            try:
                del self.history[_i]
                self.app._save_history()
                _paint()
            except Exception:
                pass

        def _hear(_t):
            try:
                _, _, _tgt, _ = self.app.current()
                import threading as _th
                _th.Thread(target=speak, args=((_t or "")[:500], _tgt),
                           daemon=True).start()
            except Exception:
                pass

        tv.bind("<Button-3>", _hist_menu)

        def toggle_fav():
            # Strings 201/202: Add/Remove favorites
            try:
                sel = tv.selection()[0]
                idx = int(sel)
                svc, src, res = self.history[idx][:3]
                fav = not (len(self.history[idx]) > 3
                           and self.history[idx][3])
                self.history[idx] = (svc, src, res, fav)
                _paint()
                tv.selection_set(str(idx))
            except Exception:
                pass

        def clear():
            self.history.clear()
            for i in tv.get_children():
                tv.delete(i)

        frm = tk.Frame(w, bg=_COLORS["back"])
        frm.pack(pady=(0, 8))
        tk.Button(frm, text=_T("Strings", 201, "Favorite"),
                  command=toggle_fav).pack(side="left", padx=4)
        tk.Button(frm, text=_Cw(3, 1067, "Clear"),
                  command=clear).pack(side="left", padx=4)
        tk.Button(frm, text=_Cw(3, 1160, "Save as..."),
                  command=self.app.on_export_history).pack(side="left",
                                                           padx=4)
        return w


# The remaining Phase 7 classes are extracted in follow-up slices. Each is
# added here and wired to a delegator in app.py in the same change, so the
# split is never half-landed:
#   OptionsDialog  <- App.open_options
#   DictionaryView <- App.open_dict_window
#   TrayController <- _make_tray
#   PopupHost      <- show_popup
