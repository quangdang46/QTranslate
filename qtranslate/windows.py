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



class OptionsDialog:
    """The Options window (native DLG 154 + pages) -- `App.open_options`.

    Thirteen pages (Basics/Appearance/Hotkeys/Services/Languages/Internet/
    Exceptions/Advanced/Updates), each a closure the original method
    defined. Transcribed from `App.open_options` with the one substitution
    the Phase 7 split allows: ``self.`` -> ``self.app.``. The window
    variable is kept as `w` -- this body uses the literal ``"w"`` as a file
    mode (a dozen ``open(path, "w")`` calls) and as ``anchor="w"``, so
    renaming it is not worth the risk of corrupting one of those.
    `self.win` is set once as an alias so `open()` can be idempotent.

    tests/regress_windows.py compares this body against the pre-split
    commit and fails on any difference beyond that one substitution.
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
                try:
                    from qtranslate import config as C
                    cfg = C.load()
                except Exception:
                    cfg = {}
                self.win = w = tk.Toplevel(self.app.root)
                w.title(_W(2, "Options"))
                w.configure(bg=_COLORS["back"])
                _place_aux(w, "WindowOptionsPlacement", "560x420")
                left = tk.Listbox(w, width=14, height=20, bg=_COLORS["back"],
                                  fg=_COLORS["text"])
                left.pack(side="left", fill="y", padx=8, pady=8)
                # Page order = Windows Ids 10-18 (Basics/Internet/Services/
                # Languages/Appearance/Exceptions/Hotkeys/Advanced/Updates);
                # labels localized via _W. _PAGE_IDS maps listbox index.
                _PAGES = [("Basics", 10), ("Internet", 11), ("Services", 12),
                          ("Languages", 13), ("Appearance", 14),
                          ("Exceptions", 15), ("Hotkeys", 16), ("Advanced", 17),
                          ("Updates", 18)]
                pages = [p for p, _ in _PAGES]
                _PAGE_IDS = {p: i for i, (p, _) in enumerate(_PAGES)}
                for p, wid in _PAGES:
                    left.insert("end", _W(wid, p))
                body = tk.Frame(w, bg=_COLORS["back"])
                body.pack(side="left", fill="both", expand=True, padx=8, pady=8)

                def show_basics():
                    # Defaults from the real Options.json (General/AutoDetection):
                    # startup reg present, FontName='' (-> --- Default ---),
                    # TextSize=9, AutoDetection 57/17/57 (vi/en/vi),
                    # EnableHistory + ClearHistoryOnExit true, Expand false.
                    import os as _os
                    for c in body.winfo_children():
                        c.destroy()
                    try:
                        from qtranslate import config as _C
                        _cfg = _C.load()
                        _gen = _cfg.get("General", {})
                        _ad = _cfg.get("AutoDetection", {})
                    except Exception:
                        _gen, _ad = {}, {}
                    tk.Label(body, text=_Cw(10, 1046, "General"), bg=_COLORS["back"],
                             fg=_COLORS["text"],
                             font=("Segoe UI", 10, "bold")).pack(anchor="w")
                    self.app._opt_vars = getattr(self, "_opt_vars", {})
                    # Start-with-Windows via startup_entry (Win HKCU Run; honest
                    # no-op off-Windows). Same key/value as before the refactor.
                    _startup, _set_startup = startup_entry()
                    _sv = tk.BooleanVar(value=_startup)
                    self.app._opt_vars["startup"] = _sv  # keep ref: no GC-uncheck

                    def _toggle_startup():
                        _set_startup(bool(_sv.get()))

                    tk.Checkbutton(body, text=_Cw(10, 1045, "Start with Windows"),
                                   variable=_sv, command=_toggle_startup,
                                   bg=_COLORS["back"], fg=_COLORS["text"],
                                   selectcolor=_COLORS["back"]).pack(anchor="w")
                    try:
                        _langs = sorted(
                            d for d in _os.listdir(
                                "C:/Program Files (x86)/QTranslate/Locales")
                            if _os.path.isdir(
                                _os.path.join(
                                    "C:/Program Files (x86)/QTranslate/Locales",
                                    d)))
                    except Exception:
                        _langs = ["English"]
                    _cur_lang = _gen.get("LocaleFoderName") or "English"
                    if _cur_lang not in _langs:
                        _cur_lang = "English"
                    for lab, vals, default, key in (
                            (_Cw(10, 1070, "Interface language:"), _langs,
                             _cur_lang, "LocaleFoderName"),
                            (_Cw(10, 1075, "Font name:"), ["--- Default ---"],
                             "--- Default ---", "FontName"),
                            (_Cw(10, 1074, "Text size:"), ["9"],
                             str(_gen.get("TextSize", 9)), "TextSize")):
                        r = tk.Frame(body, bg=_COLORS["back"])
                        r.pack(fill="x", pady=1)
                        tk.Label(r, text=lab, width=18, anchor="w",
                                 bg=_COLORS["back"],
                                 fg=_COLORS["text"]).pack(side="left")
                        cb = ttk.Combobox(r, values=vals, width=26,
                                          state="readonly")
                        cb.pack(side="left")
                        cb.set(default)

                        def _save_general(k=key, w=cb):
                            try:
                                from qtranslate import config as _CSG
                                import json as _jsg
                                full = _CSG.load()
                                _val = w.get()
                                if k == "TextSize":
                                    try:
                                        _val = int(_val)
                                    except Exception:
                                        return
                                full.setdefault("General", {})[k] = _val
                                with open(_CSG.DEFAULT_PATH, "w",
                                          encoding="utf-8") as fh:
                                    _jsg.dump(full, fh, ensure_ascii=False,
                                              indent=1)
                                _gen[k] = _val
                            except Exception:
                                pass
                        cb.bind("<<ComboboxSelected>>", lambda e: _save_general())
                    tk.Label(body, text=_Cw(10, 1063, "Auto-detect languages"),
                             bg=_COLORS["back"], fg=_COLORS["text"],
                             font=("Segoe UI", 10, "bold")).pack(anchor="w",
                                                                 pady=(8, 0))
                    _IDX2NAME = {57: "Vietnamese", 17: "English"}
                    for lab, key in ((_Cw(10, 1068, "First language:"), "LanguageFirst"),
                                     (_Cw(10, 1069, "Second language:"), "LanguageSecond"),
                                     (_Cw(10, 1071, "Speech input:"),
                                      "LanguageSpeechRecognition")):
                        r = tk.Frame(body, bg=_COLORS["back"])
                        r.pack(fill="x", pady=1)
                        tk.Label(r, text=lab, width=18, anchor="w",
                                 bg=_COLORS["back"],
                                 fg=_COLORS["text"]).pack(side="left")
                        cb = ttk.Combobox(r, values=TO_LANG_NAMES, width=26,
                                          state="readonly")
                        cb.pack(side="left")
                        cb.set(_IDX2NAME.get(_ad.get(key, 17), "English"))

                        def _save_autodetect(k=key, w=cb):
                            # AutoDetection.LanguageFirst/Second/
                            # LanguageSpeechRecognition (SUPPORTED_LANGS indices).
                            try:
                                from qtranslate import config as _CSA
                                import json as _jsa
                                full = _CSA.load()
                                _tbl = list(__import__(
                                    "qtranslate.services.google_translate",
                                    fromlist=["SUPPORTED_LANGS"]).SUPPORTED_LANGS)
                                try:
                                    _idx = _tbl.index(
                                        LANG_CODES.get(w.get(), w.get()))
                                except ValueError:
                                    _idx = 17
                                full.setdefault("AutoDetection", {})[k] = _idx
                                with open(_CSA.DEFAULT_PATH, "w",
                                          encoding="utf-8") as fh:
                                    _jsa.dump(full, fh, ensure_ascii=False,
                                              indent=1)
                                _ad[k] = _idx
                            except Exception:
                                pass
                        cb.bind("<<ComboboxSelected>>", lambda e: _save_autodetect())
                    tk.Label(body, text=_Cw(10, 1064, "History"), bg=_COLORS["back"],
                             fg=_COLORS["text"],
                             font=("Segoe UI", 10, "bold")).pack(anchor="w",
                                                                 pady=(8, 0))
                    def _save_history_flag(key, var):
                        try:
                            from qtranslate import config as _CH
                            import json as _jh
                            full = _CH.load()
                            full.setdefault("General", {})[key] = bool(var.get())
                            with open(_CH.DEFAULT_PATH, "w",
                                      encoding="utf-8") as fh:
                                _jh.dump(full, fh, ensure_ascii=False, indent=1)
                            _gen[key] = bool(var.get())
                        except Exception:
                            pass

                    for lab, key, default in (
                            (_Cw(10, 1122, "Enable history"), "EnableHistory",
                             _gen.get("EnableHistory", True)),
                            (_Cw(10, 1124, "Clear history on exit"),
                             "ClearHistoryOnExit",
                             _gen.get("ClearHistoryOnExit", True)),
                            (_Cw(10, 1123, "Expand items"), "ExpandHistoryItems",
                             _gen.get("ExpandHistoryItems", False))):
                        v = tk.BooleanVar(value=bool(default))
                        self.app._opt_vars[lab] = v  # keep ref: no GC-uncheck
                        tk.Checkbutton(
                            body, text=lab, variable=v, bg=_COLORS["back"],
                            fg=_COLORS["text"], selectcolor=_COLORS["back"],
                            command=lambda k=key, vv=v: _save_history_flag(
                                k, vv)).pack(anchor="w")

                def show_appearance():
                    # mirrors DLG 175; all values live from the real
                    # Options.json Appearance section (verified keys).
                    for c in body.winfo_children():
                        c.destroy()
                    _ap = cfg.get("Appearance", {})
                    self.app._opt_vars = getattr(self, "_opt_vars", {})
                    tk.Label(body, text="General", bg=_COLORS["back"],
                             fg=_COLORS["text"],
                             font=("Segoe UI", 10, "bold")).pack(anchor="w")
                    r = tk.Frame(body, bg=_COLORS["back"])
                    r.pack(fill="x", pady=1)
                    tk.Label(r, text=_Cw(14, 1169, "Theme:"), width=18, anchor="w",
                             bg=_COLORS["back"],
                             fg=_COLORS["text"]).pack(side="left")
                    th = ttk.Combobox(r, values=_THEMES, width=26,
                                      state="readonly")
                    th.pack(side="left")
                    _cur_th = _ap.get("ThemeName") or THEME
                    th.set(_cur_th if _cur_th in _THEMES else
                           (_THEMES[0] if _THEMES else ""))
                    th.bind("<<ComboboxSelected>>",
                            lambda e: self.app.apply_theme(th.get()))
                    def _save_appearance_flag(key, var):
                        try:
                            from qtranslate import config as _CAF
                            import json as _jaf
                            full = _CAF.load()
                            full.setdefault("Appearance", {})[key] = bool(
                                var.get())
                            with open(_CAF.DEFAULT_PATH, "w",
                                      encoding="utf-8") as fh:
                                _jaf.dump(full, fh, ensure_ascii=False, indent=1)
                            _ap[key] = bool(var.get())
                        except Exception:
                            pass

                    for lab, key in ((_Cw(14, 1158, "Enable auto size"), "PopupAutoSize"),
                                     (_Cw(14, 1160, "Enable auto position"), "PopupAutoPos"),
                                     (_Cw(14, 1159, "Always activate"), "PopupAutoFocus"),
                                     (_Cw(14, 1161, "Pin when dragging"),
                                      "PopupPinWhenDragging"),
                                     (_Cw(14, 1123, "Enable window style"),
                                      "EnableWindowStyle")):
                        vv = tk.BooleanVar(value=bool(_ap.get(key, False)))
                        self.app._opt_vars[key] = vv
                        tk.Checkbutton(
                            body, text=lab, variable=vv, bg=_COLORS["back"],
                            fg=_COLORS["text"], selectcolor=_COLORS["back"],
                            command=lambda k=key, v=vv: _save_appearance_flag(
                                k, v)).pack(anchor="w")
                    tk.Label(body, text="Popup window", bg=_COLORS["back"],
                             fg=_COLORS["text"],
                             font=("Segoe UI", 10, "bold")).pack(anchor="w",
                                                                 pady=(8, 0))
                    for lab, key in ((_Cw(14, 1147, "Auto-hide delay (s):"), "PopupTimeout"),
                                     (_Cw(14, 1145, "Transparency (0-255):"), "Transparency"),
                                     (_Cw(14, 1146, "Frame thickness:"), "PopupWindowFrameThickness")):
                        rr = tk.Frame(body, bg=_COLORS["back"])
                        rr.pack(fill="x", pady=1)
                        tk.Label(rr, text=lab, width=20, anchor="w",
                                 bg=_COLORS["back"],
                                 fg=_COLORS["text"]).pack(side="left")
                        ee = tk.Entry(rr, width=10)
                        ee.pack(side="left")
                        ee.insert(0, str(_ap.get(key, "")))
                        self.app._opt_vars[key] = ee
                    # PopupIcons bitmask (native checkboxes 1138-1141):
                    # 2=dict, 4=listen-text, 8=copy, 16=replace (30 = all)
                    tk.Label(body, text=_Cw(14, 1137, "Popup icons:"),
                             bg=_COLORS["back"], fg=_COLORS["text"],
                             font=("Segoe UI", 9, "bold")).pack(anchor="w",
                                                                pady=(6, 0))

                    def _save_icons():
                        try:
                            from qtranslate import config as C3
                            import json as _j
                            full = C3.load()
                            full.setdefault("Appearance", {})["PopupIcons"] = \
                                _ap.get("PopupIcons", 30)
                            with open(C3.DEFAULT_PATH, "w",
                                      encoding="utf-8") as f:
                                _j.dump(full, f, ensure_ascii=False, indent=1)
                        except Exception:
                            pass

                    for lab, bit in ((_Cw(14, 1138, "Show dictionary icon"), 2),
                                     (_Cw(14, 1139, "Show listen icon"), 4),
                                     (_Cw(14, 1140, "Show copy icon"), 8),
                                     (_Cw(14, 1141, "Show replace icon"), 16)):
                        vv = tk.BooleanVar(value=bool(
                            int(_ap.get("PopupIcons", 30)) & bit))
                        self.app._opt_vars[f"PopupIcons_{bit}"] = vv

                        def _flip(b=bit, v=vv):
                            try:
                                cur = int(_ap.get("PopupIcons", 30))
                                _ap["PopupIcons"] = (cur | b) if v.get() \
                                    else (cur & ~b)
                            except Exception:
                                pass
                            _save_icons()

                        tk.Checkbutton(body, text=lab, variable=vv,
                                       bg=_COLORS["back"], fg=_COLORS["text"],
                                       selectcolor=_COLORS["back"],
                                       command=_flip).pack(anchor="w")
                    for lab, key in ((_Cw(14, 1092, "Background color:"), "ColorBack"),
                                     (_Cw(14, 1091, "Text color:"), "ColorText"),
                                     (_Cw(14, 1090, "Frame color:"), "ColorFrame")):
                        rr = tk.Frame(body, bg=_COLORS["back"])
                        rr.pack(fill="x", pady=1)
                        tk.Label(rr, text=lab, width=20, anchor="w",
                                 bg=_COLORS["back"],
                                 fg=_COLORS["text"]).pack(side="left")
                        ee = tk.Entry(rr, width=10)
                        ee.pack(side="left")
                        ee.insert(0, "#%06x" % int(_ap.get(key, 0)))
                        self.app._opt_vars[key] = ee

                def show_hotkeys():
                    # mirrors DLG 179: Enable hot keys + per-action list with
                    # current bindings decoded via FUN_00403B48 port; Change
                    # captures a new combo, Clear unbinds (writes Options.json).
                    for c in body.winfo_children():
                        c.destroy()
                    try:
                        from qtranslate import config as C
                        hk = cfg.get("HotKeys", {})
                        names = C.HOTKEY_NAMES
                    except Exception:
                        hk, names = {}, []
                    self.app._opt_vars = getattr(self, "_opt_vars", {})
                    v = tk.BooleanVar(value=bool(hk.get("EnableHotKeys", True)))
                    self.app._opt_vars["EnableHotKeys"] = v

                    def _toggle_enable_hotkeys():
                        try:
                            from qtranslate import config as _CEK
                            import json as _jek
                            full = _CEK.load()
                            full.setdefault("HotKeys", {})["EnableHotKeys"] = \
                                bool(v.get())
                            with open(_CEK.DEFAULT_PATH, "w",
                                      encoding="utf-8") as fh:
                                _jek.dump(full, fh, ensure_ascii=False, indent=1)
                            hk["EnableHotKeys"] = bool(v.get())
                        except Exception:
                            pass

                    tk.Checkbutton(body, text=_Cw(16, 1118, "Enable hot keys"),
                                   variable=v, command=_toggle_enable_hotkeys,
                                   bg=_COLORS["back"], fg=_COLORS["text"],
                                   selectcolor=_COLORS["back"]).pack(anchor="w")
                    tv = ttk.Treeview(body, columns=("Hotkey",),
                                      show="tree headings", height=13)
                    tv.heading("#0", text=_T("Strings", 0, "Action"))
                    tv.heading("Hotkey", text=_T("Strings", 1, "Hotkey"))
                    tv.column("#0", width=260)
                    tv.column("Hotkey", width=140)
                    tv.pack(fill="both", expand=True, pady=4)
                    try:
                        _fmt = C.format_hotkey
                    except Exception:
                        _fmt = lambda code: str(code)  # noqa: E731
                    # Action display names: Windows Id 16 control 1165 list
                    # (order matches HOTKEY_NAMES); fallback = key name.
                    try:
                        _acts = None
                        for _w in _pack().get("Windows", []):
                            if isinstance(_w, dict) and _w.get("Id") == 16:
                                for _c in _w.get("Controls", []):
                                    if isinstance(_c, (list, tuple)) \
                                            and _c[0] == 1165:
                                        _acts = [t for _, t in _c[1]]
                        _act_map = dict(zip(names, _acts)) \
                            if _acts and len(_acts) == len(names) else {}
                    except Exception:
                        _act_map = {}
                    for n in names:
                        code = hk.get(n, 0) or 0
                        tv.insert("", "end", iid=n,
                                  text=_act_map.get(n, n),
                                  values=(_fmt(code) or "(none)",))

                    def _save_hotkey(name, code):
                        try:
                            from qtranslate import config as C2
                            full = C2.load()
                            full.setdefault("HotKeys", {})[name] = code
                            with open(C2.DEFAULT_PATH, "w",
                                      encoding="utf-8") as f:
                                import json as _j
                                _j.dump(full, f, ensure_ascii=False, indent=1)
                            cfg.get("HotKeys", {})[name] = code
                        except Exception:
                            pass

                    def _change():
                        sel = tv.selection()
                        if not sel:
                            return
                        name = sel[0]
                        cap = tk.Toplevel(w)
                        cap.title("Press hotkey")
                        cap.geometry("280x90")
                        tk.Label(cap,
                                 text=f"Press a key combo for\n{name} "
                                      "(Esc = cancel)").pack(pady=8)

                        def _key(e):
                            if e.keysym == "Escape":
                                cap.destroy()
                                return "break"
                            mods = 0
                            # Tk state bits: Shift=0x1, Control=0x4,
                            # Alt/Mod1=0x8, Win/Mod4=0x40. Native mod bits
                            # (FUN_00405A17): 1=Alt, 2=Ctrl, 4=Shift, 8=Win.
                            if e.state & 0x1:
                                mods |= 4
                            if e.state & 0x4:
                                mods |= 2
                            if e.state & 0x8:
                                mods |= 1
                            if e.state & 0x40:
                                mods |= 8
                            try:
                                # keysym for letters (layout-independent like
                                # MapVirtualKeyW); fall back to keycode.
                                _ks = (e.keysym or "")
                                if len(_ks) == 1:
                                    vk = ord(_ks.upper()) & 0xFF
                                else:
                                    vk = e.keycode & 0xFF
                            except Exception:
                                vk = 0
                            code = (vk | (mods << 8)) or 0
                            _save_hotkey(name, code)
                            try:
                                tv.set(name, "Hotkey", _fmt(code) or "(none)")
                            except Exception:
                                pass
                            cap.destroy()
                            return "break"

                        cap.bind("<Key>", _key)
                        cap.focus_force()
                        cap.grab_set()

                    def _clear():
                        sel = tv.selection()
                        if not sel:
                            return
                        _save_hotkey(sel[0], 0)
                        try:
                            tv.set(sel[0], "Hotkey", "(none)")
                        except Exception:
                            pass

                    frm = tk.Frame(body, bg=_COLORS["back"])
                    frm.pack(pady=(0, 2))
                    tk.Button(frm, text="Change...",
                              command=_change).pack(side="left", padx=4)
                    tk.Button(frm, text="Clear",
                              command=_clear).pack(side="left", padx=4)

                def show_services():
                    # Translate services (ServicesOrder + DisabledServices) and
                    # dictionary services (DictionariesOrder +
                    # DisabledDictionaries); check = enabled, writes Options.json.
                    for c in body.winfo_children():
                        c.destroy()
                    try:
                        from qtranslate import config as C2
                        _order = list(cfg.get("ServicesOrder", []))
                        _dis = set(cfg.get("DisabledServices", []))
                        _dorder = list(cfg.get("DictionariesOrder", []))
                        _ddis = set(cfg.get("DisabledDictionaries", []))
                        _names = dict(C2.SERVICE_NAMES)
                    except Exception:
                        _order, _dis, _dorder, _ddis, _names = [], set(), [], \
                            set(), {}
                    # Display names for the service/dict lists (config-owned
                    # constants; the dead ``dictionary as _D`` import that sat here
                    # is gone — nothing in this page called it).
                    _dnames = {}
                    try:
                        _dnames = dict(C2.DICT_DISPLAY)
                        _names = dict(C2.SERVICE_DISPLAY)
                    except Exception:
                        pass

                    def _save():
                        try:
                            from qtranslate import config as C3
                            import json as _j
                            full = C3.load()
                            full["ServicesOrder"] = _order
                            full["DisabledServices"] = sorted(_dis)
                            full["DictionariesOrder"] = _dorder
                            full["DisabledDictionaries"] = sorted(_ddis)
                            with open(C3.DEFAULT_PATH, "w",
                                      encoding="utf-8") as f:
                                _j.dump(full, f, ensure_ascii=False, indent=1)
                            cfg["ServicesOrder"] = _order
                            cfg["DisabledServices"] = sorted(_dis)
                            cfg["DictionariesOrder"] = _dorder
                            cfg["DisabledDictionaries"] = sorted(_ddis)
                        except Exception:
                            pass

                    def _mk_list(parent, title, order, disabled, names):
                        tk.Label(parent, text=title, bg=_COLORS["back"],
                                 fg=_COLORS["text"],
                                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
                        fr = tk.Frame(parent, bg=_COLORS["back"])
                        fr.pack(fill="both", expand=True)
                        lb = tk.Listbox(fr, height=6, selectmode="single",
                                        bg="white", fg="black")
                        lb.pack(side="left", fill="both", expand=True)
                        for i in order:
                            lb.insert("end", names.get(i, f"id:{i}"))
                        sb = tk.Frame(fr, bg=_COLORS["back"])
                        sb.pack(side="left", padx=2)

                        def _refresh():
                            lb.delete(0, "end")
                            for i in order:
                                lb.insert("end", names.get(i, f"id:{i}"))
                            _save()

                        def _move(d):
                            s = lb.curselection()
                            if not s:
                                return
                            i = s[0]
                            j = i + d
                            if 0 <= j < len(order):
                                order[i], order[j] = order[j], order[i]
                                _refresh()
                                lb.selection_set(j)

                        def _toggle():
                            s = lb.curselection()
                            if not s:
                                return
                            sid = order[s[0]]
                            if sid in disabled:
                                disabled.discard(sid)
                            else:
                                disabled.add(sid)
                            _save()
                            _paint()

                        def _paint():
                            for idx, sid in enumerate(order):
                                lb.itemconfig(
                                    idx, fg="gray" if sid in disabled else "black")
                        _paint()

                        def _check_all():
                            # DLG 174 "Check / Uncheck all": enable all if any
                            # disabled, else disable all.
                            if any(s in disabled for s in order):
                                disabled.clear()
                            else:
                                disabled.update(order)
                            _save()
                            _paint()

                        tk.Button(sb, text="▲", width=3,
                                  command=lambda: _move(-1)).pack(pady=1)
                        tk.Button(sb, text="▼", width=3,
                                  command=lambda: _move(1)).pack(pady=1)
                        tk.Button(sb, text="On/Off", width=5,
                                  command=_toggle).pack(pady=1)
                        tk.Button(sb, text="All", width=5,
                                  command=_check_all).pack(pady=1)
                        return lb

                    _mk_list(body, "Translation services", _order, _dis, _names)
                    _mk_list(body, "Dictionary services", _dorder, _ddis, _dnames)

                def show_languages():
                    # Index <-> code via Google SupportedLanguages (canonical
                    # table: 1=auto, 17=en, 57=vi). Pairs + per-slot defaults +
                    # disabled list + detect flags; writes Options.json/General.
                    for c in body.winfo_children():
                        c.destroy()
                    try:
                        # Canonical language-index table (constant, not dispatch).
                        from qtranslate.services.google_translate import (
                            SUPPORTED_LANGS as _SL)
                        # SUPPORTED_LANGS[0] is -1 placeholder; native table
                        # is indexed with it (1=auto, 17=en, 57=vi)
                        _table = list(_SL)
                    except Exception:
                        _table = [-1, "auto", "en", "vi"]
                    _names_l = [("auto (auto-detect)" if c == "auto" else c)
                                for c in _table]
                    _gen = cfg.get("General", {})
                    _dis_l = set(cfg.get("DisabledLanguages", []))
                    _pairs = [list(p) for p in cfg.get("LanguagePairs",
                                                       [[57, 17], [17, 57]])]
                    self.app._opt_vars = getattr(self, "_opt_vars", {})

                    def _save_l():
                        try:
                            from qtranslate import config as C3
                            import json as _j
                            full = C3.load()
                            full["LanguagePairs"] = _pairs
                            full["DisabledLanguages"] = sorted(_dis_l)
                            full["General"].update(_gen)
                            with open(C3.DEFAULT_PATH, "w",
                                      encoding="utf-8") as f:
                                _j.dump(full, f, ensure_ascii=False, indent=1)
                            cfg["LanguagePairs"] = _pairs
                            cfg["DisabledLanguages"] = sorted(_dis_l)
                            cfg["General"].update(_gen)
                        except Exception:
                            pass

                    def _idx_combo(parent, lab, idx):
                        r = tk.Frame(parent, bg=_COLORS["back"])
                        r.pack(fill="x", pady=1)
                        tk.Label(r, text=lab, width=18, anchor="w",
                                 bg=_COLORS["back"],
                                 fg=_COLORS["text"]).pack(side="left")
                        cb = ttk.Combobox(r, values=_names_l, width=26,
                                          state="readonly")
                        cb.pack(side="left")
                        try:
                            cb.set(_names_l[idx])
                        except Exception:
                            pass
                        return cb

                    tk.Label(body, text="Default languages",
                             bg=_COLORS["back"], fg=_COLORS["text"],
                             font=("Segoe UI", 10, "bold")).pack(anchor="w")
                    _cb = {}
                    # Per-key native defaults (real Options.json: From=1/auto,
                    # To=57/vi, Dictionary=17/en, Keyboard=17/en). A single
                    # default for all four showed `en` for an unset From on
                    # first run instead of `auto`.
                    _defs = {"LanguageFrom": 1, "LanguageTo": 57,
                             "LanguageDictionary": 17, "LanguageKeyboard": 17}
                    for lab, key in (("Translate from:", "LanguageFrom"),
                                     ("Translate to:", "LanguageTo"),
                                     ("Dictionary:", "LanguageDictionary"),
                                     ("Virtual keyboard:", "LanguageKeyboard")):
                        _cb[key] = _idx_combo(body, lab,
                                              _gen.get(key, _defs[key]) or 0)
                        _cb[key].bind("<<ComboboxSelected>>",
                                      lambda e, k=key: (
                                          _gen.__setitem__(
                                              k, _names_l.index(_cb[k].get())),
                                          _save_l()))
                    for lab, key in (("Always detect language",
                                      "AlwaysDetectLanguage"),
                                     ("Smart detection", "UseSmartDetection")):
                        vv = tk.BooleanVar(value=bool(_gen.get(key, False)))
                        self.app._opt_vars[key] = vv
                        tk.Checkbutton(
                            body, text=lab, variable=vv, bg=_COLORS["back"],
                            fg=_COLORS["text"], selectcolor=_COLORS["back"],
                            command=lambda k=key: (
                                _gen.__setitem__(k, self.app._opt_vars[k].get()),
                                _save_l())).pack(anchor="w")
                    tk.Label(body, text="Language pairs", bg=_COLORS["back"],
                             fg=_COLORS["text"],
                             font=("Segoe UI", 10, "bold")).pack(anchor="w",
                                                                 pady=(8, 0))
                    _plb = tk.Listbox(body, height=4, bg="white", fg="black")
                    _plb.pack(fill="x", pady=2)

                    def _paint_pairs():
                        _plb.delete(0, "end")
                        for a, b in _pairs:
                            try:
                                _plb.insert("end",
                                            f"{_table[a]} > {_table[b]}")
                            except Exception:
                                _plb.insert("end", f"{a} > {b}")

                    _paint_pairs()
                    _pr = tk.Frame(body, bg=_COLORS["back"])
                    _pr.pack(fill="x")

                    def _add_pair():
                        try:
                            a = _names_l.index(_cb["LanguageFrom"].get())
                            b = _names_l.index(_cb["LanguageTo"].get())
                        except Exception:
                            return
                        if [a, b] not in _pairs:
                            _pairs.append([a, b])
                            _paint_pairs()
                            _save_l()

                    def _del_pair():
                        s = _plb.curselection()
                        if not s:
                            return
                        _pairs.pop(s[0])
                        _paint_pairs()
                        _save_l()

                    def _move_pair(d):
                        # DLG 190 Up/Down for the pairs list
                        s = _plb.curselection()
                        if not s:
                            return
                        i, j = s[0], s[0] + d
                        if 0 <= j < len(_pairs):
                            _pairs[i], _pairs[j] = _pairs[j], _pairs[i]
                            _paint_pairs()
                            _plb.selection_set(j)
                            _save_l()

                    def _clear_pairs():
                        # DLG 190 Remove All
                        _pairs.clear()
                        _paint_pairs()
                        _save_l()

                    tk.Button(_pr, text="Add",
                              command=_add_pair).pack(side="left", padx=2)
                    tk.Button(_pr, text="Remove",
                              command=_del_pair).pack(side="left", padx=2)
                    tk.Button(_pr, text="Remove All",
                              command=_clear_pairs).pack(side="left", padx=2)
                    tk.Button(_pr, text="Up",
                              command=lambda: _move_pair(-1)).pack(side="left",
                                                                   padx=2)
                    tk.Button(_pr, text="Down",
                              command=lambda: _move_pair(1)).pack(side="left",
                                                                 padx=2)
                    tk.Label(body, text="Disabled languages",
                             bg=_COLORS["back"], fg=_COLORS["text"],
                             font=("Segoe UI", 10, "bold")).pack(anchor="w",
                                                                 pady=(8, 0))
                    _dlb = tk.Listbox(body, height=4, selectmode="multiple",
                                      bg="white", fg="black")
                    _dlb.pack(fill="x", pady=2)
                    for i, n in enumerate(_names_l):
                        _dlb.insert("end", n)
                        if i in _dis_l:
                            _dlb.selection_set(i)
                            _dlb.itemconfig(i, fg="gray")

                    def _save_dis():
                        _dis_l.clear()
                        _dis_l.update(_dlb.curselection())
                        _save_l()

                    tk.Button(body, text="Apply disabled",
                              command=_save_dis).pack(anchor="w", pady=2)

                def show_internet():
                    # Internet.Timeout (ms) + full Proxy section; live: the
                    # net stack (session._net_open) already honors these.
                    for c in body.winfo_children():
                        c.destroy()
                    _inet = cfg.get("Internet", {})
                    _px = cfg.get("Proxy", {})
                    self.app._opt_vars = getattr(self, "_opt_vars", {})

                    def _save_n():
                        try:
                            from qtranslate import config as C3
                            import json as _j
                            full = C3.load()
                            full["Internet"] = _inet
                            full["Proxy"] = _px
                            with open(C3.DEFAULT_PATH, "w",
                                      encoding="utf-8") as f:
                                _j.dump(full, f, ensure_ascii=False, indent=1)
                            cfg["Internet"] = _inet
                            cfg["Proxy"] = _px
                        except Exception:
                            pass

                    tk.Label(body, text=_Cw(11, 1049, "Connection"), bg=_COLORS["back"],
                             fg=_COLORS["text"],
                             font=("Segoe UI", 10, "bold")).pack(anchor="w")
                    r = tk.Frame(body, bg=_COLORS["back"])
                    r.pack(fill="x", pady=1)
                    # Native label shows seconds (1084) but Options.json
                    # stores ms (10000) — entry edits ms like the value.
                    tk.Label(r, text=_Cw(11, 1084, "Timeout (ms):"), width=18, anchor="w",
                             bg=_COLORS["back"],
                             fg=_COLORS["text"]).pack(side="left")
                    _te = tk.Entry(r, width=10)
                    _te.pack(side="left")
                    _te.insert(0, str(_inet.get("Timeout", 10000)))
                    _te.bind("<FocusOut>", lambda e: (
                        _inet.__setitem__("Timeout",
                                          int(_te.get() or 10000)), _save_n()))
                    tk.Label(body, text=_Cw(11, 1048, "Proxy"), bg=_COLORS["back"],
                             fg=_COLORS["text"],
                             font=("Segoe UI", 10, "bold")).pack(anchor="w",
                                                                 pady=(8, 0))
                    # Native ProxyType combo (W11/1135): system/no/manual/
                    # auto-detect; manual details below map Proxy.Host/Port
                    # (HTTP/SOCKS distinguished by Scheme in our stack).
                    _pt_vals = ["Use system proxy settings", "No proxy",
                                "Manual proxy configuration",
                                "Auto-detect proxy settings"]
                    _pt = ttk.Combobox(body, values=_pt_vals, width=26,
                                       state="readonly")
                    _pt.pack(anchor="w", pady=1)
                    try:
                        _pt.set(_pt_vals[int(_px.get("ProxyType", 0))])
                    except Exception:
                        _pt.set(_pt_vals[1])
                    _entries = {}
                    for lab, key in ((_Cw(11, 1034, "Host:"), "Host"), (_Cw(11, 1035, "Port:"), "Port"),
                                     (_Cw(11, 1036, "Username:"), "Username"),
                                     (_Cw(11, 1037, "Password:"), "Password")):
                        rr = tk.Frame(body, bg=_COLORS["back"])
                        rr.pack(fill="x", pady=1)
                        tk.Label(rr, text=lab, width=18, anchor="w",
                                 bg=_COLORS["back"],
                                 fg=_COLORS["text"]).pack(side="left")
                        ee = tk.Entry(rr, width=26,
                                      show="*" if key == "Password" else "")
                        ee.pack(side="left")
                        ee.insert(0, str(_px.get(key, "")))
                        _entries[key] = ee
                    _sch = ttk.Combobox(body, values=["http", "https"], width=26,
                                        state="readonly")
                    _sch.pack(anchor="w", pady=1)
                    _sch.set("https" if int(_px.get("Scheme", 0)) else "http")

                    def _apply_px():
                        _names = {_pt_vals[0]: 0, _pt_vals[1]: 1,
                                  _pt_vals[2]: 2, _pt_vals[3]: 3}
                        _px["ProxyType"] = _names.get(_pt.get(), 1)
                        _px["Scheme"] = 1 if _sch.get() == "https" else 0
                        for k, ee in _entries.items():
                            v = ee.get()
                            _px[k] = int(v) if k == "Port" and v.isdigit() \
                                else v
                        _save_n()

                    tk.Button(body, text="Apply",
                              command=_apply_px).pack(anchor="w", pady=4)

                def show_exceptions():
                    # Exceptions.Disabled/Enabled ([exe, class] pairs) +
                    # DisabledMode; live: exclusions.foreground_excluded honors it.
                    for c in body.winfo_children():
                        c.destroy()
                    _ex = cfg.get("Exceptions", {})
                    _dis_list = [list(p) for p in _ex.get("Disabled", [])]
                    _en_list = [list(p) for p in _ex.get("Enabled", [])]

                    def _save_x():
                        try:
                            from qtranslate import config as C3
                            import json as _j
                            full = C3.load()
                            full["Exceptions"] = {
                                "Disabled": _dis_list, "Enabled": _en_list,
                                "DisabledMode": _ex.get("DisabledMode", True)}
                            with open(C3.DEFAULT_PATH, "w",
                                      encoding="utf-8") as f:
                                _j.dump(full, f, ensure_ascii=False, indent=1)
                            cfg["Exceptions"] = full["Exceptions"]
                        except Exception:
                            pass

                    vv = tk.BooleanVar(value=bool(_ex.get("DisabledMode", True)))
                    tk.Checkbutton(body, text="Disable capture in listed windows "
                                              "(uncheck = enable only here)",
                                   variable=vv, bg=_COLORS["back"],
                                   fg=_COLORS["text"], selectcolor=_COLORS["back"],
                                   command=lambda: (
                                       _ex.__setitem__("DisabledMode", vv.get()),
                                       _save_x())).pack(anchor="w")

                    def _mk_xlist(parent, title, pairs):
                        tk.Label(parent, text=title, bg=_COLORS["back"],
                                 fg=_COLORS["text"],
                                 font=("Segoe UI", 10, "bold")).pack(anchor="w",
                                                                     pady=(6, 0))
                        lb = tk.Listbox(parent, height=5, bg="white", fg="black")
                        lb.pack(fill="x")
                        for exe, cls in pairs:
                            lb.insert("end", f"{exe or '*'}  |  {cls or '*'}")
                        fr = tk.Frame(parent, bg=_COLORS["back"])
                        fr.pack(fill="x", pady=2)
                        er = tk.Entry(fr, width=16)
                        er.pack(side="left", padx=1)
                        er.insert(0, "exe or empty")
                        cr = tk.Entry(fr, width=16)
                        cr.pack(side="left", padx=1)
                        cr.insert(0, "class or empty")

                        def _add():
                            exe = er.get().strip()
                            cls = cr.get().strip()
                            if exe == "exe or empty":
                                exe = ""
                            if cls == "class or empty":
                                cls = ""
                            pairs.append([exe, cls])
                            lb.insert("end", f"{exe or '*'}  |  {cls or '*'}")
                            _save_x()

                        def _dele():
                            s = lb.curselection()
                            if not s:
                                return
                            pairs.pop(s[0])
                            lb.delete(s[0])
                            _save_x()

                        def _modify():
                            # DLG 176 Modify: edit selected entry in place
                            s = lb.curselection()
                            if not s:
                                return
                            i = s[0]
                            exe = er.get().strip()
                            cls = cr.get().strip()
                            if exe in ("", "exe or empty"):
                                exe = pairs[i][0] if er.get().strip() in (
                                    "", "exe or empty") else ""
                            if cls in ("", "class or empty"):
                                cls = pairs[i][1] if cr.get().strip() in (
                                    "", "class or empty") else ""
                            pairs[i] = [exe, cls]
                            lb.delete(i)
                            lb.insert(i, f"{exe or '*'}  |  {cls or '*'}")
                            lb.selection_set(i)
                            _save_x()

                        tk.Button(fr, text=_Cw(15, 1101, "Add"),
                                  command=_add).pack(side="left", padx=2)
                        tk.Button(fr, text=_Cw(15, 1103, "Modify"),
                                  command=_modify).pack(side="left", padx=2)
                        tk.Button(fr, text=_Cw(15, 1102, "Remove"),
                                  command=_dele).pack(side="left", padx=2)

                    _mk_xlist(body, _Cw(15, 1162, "Blocked (Disabled)"), _dis_list)
                    _mk_xlist(body, _Cw(15, 1162, "Allowed (Enabled)"), _en_list)
                    # DLG 176 "Enable smart detection" (General.UseSmartDetection)
                    try:
                        _genx = cfg.get("General", {})
                    except Exception:
                        _genx = {}
                    _sv = tk.BooleanVar(
                        value=bool(_genx.get("UseSmartDetection", True)))
                    self.app._opt_vars = getattr(self, "_opt_vars", {})
                    self.app._opt_vars["UseSmartDetection_x"] = _sv

                    def _save_smart():
                        try:
                            from qtranslate import config as C3
                            import json as _j
                            full = C3.load()
                            full.setdefault("General", {})[
                                "UseSmartDetection"] = _sv.get()
                            with open(C3.DEFAULT_PATH, "w",
                                      encoding="utf-8") as f:
                                _j.dump(full, f, ensure_ascii=False, indent=1)
                            cfg.setdefault("General", {})[
                                "UseSmartDetection"] = _sv.get()
                        except Exception:
                            pass

                    tk.Checkbutton(body, text=_Cw(15, 1113, "Enable smart detection"),
                                   variable=_sv, bg=_COLORS["back"],
                                   fg=_COLORS["text"], selectcolor=_COLORS["back"],
                                   command=_save_smart).pack(anchor="w",
                                                             pady=(6, 0))

                def show_advanced():
                    # Full Advanced section, live where implemented.
                    for c in body.winfo_children():
                        c.destroy()
                    _ad2 = cfg.get("Advanced", {})
                    self.app._opt_vars = getattr(self, "_opt_vars", {})

                    def _save_a():
                        try:
                            from qtranslate import config as C3
                            import json as _j
                            full = C3.load()
                            full["Advanced"] = _ad2
                            with open(C3.DEFAULT_PATH, "w",
                                      encoding="utf-8") as f:
                                _j.dump(full, f, ensure_ascii=False, indent=1)
                            cfg["Advanced"] = _ad2
                        except Exception:
                            pass

                    for lab, key in (
                            (_Cw(17, 1159, "Slower (clearer) listening"),
                             "EnableSlowerListening"),
                            (_Cw(17, 1154, "GUI translation (XDXF hover)"),
                             "EnableGuiTranslation"),
                            (_Cw(17, 1155, "Mouse mode on Ctrl"),
                             "EnableMouseModeOnCtrl"),
                            (_Cw(17, 1160, "Remove line breaks"),
                             "RemoveLineBreaks"),
                            (_Cw(17, 1156, "Tray click toggles mouse mode"),
                             "SwitchMouseModeOnTrayClick")):
                        vv = tk.BooleanVar(value=bool(_ad2.get(key, False)))
                        self.app._opt_vars[key] = vv
                        tk.Checkbutton(
                            body, text=lab, variable=vv, bg=_COLORS["back"],
                            fg=_COLORS["text"], selectcolor=_COLORS["back"],
                            command=lambda k=key: (
                                _ad2.__setitem__(k, self.app._opt_vars[k].get()),
                                _save_a())).pack(anchor="w")
                    for lab, key in (
                            (_Cw(17, 1195, "OCR API key:"), "OcrApiKey"),
                            (_Cw(17, 1157, "Preferred domain:"),
                             "PreferredDomain"),
                            (_Cw(17, 1157, "Google domain:"), "GoogleDomain"),
                            (_Cw(17, 1151, "Default browser id:"),
                             "DefaultBrowserId"),
                            (_Cw(17, 1151, "Open links with:"),
                             "DefaultBrowserId"),
                            (_Cw(17, 1149, "Layout indicator:"),
                             "LayoutIndicator"),
                            (_Cw(17, 1149, "Keyboard layout indicator:"),
                             "LayoutIndicator"),
                            (_Cw(17, 1147, "Copy action:"), "CopyAction"),
                            (_Cw(17, 1186, "Mouse mode:"), "MouseMode")):
                        r = tk.Frame(body, bg=_COLORS["back"])
                        r.pack(fill="x", pady=1)
                        tk.Label(r, text=lab, width=22, anchor="w",
                                 bg=_COLORS["back"],
                                 fg=_COLORS["text"]).pack(side="left")
                        ee = tk.Entry(r, width=26)
                        ee.pack(side="left")
                        try:
                            _cur = _ad2.get(key, "")
                            if _cur is None:
                                _cur = ""
                        except Exception:
                            _cur = ""
                        ee.insert(0, str(_cur))
                        ee.bind("<FocusOut>", lambda e, k=key, w=ee: (
                            _ad2.__setitem__(k, w.get()), _save_a()))
                    # DLG 185 API-keys SysLink -> ocr.space key docs
                    _api = tk.Label(body, text="Get OCR API keys at ocr.space",
                                    fg="blue", cursor="hand2", bg=_COLORS["back"],
                                    font=("Segoe UI", 9, "underline"))
                    _api.pack(anchor="w", pady=4)
                    _api.bind("<Button-1>",
                              lambda e: _open_url("https://ocr.space/ocrapi"))

                def show_updates():
                    for c in body.winfo_children():
                        c.destroy()
                    _up = cfg.get("Update", {})

                    def _save_u():
                        try:
                            from qtranslate import config as C3
                            import json as _j
                            full = C3.load()
                            full["Update"] = _up
                            with open(C3.DEFAULT_PATH, "w",
                                      encoding="utf-8") as f:
                                _j.dump(full, f, ensure_ascii=False, indent=1)
                            cfg["Update"] = _up
                        except Exception:
                            pass

                    vv = tk.BooleanVar(value=bool(_up.get("CheckForUpdates",
                                                          False)))
                    tk.Checkbutton(body, text=_Cw(18, 1188,
                                                  "Check for updates on startup"),
                                   variable=vv, bg=_COLORS["back"],
                                   fg=_COLORS["text"], selectcolor=_COLORS["back"],
                                   command=lambda: (
                                       _up.__setitem__("CheckForUpdates",
                                                       vv.get()),
                                       _save_u())).pack(anchor="w")
                    def _check_now():
                        # Native R1/R2: GET the update manifest and parse it.
                        # The host retired in 2022 -> normally BLOCKED; parse the
                        # payload if one is ever served (uses updater.parse_manifest,
                        # FUN_00461ADE).
                        try:
                            import urllib.request as _ur
                            from qtranslate import updater as _UP
                            _u = ("https://quest-app.appspot.com/update?v=6.10.0")
                            _req = _ur.Request(_u, headers={"User-Agent": "QTranslate"})
                            with _ur.urlopen(_req, timeout=8) as _r:
                                _txt = _r.read().decode("utf-8", "replace")
                            _man = _UP.parse_manifest(_txt)
                            if _man.get("valid"):
                                self.app.render(
                                    "Update manifest: v{0} ({1})\n{2}".format(
                                        _man["version"], _man["date"],
                                        _man["changelog"]))
                            else:
                                self.app.render("update server returned no valid "
                                            "manifest (offline/retired).")
                        except Exception as _e:
                            self.app.render(
                                "update check BLOCKED: server unreachable "
                                f"(retired 2022) — {_e}")
                    tk.Button(body, text=_Cw(18, 1190, "Check now"),
                              command=_check_now).pack(anchor="w", pady=2)
                    tk.Label(body, text="QTranslate 6.10.0 — 'Check now' tries the "
                                        "native update manifest endpoint; it is "
                                        "retired, so the check reports BLOCKED.",
                             bg=_COLORS["back"], fg="gray", wraplength=380,
                             justify="left").pack(anchor="w", pady=6)

                def on_select(_e=None):
                    if not left.curselection():
                        return
                    # map back via index (labels are localized)
                    page = pages[left.curselection()[0]]
                    if page == "Basics":
                        show_basics()
                    elif page == "Appearance":
                        show_appearance()
                    elif page == "Hotkeys":
                        show_hotkeys()
                    elif page == "Services":
                        show_services()
                    elif page == "Languages":
                        show_languages()
                    elif page == "Internet":
                        show_internet()
                    elif page == "Exceptions":
                        show_exceptions()
                    elif page == "Advanced":
                        show_advanced()
                    elif page == "Updates":
                        show_updates()
                    else:
                        for c in body.winfo_children():
                            c.destroy()
                        tk.Label(body,
                                 text=page + " (see Options.json sections)",
                                 bg=_COLORS["back"],
                                 fg=_COLORS["text"]).pack(anchor="w")

                import copy as _copy
                _snapshot = _copy.deepcopy(cfg)

                def _cancel():
                    # Native Cancel discards: restore the snapshot since pages
                    # save live into cfg/Options.json as they edit.
                    try:
                        from qtranslate import config as _C
                        import json as _j
                        with open(_C.DEFAULT_PATH, "w",
                                  encoding="utf-8") as f:
                            _j.dump(_snapshot, f, ensure_ascii=False, indent=1)
                        cfg.clear()
                        cfg.update(_copy.deepcopy(_snapshot))
                    except Exception:
                        pass
                    w.destroy()

                def _save_page_index():
                    try:
                        from qtranslate import config as _C
                        import json as _j
                        full = _C.load()
                        sel = left.curselection()
                        full.setdefault("Application", {})[
                            "OptionsPageIndex"] = sel[0] if sel else 0
                        with open(_C.DEFAULT_PATH, "w",
                                  encoding="utf-8") as f:
                            _j.dump(full, f, ensure_ascii=False, indent=1)
                    except Exception:
                        pass

                _orig_select = on_select

                def on_select(_e=None):
                    _orig_select(_e)
                    _save_page_index()

                left.bind("<<ListboxSelect>>", on_select)
                try:
                    from qtranslate import config as _CI
                    _pi = int(_CI.load().get("Application", {}).get(
                        "OptionsPageIndex", 0))
                except Exception:
                    _pi = 0
                if 0 <= _pi < len(pages):
                    left.selection_set(_pi)
                    page = pages[_pi]
                    {"Basics": show_basics, "Appearance": show_appearance,
                     "Hotkeys": show_hotkeys, "Services": show_services,
                     "Languages": show_languages, "Internet": show_internet,
                     "Exceptions": show_exceptions, "Advanced": show_advanced,
                     "Updates": show_updates}.get(page, show_basics)()
                else:
                    left.selection_set(0)
                    show_basics()
                frm = tk.Frame(w, bg=_COLORS["back"])
                frm.pack(side="bottom", pady=(0, 8))
                tk.Button(frm, text="OK",
                          command=w.destroy).pack(side="left", padx=4)
                tk.Button(frm, text="Cancel",
                          command=_cancel).pack(side="left", padx=4)
                tk.Button(frm, text="Apply",
                          command=w.destroy).pack(side="left", padx=4)

