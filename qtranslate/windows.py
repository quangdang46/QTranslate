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
    LANG_DISPLAY, _COLORS, _Cw, _T, _W, _safe_destroy, speak,
)
from qtranslate.placement import (  # noqa: E402
    place_aux as _place_aux,
    save_placement as _save_placement,
)


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
class DictionaryView:
    """The Dictionary window (native DLG 184) -- `App.open_dict_window`.

    Search bar + services pane (left, toggleable via
    `Dictionary.ShowServicesPane`) + XDXF-rendered article view + zoom
    (`DictionaryZoom`) + exact search (`DictionaryExactSearch`) + per-word
    history (`DictionaryHistory.json`).

    Transcribed from `App.open_dict_window` with the ONE substitution the
    Phase 7 split allows: ``self.`` -> ``self.app.``. The window variable is
    deliberately **kept as `w`**: this body also uses the literal ``"w"``
    as a file mode and as ``anchor="w"``, so a regex that renames `w` would
    have to be told to skip those -- and a rename capable of corrupting an
    ``open(path, "w")`` is not worth the tidiness. `self.win` is set once as
    an alias, purely so `open()` can be idempotent.

    tests/regress_windows.py compares this body against the pre-split commit
    and fails on any difference beyond that substitution.
    """

    def __init__(self, root, app):
        self.root = root
        self.app = app
        self.win = None

    def open(self):
        """Build (or raise) the window."""
        if self.win is not None:
            try:
                self.win.lift()
                return self.win
            except Exception:
                self.win = None
        # Native Dictionary window: search bar + services pane (left,
        # toggleable via Dictionary.ShowServicesPane) + article view
        # (XDXF-rendered HTML like dict_render) + zoom
        # (DictionaryZoom) + exact search (DictionaryExactSearch) +
        # per-word history (DictionaryHistory.json).
        from qtranslate import config as _C
        try:
            _dcfg = _C.load().get("Dictionary", {})
            _dorder = _C.load().get("DictionariesOrder",
                                    [10, 19, 20, 14, 17, 18, 22, 24, 25,
                                     26, 29])
            # DisabledDictionaries: globally disabled dicts must not
            # appear at all (was previously shown and queried regardless).
            _ddis = set(_C.load().get("DisabledDictionaries", []))
            _dorder = [sid for sid in _dorder if sid not in _ddis]
        except Exception:
            _dcfg, _dorder = {}, [10, 19, 20, 14, 17, 18, 22, 24, 25,
                                  26, 29]
        try:
            _disp = _C.DICT_DISPLAY
        except Exception:
            _disp = {}
        _zoom = _dcfg.get("DictionaryZoom", -1)
        _font = max(6, 11 + (0 if _zoom in (-1, None) else int(_zoom)))
        self.win = w = tk.Toplevel(self.app.root)
        w.title(_W(5, "Dictionary"))
        w.configure(bg=_COLORS["back"])
        _place_aux(w, "WindowDictionaryPlacement", "640x460")
        frm = tk.Frame(w, bg=_COLORS["back"])
        frm.pack(fill="x", padx=8, pady=8)
        tk.Label(frm, text="Word:", bg=_COLORS["back"],
                 fg="gray").pack(side="left")
        ent = tk.Entry(frm, width=28)
        ent.pack(side="left", padx=4)
        ent.bind("<Return>", lambda e: go_all())
        _exact_v = tk.BooleanVar(
            value=bool(_dcfg.get("DictionaryExactSearch", True)))

        def _save_exact(*_a):
            # Persist DictionaryExactSearch like the native loader/saver
            # (options +0x181); the flag gates the XDXF match breadth.
            try:
                full = _C.load()
                full.setdefault("Dictionary", {})[
                    "DictionaryExactSearch"] = bool(_exact_v.get())
                import json as _j2
                with open(_C.DEFAULT_PATH, "w",
                          encoding="utf-8") as fh:
                    _j2.dump(full, fh, ensure_ascii=False, indent=1)
            except Exception:
                pass

        tk.Checkbutton(frm, text="Exact", variable=_exact_v,
                       command=_save_exact,
                       bg=_COLORS["back"], fg=_COLORS["text"],
                       selectcolor=_COLORS["back"]).pack(side="left")
        tk.Button(frm, text="Look up",
                  command=lambda: go_all()).pack(side="left", padx=4)
        mid = tk.Frame(w, bg=_COLORS["back"])
        mid.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        pane = tk.Frame(mid, bg=_COLORS["back"])
        if _dcfg.get("ShowServicesPane", True):
            pane.pack(side="left", fill="y", padx=(0, 6))
            tk.Label(pane, text="Dictionaries", bg=_COLORS["back"],
                     fg=_COLORS["text"],
                     font=("Segoe UI", 9, "bold")).pack(anchor="w")
            _dlb = tk.Listbox(pane, height=18, width=22,
                              selectmode="multiple", bg="white", fg="black")
            _dlb.pack(fill="y", expand=True)
            try:
                _active_d = set(_C.load().get("General", {}).get(
                    "ActiveDictionaryServices", _dorder))
            except Exception:
                _active_d = set(_dorder)
            for i, sid in enumerate(_dorder):
                _dlb.insert("end", _disp.get(sid, f"id:{sid}"))
                if sid in _active_d:
                    _dlb.selection_set(i)
        else:
            _dlb = None
        out = tk.Text(mid, wrap="word", bg="white", fg="black",
                      insertbackground="black", font=("Tahoma", _font))
        out.pack(side="left", fill="both", expand=True)

        def _sel_ids():
            if _dlb is None:
                return list(_dorder)
            sel = _dlb.curselection()
            ids = [_dorder[i] for i in sel if i < len(_dorder)]
            out_ids = ids or list(_dorder)
            # persist ActiveDictionaryServices (native remembers)
            try:
                from qtranslate import config as C3
                import json as _j
                full = C3.load()
                full.setdefault("General", {})[
                    "ActiveDictionaryServices"] = out_ids
                with open(C3.DEFAULT_PATH, "w",
                          encoding="utf-8") as f:
                    _j.dump(full, f, ensure_ascii=False, indent=1)
            except Exception:
                pass
            return out_ids

        _ID2FN = {"googlesearch": "google-search", "wikipedia": "wikipedia",
                  "multitran": "multitran", "imtranslator": "imtranslator",
                  "wordreference": "wordreference", "babylon": "babylon",
                  "reverso": "reverso", "urban": "urban",
                  "lingvo": "lingvo", "youdao": "youdao",
                  "oxford": "oxford"}

        def go_all():
            word = ent.get().strip()[:500]
            if not word:
                return
            # DictionaryExactSearch (native options +0x181): exact is the
            # default; when off, match is broadened to substring. Only the
            # exact-vs-broader distinction is evidence-backed (consumer
            # FUN_004151c3); the precise native index algorithm is INFERRED.
            word_q = word
            exact = bool(_exact_v.get())
            sids = _sel_ids()
            out.delete("1.0", "end")
            out.insert("1.0", f"querying {len(sids)} dictionaries...")
            try:
                import json as _j
                import os as _o
                _hp = _o.path.join(_o.path.dirname(
                    _C.DEFAULT_PATH), "DictionaryHistory.json")
                try:
                    _h = _j.load(open(_hp, encoding="utf-8"))
                except Exception:
                    _h = []
                if word not in _h:
                    _h.insert(0, word)
                    open(_hp, "w", encoding="utf-8").write(
                        _j.dumps(_h[:200], ensure_ascii=False))
            except Exception:
                pass

            def work():
                from qtranslate import dict_render as DR
                cards = []
                # Offline XDXF first (native OfflineDictionaries list;
                # empty on this machine, but honored when configured).
                try:
                    from qtranslate import xdxf as _X
                    _off = _C.load().get("OfflineDictionaries", []) or []
                    for _xp in _off:
                        try:
                            _frag = _X.lookup(word_q, _xp, exact=exact)
                            if _frag:
                                cards.append(("xdxf", _xp.split(
                                    "/")[-1].split("\\")[-1],
                                    _frag[:8000]))
                        except Exception:
                            pass
                except Exception:
                    pass
                # Native dict-task builder (FUN_00414f54): param_1[4]
                # (target) is overwritten with DAT_005493f4
                # (General.LanguageDictionary, default 17 = "en") when == 1
                # (auto). The dict calls use that resolved code, not the
                # hardcoded "en" that used to sit here. Evidence:
                # docs/review/DICT_LANG_BUILDER_2026-10-15.md.
                try:
                    import qtranslate.services.google_translate as _G
                    _ld = _C.load().get("General", {}).get(
                        "LanguageDictionary", 17)
                    _dsl = _G.SUPPORTED_LANGS[_ld] \
                        if 0 <= _ld < len(_G.SUPPORTED_LANGS) else "en"
                    if _dsl in (-1, "auto"):
                        _dsl = "en"
                except Exception:
                    _dsl = "en"
                for sid in sids:
                    key = {_v: _k for _k, _v in _disp.items()
                           }.get(_disp.get(sid, ""), "")
                    fn = DICTS.get(
                        _ID2FN.get(
                            _disp.get(sid, "").lower().split()[0], ""))
                    if fn is None:
                        continue
                    try:
                        frag = fn(word_q, _dsl, self.app.target)
                        if frag:
                            cards.append((str(sid), _disp.get(sid, str(
                                sid)), frag[:8000]))
                    except Exception:
                        pass
                page = DR.render_cards(cards, word_q)
                try:
                    open("dict_last.html", "w",
                         encoding="utf-8").write(page)
                except Exception:
                    pass
                summary = "\n\n".join(
                    f"===== {t} =====\n" + _strip_html(f)[:800]
                    for _, t, f in cards)

                def _show():
                    out.delete("1.0", "end")
                    out.insert("1.0", summary or "[empty]")
                    self.app.tag_links(
                        out, summary,
                        lambda e: self.app._click_link_dict(out, e))

                self.app.root.after(0, _show)
            threading.Thread(target=work, daemon=True).start()

        def _zoom_by(d):
            try:
                size = int(str(out.cget("font")).split()[-1])
            except Exception:
                size = _font
            out.config(font=("Tahoma", max(6, size + d)))

        zb = tk.Frame(w, bg=_COLORS["back"])
        zb.pack(fill="x", padx=8, pady=(0, 8))
        tk.Button(zb, text="A-",
                  command=lambda: _zoom_by(-1)).pack(side="left")
        tk.Button(zb, text="A+",
                  command=lambda: _zoom_by(1)).pack(side="left", padx=4)

        def _manage_offline():
            # DLG 173: offline XDXF dictionary manager
            # (Add dictionary... / Remove dictionary).
            mw = tk.Toplevel(w)
            mw.title("Offline dictionaries")
            mw.configure(bg=_COLORS["back"])
            mw.geometry("420x280")
            lb = tk.Listbox(mw, bg="white", fg="black")
            lb.pack(fill="both", expand=True, padx=8, pady=8)

            def _load():
                lb.delete(0, "end")
                try:
                    _items = _C.load().get("OfflineDictionaries",
                                           []) or []
                except Exception:
                    _items = []
                for p in _items:
                    lb.insert("end", p)
                return _items

            _items = _load()

            def _save(items):
                try:
                    from qtranslate import config as C3
                    import json as _j
                    full = C3.load()
                    full["OfflineDictionaries"] = items
                    with open(C3.DEFAULT_PATH, "w",
                              encoding="utf-8") as f:
                        _j.dump(full, f, ensure_ascii=False, indent=1)
                except Exception:
                    pass

            def _add():
                p = filedialog.askopenfilename(
                    title="Add dictionary...",
                    filetypes=[("XDXF dictionaries", "*.xdxf"),
                               ("All files", "*.*")])
                if not p:
                    return
                _items = _load()
                if p not in _items:
                    _items.append(p)
                    _save(_items)
                    _load()

            def _remove():
                s = lb.curselection()
                if not s:
                    return
                _items = _load()
                _items.pop(s[0])
                _save(_items)
                _load()

            fr = tk.Frame(mw, bg=_COLORS["back"])
            fr.pack(pady=(0, 8))
            tk.Button(fr, text="Add dictionary...",
                      command=_add).pack(side="left", padx=4)
            tk.Button(fr, text="Remove dictionary",
                      command=_remove).pack(side="left", padx=4)

        tk.Button(zb, text="Dictionaries...",
                  command=_manage_offline).pack(side="left", padx=8)
        return self.win



class TrayController:
    """The system-tray icon and its menu -- the port's `_make_tray`.

    Native `FUN_00418B69` picks the icon index from the mouse-capture arm
    state (`FUN_00418DA0`), NOT from the HotKeys list; the icon colours
    (199 gray / 0x84 blue / 0x8A orange) come from the image. The port
    draws its own single-letter Q glyphs because the native icon resources
    are not extractable cleanly.

    Transcribed from `_make_tray(root, app)` -- a plain module function, so
    there are no `self.` renames at all. Two changes only: it became a
    method, and the icon is also kept on ``self.icon`` so `sync()` can be
    reached without rebuilding it. The original docstring is folded into
    `build()`'s. tests/regress_windows.py compares this body against the
    pre-split commit and fails on any other difference.
    """

    def __init__(self, root, app):
        self.root = root
        self.app = app
        self.icon = None

    def build(self):
        """Build the native-like tray icon + menu, or None if pystray/PIL
        is missing. Icon = QTranslate.exe main icon; menu mirrors the
        native tray menu (mouse modes + windows + Options/Exit)."""
        if self.icon is not None:
            return self.icon
        """Build the native-like tray icon + menu, or None if pystray/PIL
        is missing. Icon = QTranslate.exe main icon; menu mirrors the
        native tray menu (mouse modes + windows + Options/Exit)."""
        try:
            import pystray
            from PIL import Image
            from pystray import Menu, MenuItem
        except ImportError:
            return None
        def _tray_icon(color):
            # Native tray states (FUN_00418B69): 199=off(gray),
            # 0x84=on(blue), 0x8A=partial(orange). Single-letter Q glyph
            # on the state color (exe icons not extractable cleanly).
            from PIL import ImageDraw
            img = Image.new("RGBA", (16, 16), color + (255,))
            try:
                ImageDraw.Draw(img).text((3, 0), "Q", fill=(255, 255, 255,
                                                            255))
            except Exception:
                pass
            return img

        _COLORS_TRAY = {"off": (128, 128, 128), "on": (30, 144, 255),
                        "partial": (255, 140, 0)}
        try:
            _imgs = {k: _tray_icon(v) for k, v in _COLORS_TRAY.items()}
            _img = _imgs["off"]
        except Exception:
            return None

        _mouse_mode = [False]

        def _sync_icon(icon):
            # Native rule (FUN_00418DA0 -> FUN_00418B69), now via tray_state:
            #   param_2==0 -> 199 (off/gray)
            #   param_2==1 -> 0x84 (on/blue)      flag set, hook unavailable
            #   param_2==2 -> 0x8A (partial/orange) flag set, hook available
            # The flag is the MOUSE-CAPTURE arm state, and the "hook available"
            # bit is whether the Win32 low-level mouse hook actually installed
            # (mouse_capture.start) -- NOT the HotKeys list. The previous
            # inlined mapping (hotkeys-bound -> on) was a port-side guess;
            # `tray_state.select_state` had the real rule but nothing called it.
            try:
                from qtranslate import tray_state as _TS
                _idx = _TS.select_state(_mouse_mode[0], bool(_MOUSE_HOOK["on"]))
                _name = _TS.state_name(_idx)
            except Exception:
                _name = "off"
            try:
                icon.icon = _imgs.get(_name, _imgs["off"])
                icon.title = ("QTranslate (mouse mode: %s)"
                              % ("on" if _mouse_mode[0] else "off"))
            except Exception:
                pass

        def _show():
            try:
                root.after(0, lambda: (root.deiconify(), root.lift(),
                                       root.focus_force()))
            except Exception:
                pass

        def _toggle(icon, item):
            # SwitchMouseModeOnTrayClick gates whether tray click flips
            # the clipboard monitor (native Advanced flag).
            try:
                from qtranslate import config as _C
                _allowed = bool(_C.load().get("Advanced", {}).get(
                    "SwitchMouseModeOnTrayClick", True))
            except Exception:
                _allowed = True
            if not _allowed:
                return
            _mouse_mode[0] = not _mouse_mode[0]
            try:
                from qtranslate import app as _A
                if _mouse_mode[0]:
                    _A._set_mouse_hook(app, True)
                    if _A._MOUSE_MON["active"] is None:
                        _A._MOUSE_MON["active"] = \
                            _A.start_clipboard_monitor(app, popup=True)
                else:
                    _A._set_mouse_hook(app, False)
                    if _A._MOUSE_MON["active"] is not None:
                        _A._MOUSE_MON["active"][0] = False
                        _A._MOUSE_MON["active"] = None
            except Exception:
                pass
            try:
                icon.title = ("QTranslate (mouse mode: %s)"
                              % ("on" if _mouse_mode[0] else "off"))
            except Exception:
                pass
            _sync_icon(icon)

        def _open(win):
            return lambda icon, item: root.after(0, win)

        def _quit(icon, item):
            try:
                icon.stop()
            finally:
                root.after(0, root.destroy)

        _hotkeys_on = [True]
        _mouse_mode_val = ["Show icon"]

        def _toggle_hotkeys(icon, item):
            # Menu item -> General.EnableHotKeys, so the hotkey gates honour it
            try:
                from qtranslate import config as _C
                import json as _j
                full = _C.load()
                full.setdefault("General", {})["EnableHotKeys"] = \
                    not full.get("General", {}).get("EnableHotKeys", True)
                _hotkeys_on[0] = bool(full["General"]["EnableHotKeys"])
                with open(_C.DEFAULT_PATH, "w", encoding="utf-8") as f:
                    _j.dump(full, f, ensure_ascii=False, indent=1)
            except Exception:
                _hotkeys_on[0] = not _hotkeys_on[0]
            _sync_icon(icon)

        def _set_mouse_mode(icon, item):
            # Radio group: "Show icon" = off, anything else = armed
            _mouse_mode_val[0] = item.text
            _want = item.text != "Show icon"
            if _want != _mouse_mode[0]:
                _toggle(icon, None)
            _sync_icon(icon)

        # Native tray menu order (user-verified screenshot 2126, spec §5):
        #   QTranslate (bold heading) / Dictionary / Text recognition /
        #   History / Keyboard / Options / About QTranslate -- sep --
        #   Enable global hotkeys (checkable) / Mouse mode (submenu) -- sep --
        #   Exit.
        # pystray renders this as the real taskbar right-click menu, so the
        # menu is NOT self-drawn (the spec's hard rule 5).
        _mouse_modes = ("Show icon", "Translate in popup window",
                        "Translate in main window")
        menu = Menu(
            MenuItem("Show main window", _open(app.root.lift),
                     default=True),
            MenuItem("Dictionary", _open(app.open_dict_window)),
            MenuItem("Text recognition", _open(app.on_ocr)),
            MenuItem("History", _open(app.open_history_window)),
            MenuItem("Keyboard", _open(app.open_keyboard)),
            MenuItem("Options...", _open(app.open_options)),
            MenuItem("About QTranslate", _open(app.show_about)),
            Menu.SEPARATOR,
            MenuItem("Enable global hotkeys", _toggle_hotkeys,
                     checked=lambda item: _hotkeys_on[0]),
            MenuItem("Mouse mode", Menu(
                *[MenuItem(m, _set_mouse_mode,
                           radio=lambda item, _m=m: _mouse_mode_val[0] == _m)
                  for m in _mouse_modes])),
            Menu.SEPARATOR,
            MenuItem("Exit", _quit))
        self.icon = icon = pystray.Icon("QTranslate", _img, "QTranslate",
                            menu)
        try:
            icon.on_activate = lambda i: _show()  # double-click
        except Exception:
            pass
        _sync_icon(icon)
        return icon



class PopupHost:
    """The borderless topmost popup window -- the port's `show_popup`.

    Mirrors native's `FUN_0040C393` render path: `SetWindowTextW(title)` ->
    `WM_SETICON`(service icon) -> RichEdit child content ->
    EM_EXLIMITTEXT-style config -> second control text -> auto-resize
    (`FUN_0044B4F4`) -> `SetWindowPos(HWND_TOPMOST, SWP_NOMOVE|NOSIZE|SHOWWINDOW)`.

    Transcribed from the module function `show_popup(source, result,
    service="google", target="vi", src_lang="auto")` with NO `self.`
    renames -- it took no `self` to begin with, every dependency already
    arrived as an argument or (`_MAIN_APP`, `_COLORS`, ...) a module global.
    The only change is that it became a `@staticmethod`, keeping the exact
    same signature so `app.py`'s three call sites and the module-level
    `show_popup` forwarder are untouched.
    """

    @staticmethod
    def open(source, result, service="google", target="vi",
            src_lang="auto"):
        """Popup window — mirrors FUN_0040c393 render path.

        Native order: SetWindowTextW(title) -> WM_SETICON(service icon) ->
        RichEdit child content -> EM_EXLIMITTEXT-style config -> second
        control text -> auto-resize (FUN_0044B4F4) ->
        SetWindowPos(HWND_TOPMOST, SWP_NOMOVE|NOSIZE|SHOWWINDOW).
        """
        # Native popup (WindowPopup/TopmostWindow): borderless topmost text
        # window, themed by Themes/*.json. No buttons — header double-click
        # opens the main window; Esc closes.
        win = tk.Toplevel()
        win.title(f"{service.title()} - QTranslate")
        win.attributes("-topmost", True)
        win.overrideredirect(True)
        try:
            from qtranslate.theme import active_theme, tk_colors, window_colors
            from qtranslate import config as _C
            _tn = _C.load().get("Appearance", {}).get("ThemeName", "")
            # FUN_0044b44f: a ThemeName that names no file on disk leaves the
            # loader empty, and the *installer* then substitutes
            # theme::DefaultColorTheme — the GetSysColor palette, never another
            # file. `_tn or "Flat Dark"` did the one thing native never does, and
            # its FileNotFoundError was swallowed by the `except` below, so a stale
            # ThemeName silently produced _COLORS while reading as success.
            _pc = tk_colors(window_colors(active_theme(_tn)))
        except Exception:
            _pc = _COLORS
        win.configure(bg=_pc.get("border", "#7a7a7a"))
        # Appearance.PopupWindowFrameThickness: border width in px (native 0..8).
        try:
            from qtranslate import config as _CFW
            _fw = max(0, min(8, int(_CFW.load().get("Appearance", {}).get(
                "PopupWindowFrameThickness", 2))))
        except Exception:
            _fw = 1
        inner = tk.Frame(win, bg=_pc.get("back", "#f0f0f0"))
        inner.pack(fill="both", expand=True, padx=max(1, _fw), pady=max(1, _fw))
        # Header line = the native popup CAPTION (FUN_0040C393:
        # SetWindowTextW(hwnd+4, [+0x3c])). Shipped order (user-verified
        # screenshots): "<Source> to <Target>…", a favourite star, then the
        # PopupIcons glyph row. `win.title()` sets the OS title, which is
        # invisible in an overrideredirect window -- so this Label IS the header.
        _hdr_src = LANG_DISPLAY.get(src_lang or "auto", "Auto-Detect")
        _hdr_tgt = LANG_DISPLAY.get(target, target)
        _hdr = tk.Frame(inner, bg=_pc.get("back", "#f0f0f0"))
        _hdr.pack(fill="x", padx=4, pady=(3, 0))
        tk.Label(_hdr, text="%s to %s…" % (_hdr_src, _hdr_tgt),
                 bg=_pc.get("back", "#f0f0f0"),
                 fg=_pc.get("text", "#000000")).pack(side="left")
        tk.Label(_hdr, text="★", bg=_pc.get("back", "#f0f0f0"),
                 fg=_pc.get("text", "#000000")).pack(side="left", padx=(2, 0))
        try:
            from qtranslate import config as _CPH
            _icons_h = int(_CPH.load().get("Appearance", {}).get(
                "PopupIcons", 30))
        except Exception:
            _icons_h = 30
        if _icons_h:
            _bar = tk.Frame(_hdr, bg=_pc.get("back", "#f0f0f0"))
            _bar.pack(side="left", padx=(2, 0))
            if _icons_h & 2:
                tk.Label(_bar, text="\U0001F4D6",
                         bg=_pc.get("back", "#f0f0f0")).pack(side="left", padx=1)
            if _icons_h & 4:
                tk.Label(_bar, text="\U0001F50A",
                         bg=_pc.get("back", "#f0f0f0")).pack(side="left", padx=1)
            if _icons_h & 8:
                tk.Label(_bar, text="\U0001F4CB",
                         bg=_pc.get("back", "#f0f0f0")).pack(side="left", padx=1)
            if _icons_h & 16:
                tk.Label(_bar, text="↻",
                         bg=_pc.get("back", "#f0f0f0")).pack(side="left", padx=1)
        txt = tk.Text(inner, wrap="word",
                      bg=_pc.get("back", "#f0f0f0"),
                      fg=_pc.get("text", "#000000"),
                      insertbackground=_pc.get("text", "#000000"),
                      font=("Segoe UI", 11), borderwidth=0,
                      highlightthickness=0)
        lines = max(2, min(12, result.count("\n") + len(result) // 60 + 1))
        txt.config(height=lines, width=60)
        txt.pack(fill="both", expand=True, padx=6, pady=6)
        txt.insert("1.0", result)
        txt.config(state="disabled")

        # (The icon glyph row lives in the header Labels above -- the old copy
        # of this block that rendered below the text was removed 2026-10-14 when
        # the header moved up, matching the native title-glyph order.)

        def _to_main(_e=None):
            # Native: double-clicking the popup header shows the EXISTING main
            # window with the current text. (Previously this created a second
            # tk.Tk(), which corrupted Tk state.)
            _close_popup()
            try:
                from qtranslate.app import _MAIN_APP
                a = _MAIN_APP
                if a is not None:
                    a.root.deiconify()
                    a.root.lift()
                    a.root.focus_force()
                    a.src.delete("1.0", "end")
                    a.src.insert("1.0", source)
                    a.render(result)
            except Exception:
                pass

        txt.bind("<Double-1>", _to_main)
        def _close_popup(_e=None):
            try:
                from qtranslate import config as _CAP
                if not _CAP.load().get("Appearance", {}).get(
                        "PopupAutoPos", True):
                    _save_placement("WindowPopupPlacement", win)
            except Exception:
                pass
            _safe_destroy(win)

        win.bind("<Escape>", _close_popup)

        # --- Appearance popup settings (native ShowPopupWindow) --------------
        try:
            from qtranslate import config as _CA
            _ap = _CA.load().get("Appearance", {})
        except Exception:
            _ap = {}
        # PopupAutoFocus: steal focus only when enabled (default False)
        if _ap.get("PopupAutoFocus"):
            try:
                win.attributes("-topmost", True)
                win.focus_force()
            except Exception:
                pass
        # Transparency 0..255 -> window alpha (only when < 255).
        # Native default 217 (DAT_005494A4, NATIVE_ARCH.md:1200; also
        # DEFAULT_APPEARANCE in config.py) — not 255.
        try:
            _tr = int(_ap.get("Transparency", 217))
            if 0 < _tr < 255:
                win.attributes("-alpha", _tr / 255.0)
        except Exception:
            pass
        # PopupAutoPos: place near the pointer. When off, restore the
        # remembered geometry (General.WindowPopupPlacement, previously
        # unused) like the other aux windows.
        if _ap.get("PopupAutoPos", True):
            try:
                px, py = win.winfo_pointerx(), win.winfo_pointery()
                win.geometry(f"+{px + 12}+{py + 12}")
            except Exception:
                pass
        else:
            try:
                win.update_idletasks()
                _place_aux(win, "WindowPopupPlacement",
                          f"{win.winfo_width()}x{win.winfo_height()}")
            except Exception:
                pass
        # PopupTimeout (seconds): auto-close; 0/absent = stay
        try:
            _to = int(_ap.get("PopupTimeout", 0))
            if _to > 0:
                win.after(_to * 1000, lambda: _safe_destroy(win))
        except Exception:
            pass

#   OptionsDialog  <- App.open_options
