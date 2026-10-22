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

import threading
import tkinter as tk
from tkinter import filedialog, font as tkfont, ttk

# `pyperclip` is optional (app.py imports it the same way): it is only
# reachable under `_HAS_KEYS`, which is True only on Windows, where the
# import has already succeeded.
try:
    import pyperclip
except Exception:      # pragma: no cover - platform dependent
    pyperclip = None

# `_Cw`/`_W` (locale lookup), `_T` (menu strings) and `_COLORS` (theme)
# live in app.py, so they are re-exported rather than duplicated.
# `_place_aux`/`_save_placement` come from where they are DEFINED
# (placement.py) — importing them through app.py would be a
# `from X import <name>` that also hides them from a static import walk.
# app.py imports THIS module lazily (inside the method), so the cycle
# resolves at call time either way.
from qtranslate.app import (  # noqa: E402
    LANG_DISPLAY, _COLORS, _Cw, _T, _W, _safe_destroy, speak,
    startup_entry,
    SRC_LANG_NAMES, TO_LANG_NAMES,
    # MainWindow (Phase 7, 6/6) needs the main window's own vocabulary:
    # the language tables, the service tables, the pane font, the locale
    # lookup and the app-level helpers the moved bodies call.
    BACKTR_MARKER, DICTS, LANGS, LANG_CODES, LANG_DEFAULTS, SVC_ICON_PX,
    TO_LANGS,
    TRANSLATORS, _HAS_KEYS, _lang_names, _open_url, _pane_font,
    do_translate,
    # 2026-10-21: the Phase 7 (6/6) split moved the bodies but NOT the
    # names they read from app.py's module scope, so six of them raised
    # `NameError` at run time -- silently, because the call sites sit
    # under a bare `except Exception: pass`. The Appearance page died on
    # `_THEMES`, the hotkey page on `_pack()`, the dictionary card on
    # `_strip_html`, the mouse-mode tray on `_MOUSE_HOOK`, the service
    # page on `_dict_service_link` and the theme combo on `THEME`.
    # `_MOUSE_HOOK` is a dict that app.py mutates IN PLACE, so importing
    # the name (not copying it) keeps the two modules on one object.
    THEME, _MOUSE_HOOK, _THEMES, _dict_service_link, _pack, _strip_html,
)
from qtranslate.placement import (  # noqa: E402
    place_aux as _place_aux,
    save_placement as _save_placement,
    template_geometry as _TEMPLATE_GEOMETRY,
)
# Native's Languages-page checklist (DLG174), in native's order. The
# list lives in `qtranslate/config.py` -- the module that already owns
# the native option tables -- so there is ONE copy of it and the live
# Options window does not have to depend on `screens.py`, the
# standalone reference sheet.
from qtranslate.config import LANGUAGE_COLUMNS as _LANGUAGE_COLUMNS  # noqa: E402
# The dictionary-service icons, by service display name. Recovered from
# the installer payload and matched against native's own dictionary strip
# (docs/review/native_screens/2132.png) -- see
# qtranslate/assets/dict_icons/manifest.json.
_DICT_ICON_FILES = {
    "Google Search": "google-search", "WordReference": "wordreference",
    "Babylon Dictionary": "babylon", "Multitran": "multitran",
    "ImTranslator": "imtranslator", "Reverso": "reverso",
    "Urban Dictionary": "urban", "ABBYY Lingvo Live": "lingvo",
    "youdao": "youdao", "Oxford Learner Dictionary": "oxford",
    # Wikipedia has no `.ico` in the payload (19 services, 18 icons) and
    # none in the EXE's RT_ICON either; native draws a 16x16 white tile
    # with a black serif W, re-drawn from its own pixels by
    # `tools/_scratch/make_wikipedia_tile.py`.
    "Wikipedia": "wikipedia",
}

# The main window's SOURCE pane. Native's is DLG129's control 1000 --
# 66 DU tall -- and its capture (docs/review/native_screens/2131.png, a
# 516x423 window) measures it at 153px, showing TEN AND A HALF lines of
# the same help text the port renders.
#
# The LINE COUNT is the invariant that travels: the pixel height follows
# the font, and the font follows the display's scaling. A fixed 153px
# would show a different number of lines on a Windows machine at 150%
# scaling, where native's own pane is 66 DU again.
SRC_PANE_LINES = 10.5
SRC_PANE_PX = 153          # the reference measurement, at 125% scaling


def _src_pane_px():
    """The source pane's height in pixels, for the font in use."""
    try:
        pitch = max(1, tkfont.Font(font=_pane_font()).metrics("linespace"))
    except Exception:
        pitch = 14
    return int(round(SRC_PANE_LINES * pitch))


# The bundled native icons, cached per Tk INTERPRETER. A PhotoImage that
# goes out of scope is freed by Tk, and a button whose image was freed
# draws NOTHING -- an empty box.
#
# The cache belongs to the interpreter, not to the process, because a
# PhotoImage belongs to the interpreter that created it: Tk frees every
# image when that interpreter is destroyed, so an image cached for
# interpreter #1 is DEAD in interpreter #2. A process-global cache
# therefore handed the second window a freed image, and Tk raised
# `image "pyimage16" doesn't exist` while building it -- which is how a
# second App in one process (a test, or a relaunch that reuses the
# interpreter) failed to draw at all.
#
# The cache hangs off the interpreter's TOPLEVEL widget, so it is
# collected with the window it belongs to and can never outlive the
# images it holds.
def _bundle_icon(name, folder="ui_icons", master=None):
    """A bundled native icon (``qtranslate/assets/<folder>/``) or None.

    ``ui_icons`` holds the EXE's own RT_ICON groups (the microphone, the
    headphone, the nav arrows, the stars); ``service_icons`` holds the
    per-service logos recovered from the installer payload.

    ``master`` is the widget the image will be drawn on. It decides which
    interpreter the image belongs to, so it must be the same interpreter
    as the widget that will use the image.
    """
    if master is None:
        master = getattr(tk, "_default_root", None)
    if master is None:
        return None
    try:
        root = master.winfo_toplevel()
    except Exception:
        root = master
    cache = getattr(root, "_qt_icon_cache", None)
    if cache is None:
        cache = {}
        try:
            root._qt_icon_cache = cache
        except Exception:
            pass
    key = folder + "/" + name
    if key in cache:
        return cache[key]
    photo = None
    try:
        import os as _os
        _path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                              "assets", folder, name + ".png")
        if _os.path.exists(_path):
            photo = tk.PhotoImage(master=root, file=_path)
    except Exception:
        photo = None
    cache[key] = photo
    return photo


def _text_scrollbar(parent, text):
    """A text pane's scrollbar, shown only when the content overflows.

    Native's RichEdits grow a scrollbar when the content does not fit:
    the capture (2131) shows one on the main window's SOURCE pane --
    whose help text is clipped at the eleventh line -- and none on its
    RESULT pane, whose single line fits; the Dictionary window's result
    pane has one (the capture 2132 shows its up and down arrows at the
    right edge). A Tk scrollbar is always drawn, so it is gridded in and
    out to match, and the text's width follows.

    The parent must lay its children out with GRID: the bar is added and
    removed as the content changes, and pack would give it the cavity
    the text already holds.
    """
    bar = tk.Scrollbar(parent, command=text.yview, width=12,
                       bd=0, highlightthickness=0)
    text.configure(yscrollcommand=bar.set)

    def _sync(*_a):
        try:
            # `yview()` returns the visible fraction of the document: the
            # last fraction is 1.0 only when everything fits.
            need = text.yview()[1] < 1.0
        except Exception:
            need = False
        try:
            if need and not bar.grid_info():
                bar.grid(row=0, column=1, sticky="ns")
            elif not need and bar.grid_info():
                bar.grid_remove()
        except Exception:
            pass

    text.bind("<Configure>", _sync, add="+")
    text.bind("<<Modified>>", _sync, add="+")
    _sync()
    return bar


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
        _place_aux(w, "WindowHistoryPlacement", _TEMPLATE_GEOMETRY("history"))
        # Native's tree (DLG 164's SysTreeView32) is a SINGLE indented
        # column with NO headings: the parent row carries a STAR ICON and
        # the source text, and the child row carries the SERVICE's icon
        # and the translation (capture 2133). The port had three headed
        # columns with the favourite as a ★ character and the service by
        # NAME.
        tv = ttk.Treeview(w, show="tree", height=12)
        # The icons must be HELD: a PhotoImage that is only passed to
        # `insert(image=...)` is garbage-collected and the image
        # disappears from the tree.
        _imgs = []
        _star_on = _bundle_icon("star", master=w)
        _star_off = _bundle_icon("star_off", master=w)
        # The service icons are named after the service DIRECTORY
        # (Papago is Naver's translator), as on the Services page.
        _icon_alias = {"papago": "naver"}

        def _row_star(fav):
            img = _star_on if fav else _star_off
            if img is not None and img not in _imgs:
                _imgs.append(img)
            return img or ""

        def _svc_icon(svc):
            img = _bundle_icon(_icon_alias.get(svc, str(svc)),
                               "service_icons", master=w)
            if img is None:
                return ""
            if img not in _imgs:
                _imgs.append(img)
            return img
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
                # Native's tree ALWAYS has the translation as the child
                # row (the capture 2133 shows "person_record" with
                # "nguồi_record" under it), so the default is ON.
                _expand = bool(_C.load().get(
                    "General", {}).get("ExpandHistoryItems", True))
            except Exception:
                _fav_only, _text, _expand = False, "", True
            for idx, item in enumerate(self.history):
                svc, src = item[0], item[1]
                res = item[2] if len(item) > 2 else ""
                fav = len(item) > 3 and item[3]
                if _fav_only and not fav:
                    continue
                if _text and _text not in src.lower():
                    continue
                tv.insert("", "end", iid=str(idx),
                          text=src[:70], image=_row_star(fav))
                if _expand and res:
                    tv.insert(str(idx), "end", iid=f"{idx}-tr",
                              text=res[:120], image=_svc_icon(svc))
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
            _paint_star()

        def _paint_star(*_a):
            """The star shows the selection's own favourite state."""
            try:
                sel = tv.selection()
                on = False
                if sel:
                    idx = int(sel[0].split("-")[0])
                    on = bool(len(self.history[idx]) > 3
                              and self.history[idx][3])
                _fav_btn.config(image=(_fav_on if on else _fav_off) or "")
            except Exception:
                pass

        def clear():
            self.history.clear()
            for i in tv.get_children():
                tv.delete(i)

        frm = tk.Frame(w, bg=_COLORS["back"])
        frm.pack(pady=(0, 8))
        # Native's DLG 164 bottom row, in the template's order:
        # 1067 'Clear' (x=1), 1160 'Save as...' (x=54), 1173 (a radio with
        # a star, x=130) and 1 'OK' (a DEFPUSHBUTTON, x=264). The port
        # had a wide 'Favorite' text button where native has a 15x14 star
        # and no OK button at all.
        tk.Button(frm, text=_Cw(3, 1067, "Clear"),
                  command=clear).pack(side="left", padx=4)
        tk.Button(frm, text=_Cw(3, 1160, "Save as..."),
                  command=self.app.on_export_history).pack(side="left",
                                                           padx=4)
        _fav_on = _bundle_icon("star", master=w)
        _fav_off = _bundle_icon("star_off", master=w)
        _fav_btn = tk.Button(frm, image=(_fav_on or ""), width=15, height=15,
                             relief="flat", bd=0, highlightthickness=0,
                             bg=_COLORS["back"], command=toggle_fav)
        if _fav_on is None:
            _fav_btn.config(text=_T("Strings", 201, "Favorite"), width=8)
        _fav_btn.pack(side="left", padx=4)
        # OK closes the window the way the X does -- through the
        # WM_DELETE_WINDOW handler, which is what saves the placement.
        # `destroy()` would skip it and the window would snap back to
        # the template next run.
        tk.Button(frm, text=_Cw(3, 1, "OK"),
                  command=lambda: w.event_generate(
                      "<WM_DELETE_WINDOW>")).pack(side="right", padx=4)
        tv.bind("<<TreeviewSelect>>", _paint_star)
        _paint_star()
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
        _place_aux(w, "WindowDictionaryPlacement", _TEMPLATE_GEOMETRY("dictionary"))
        # Native DLG 184's row is three controls -- a language ComboBox
        # (1142), a search Edit (1183) and a ':' menu button (1187) --
        # and the capture 2132 shows what native draws around them:
        #
        #   [English v] [<][>] [        search field        ] [q] [d] [v]
        #
        # The port drew "Word:" + an entry + an "Exact" checkbutton + a
        # "Look up" button, which is a different row. The lookup now
        # goes through the magnifier, the word history through the clock,
        # and "Exact" / the services pane live in the ':' menu, as
        # native's do.
        frm = tk.Frame(w, bg=_COLORS["back"])
        frm.pack(fill="x", padx=8, pady=8)
        # 1142: the language the lookup runs in.
        _lang_c = ttk.Combobox(frm, values=list(LANG_DISPLAY.values()),
                               width=14, state="readonly")
        _lang_c.pack(side="left")
        try:
            _ltbl = list(__import__(
                "qtranslate.services.google_translate",
                fromlist=["SUPPORTED_LANGS"]).SUPPORTED_LANGS)
            _lidx = int(_C.load().get("General", {}).get(
                "LanguageDictionary", 17))
            _lcode = _ltbl[_lidx] if 0 <= _lidx < len(_ltbl) else "en"
            _lang_c.set(LANG_DISPLAY.get(_lcode, _lcode))
        except Exception:
            _lang_c.set("English")

        def _set_lang(_e=None):
            try:
                _name = _lang_c.get()
                for _code, _disp in LANG_DISPLAY.items():
                    if _disp == _name:
                        _tbl = list(__import__(
                            "qtranslate.services.google_translate",
                            fromlist=["SUPPORTED_LANGS"]).SUPPORTED_LANGS)
                        if _code in _tbl:
                            _full = _C.load()
                            _full.setdefault("General", {})[
                                "LanguageDictionary"] = _tbl.index(_code)
                            import json as _jl
                            with open(_C.DEFAULT_PATH, "w",
                                      encoding="utf-8") as _fh:
                                _jl.dump(_full, _fh, ensure_ascii=False,
                                         indent=1)
                        break
            except Exception:
                pass
        _lang_c.bind("<<ComboboxSelected>>", _set_lang)

        # Native's order is: [language v] [<][>] [field] [q] [d] [v]
        # -- the history arrows sit BETWEEN the language combo and the
        # field, not after it.
        _hpos = [0]

        def _hist():
            try:
                import json as _jh
                import os as _oh
                _hp = _oh.path.join(_oh.path.dirname(
                    _C.DEFAULT_PATH), "DictionaryHistory.json")
                with open(_hp, encoding="utf-8") as _fh:
                    _h = _jh.load(_fh)
                return [str(x) for x in _h]
            except Exception:
                return []

        def _hist_step(_d):
            _h = _hist()
            if not _h:
                return
            _hpos[0] = max(0, min(len(_h) - 1, _hpos[0] + _d))
            ent.delete(0, "end")
            ent.insert(0, _h[_hpos[0]])

        tk.Button(frm, text="\u25c0", width=2,
                  command=lambda: _hist_step(-1)).pack(side="left")
        tk.Button(frm, text="\u25b6", width=2,
                  command=lambda: _hist_step(1)).pack(side="left")
        ent = tk.Entry(frm, width=28)
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

        # The magnifier is the lookup; the clock opens the history.
        _b_find = tk.Button(frm, text="\u2315", width=2,
                            command=lambda: go_all())

        def _hist_pick():
            _h = _hist()
            if not _h:
                return
            _top = tk.Toplevel(w)
            _top.title("History")
            _lb = tk.Listbox(_top, height=min(10, len(_h)), width=36)
            for _x in _h:
                _lb.insert("end", _x)
            _lb.pack(fill="both", expand=True)

            def _use():
                _s = _lb.curselection()
                if _s:
                    ent.delete(0, "end")
                    ent.insert(0, _h[_s[0]])
                _top.destroy()
            _b = tk.Frame(_top)
            _b.pack(fill="x")
            tk.Button(_b, text="OK", command=_use).pack(side="right",
                                                         padx=2)
            tk.Button(_b, text="Cancel",
                      command=_top.destroy).pack(side="right", padx=2)
        _b_hist = tk.Button(frm, text="\u2317", width=2,
                            command=_hist_pick)
        # 1187: native's ':' menu.
        _menu = tk.Menu(w, tearoff=0)
        _menu.add_checkbutton(label="Exact search", variable=_exact_v,
                              command=_save_exact)
        _menu.add_separator()
        _menu.add_command(label="History", command=_hist_pick)
        _menu.add_command(label="Look up", command=lambda: go_all())
        _b_menu = tk.Button(frm, text="\u22ee", width=2,
                            command=lambda: _menu.post(
                                frm.winfo_rootx() + frm.winfo_width() - 20,
                                frm.winfo_rooty() + frm.winfo_height()))
        # The three right-hand buttons are packed BEFORE the search
        # field, and from the right edge. A slave packed with expand=True
        # takes the whole cavity, so an entry packed first squeezed the
        # magnifier, the clock and the ':' menu down to nothing at all --
        # they measured 1x1 and never appeared.
        _b_menu.pack(side="right")
        _b_hist.pack(side="right")
        _b_find.pack(side="right", padx=(2, 0))
        ent.pack(side="left", padx=4, fill="x", expand=True)
        mid = tk.Frame(w, bg=_COLORS["back"])
        # `mid` is packed LAST (see below): a slave packed with
        # expand=True takes the whole cavity, so anything packed after it
        # lands off-screen. That is why the zoom row was invisible.
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
        # The result pane, with the scrollbar native's has (the capture
        # 2132 shows its up and down arrows at the right edge). The text
        # and the bar are gridded inside their own frame: the bar is
        # added and removed as the content changes, and pack would give
        # it the cavity the text already holds.
        outfrm = tk.Frame(mid, bg="white")
        outfrm.pack(side="left", fill="both", expand=True)
        outfrm.columnconfigure(0, weight=1)
        outfrm.rowconfigure(0, weight=1)
        out = tk.Text(outfrm, wrap="word", bg="white", fg="black",
                      insertbackground="black", font=("Tahoma", _font))
        out.grid(row=0, column=0, sticky="nsew")
        w._dict_scroll = _text_scrollbar(outfrm, out)

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
                        "LanguageDictionary", LANG_DEFAULTS["LanguageDictionary"])
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
                    # Native's zero-result state is a MESSAGE, not a
                    # blank pane: "No results found for '<query>'."
                    # (the string pool's own wording -- see
                    # dict_render.NO_RESULTS). The port showed the
                    # literal "[empty]" instead.
                    _text = summary
                    if not _text:
                        try:
                            from qtranslate import dict_render as _DR2
                            _text = _DR2.NO_RESULTS % word_q
                        except Exception:
                            _text = "No results found for '%s'." % word_q
                    out.insert("1.0", _text)
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

        # The bottom band: the zoom row and native's service strip. Both
        # are packed at the very END of the builder (see below) -- the
        # pack ORDER is the layout.
        zb = tk.Frame(w, bg=_COLORS["back"])
        tk.Button(zb, text="A-",
                  command=lambda: _zoom_by(-1)).pack(side="left")
        tk.Button(zb, text="A+",
                  command=lambda: _zoom_by(1)).pack(side="left", padx=4)

        # Native's dictionary window ends with a strip of the dictionary
        # services: one cell per service, each with the service's own
        # icon and its name clipped to the cell's width ("G...", "W...",
        # "B...", ...). The port had the services in a list on the left
        # and no strip at all, so the strip is built here from the
        # recovered icons (`qtranslate/assets/dict_icons/`) in native's
        # order.
        #
        # Two things this has to get right:
        # * The PhotoImages are held on the WINDOW, not on a local. Tk
        #   frees an image when the last Python reference to it goes, and
        #   a button whose image was freed draws an EMPTY BOX -- which is
        #   exactly what the strip did before this was fixed.
        # * The label is drawn on a fixed-width canvas, because native
        #   clips the name at the cell edge and a Tk button would simply
        #   grow instead of clipping.
        import os as _os
        _imgs = []
        _strip = tk.Frame(w, bg=_COLORS["back"], highlightthickness=1,
                          highlightbackground="#7e7e7e")
        for _sid in _dorder:
            _name = _disp.get(_sid, "id:%s" % _sid)
            _cell = tk.Frame(_strip, bg=_COLORS["back"])
            _cell.pack(side="left")
            # Native's strip is a row of 42-pixel cells separated by a 1px
            # divider, and the icon sits FOUR pixels inside the cell's
            # left edge. Measured off the capture 2132: the dividers are
            # the full-height dark columns at x = 87, 129, 171, 213, 255,
            # 297, 339, 381, 423 and the 16-pixel icons at x = 175, 217,
            # 259, 301, 343 -- a pitch of exactly 42, and four pixels
            # between a divider and the icon that follows it. The port
            # drew a plain frame per cell with a 1px gap, which put the
            # cells 40 pixels apart and lost the dividers entirely.
            #
            # 1 (divider) + 3 (gap) + 16 (icon) + 22 (label) = 42.
            _div = tk.Frame(_cell, bg="#7e7e7e", width=1)
            _div.pack(side="left", fill="y")
            _icon = None
            _stem = _DICT_ICON_FILES.get(_name, "")
            if _stem:
                try:
                    _p = _os.path.join(_os.path.dirname(
                        _os.path.abspath(__file__)), "assets", "dict_icons",
                        _stem + ".png")
                    if _os.path.exists(_p):
                        _ph = tk.PhotoImage(master=w, file=_p)
                        _imgs.append(_ph)
                        _icon = _ph
                except Exception:
                    _icon = None
            if _icon is not None:
                _b = tk.Button(_cell, image=_icon, width=16, height=16,
                               relief="flat", bd=0,
                               highlightthickness=0,
                               bg=_COLORS["back"])
            else:
                _b = tk.Button(_cell, width=16, height=16, relief="flat",
                               bd=0, highlightthickness=0,
                               bg=_COLORS["back"])
            # The 3px gap between the divider and the icon.
            _b.pack(side="left", padx=(3, 0))
            _cv = tk.Canvas(_cell, width=22, height=16, bg=_COLORS["back"],
                            highlightthickness=0, bd=0)
            _cv.create_text(1, 8, text=_name[:1] + "...", anchor="w",
                            fill=_COLORS["text"], font=("Segoe UI", 8))
            _cv.pack(side="left")

            def _pick(_sid=_sid):
                """Clicking a service shows that service's result."""
                if _dlb is not None:
                    for _i, _s in enumerate(_dorder):
                        if _s == _sid:
                            _dlb.selection_clear(0, "end")
                            _dlb.selection_set(_i)
                            break
                go_all()
            _b.configure(command=_pick)
        # The images have to outlive this function.
        w._dict_icon_images = _imgs

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
        # The pack ORDER is the layout. A slave packed with expand=True
        # takes the whole cavity, so everything that has to stay visible
        # is packed before `mid` -- and the service strip goes first of
        # all, because a side="bottom" slave packed before its siblings
        # lands on the bottom edge.
        _strip.pack(side="bottom", fill="x", padx=4, pady=(0, 2))
        zb.pack(side="bottom", fill="x", padx=8, pady=(0, 4))
        mid.pack(fill="both", expand=True, padx=8, pady=(0, 4))
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
        # Native's popup header starts with a CLOSE button (the capture
        # 2130 shows an "X" at the far left of the caption row).
        try:
            tk.Button(_hdr, text="\u2715", width=1, relief="flat",
                      bd=0, bg=_pc.get("back", "#f0f0f0"),
                      fg=_pc.get("text", "#000000"),
                      command=_close_popup).pack(side="left", padx=(0, 2))
        except Exception:
            pass
        _hdr_text = tk.Label(_hdr, text="%s to %s…" % (_hdr_src, _hdr_tgt),
                             bg=_pc.get("back", "#f0f0f0"),
                             fg=_pc.get("text", "#000000"))
        _hdr_text.pack(side="left")
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
                # Native's fourth popup glyph is "b" over "a" -- the
                # ROMANIZATION mark (measured off the native capture
                # 2130 and the Appearance page's Icons row), not a
                # refresh arrow.
                tk.Label(_bar, text="b\u2090",
                         bg=_pc.get("back", "#f0f0f0")).pack(side="left", padx=1)
        txt = tk.Text(inner, wrap="word",
                      bg=_pc.get("back", "#f0f0f0"),
                      fg=_pc.get("text", "#000000"),
                      insertbackground=_pc.get("text", "#000000"),
                      font=("Segoe UI", 11), borderwidth=0,
                      highlightthickness=0)
        # Native sizes the popup to its CONTENT, not to a fixed column
        # count: the capture 2130 is ~200px wide for the one-line result
        # "người_record", where the port drew a fixed 60 columns (616px).
        # The width is the widest of the caption row and the result, and
        # the CAPTION is truncated with an ellipsis to fit -- which is
        # why native reads "English to Viet…" and not "English to
        # Vietnamese…".
        _longest = max((len(x) for x in result.split("\n")), default=1)
        _cols = max(16, min(60, _longest + 2))
        lines = max(2, min(12, result.count("\n") + len(result) // 60 + 1))
        txt.config(height=lines, width=_cols)
        txt.pack(fill="both", expand=True, padx=6, pady=6)
        txt.insert("1.0", result)
        txt.config(state="disabled")
        try:
            win.update_idletasks()
            _w_max = 265
            _want = max(_hdr.winfo_reqwidth(), txt.winfo_reqwidth())
            _w = max(120, min(_w_max, _want))
            win.geometry("%dx%d" % (_w, win.winfo_reqheight()))
            win.update_idletasks()
            # Truncate the caption to what is left after the close
            # button, the star and the glyph row.
            _fixed = _hdr.winfo_reqwidth() - _hdr_text.winfo_reqwidth()
            _room = max(4, (_w - _fixed - 8) // 7)
            _full = "%s to %s…" % (_hdr_src, _hdr_tgt)
            if len(_full) > _room:
                _hdr_text.config(text=_full[:max(1, _room - 1)] + "…")
        except Exception:
            pass

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
        return win



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
        _place_aux(w, "WindowOptionsPlacement", _TEMPLATE_GEOMETRY("options"))
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

        # --- the SHELL, measured off the native captures -------------------
        #
        # Every number below is measured from the native Options window
        # (docs/review/native_screens/2140.png and 2141.png, both 646x389)
        # with a pixel scan, not estimated, and is a CLIENT coordinate --
        # the native's title bar is 26 pixels tall, so its client area
        # starts at y = 26 and the measurements below have that offset
        # removed:
        #
        #   * the nav list is a SUNKEN FRAME whose border columns are 4
        #     and 145, with a horizontal line at client y = 3 (the image
        #     row 29) and one at client y = 326 (the image row 352);
        #   * the page body starts at client x = 152 -- the group box's
        #     own left edge is the column 152 -- and ends at x = 635;
        #   * the OK / Cancel / Apply row's top edge is the image row
        #     358, i.e. client y = 332.
        #
        # The port drew the list at x = 10 with 8px of padding around
        # it, which pushed the body to x = 162 and left every group 10
        # pixels to the right of where native draws it.
        #
        # The nav list is a Listbox, and a Listbox draws its own sunken
        # border, so it needs no extra frame: `place` puts it exactly
        # where the measurement says.
        _SHELL = {
            "list_x": 4, "list_w": 141, "list_y": 3, "list_h": 323,
            "body_x": 152, "body_w": 483, "body_y": 3,
            "btn_y": 332, "btn_h": 25,
        }
        # DLG 154's button row: OK / Cancel / Apply in a strip along the
        # BOTTOM, right-aligned. The port packed the row after the nav
        # and the body, so the body had already taken the width and the
        # row was pushed off the right-hand edge of the window.
        frm = tk.Frame(w, bg=_COLORS["back"])
        frm.pack(side="bottom", fill="x")
        # Packed right-to-left, so the LAST one packed is the leftmost:
        # DLG154's order is OK (x 267), Cancel (321), Apply (375).
        tk.Button(frm, text="Apply",
                  command=w.destroy).pack(side="right", padx=4)
        tk.Button(frm, text="Cancel",
                  command=_cancel).pack(side="right", padx=4)
        tk.Button(frm, text="OK",
                  command=w.destroy).pack(side="right", padx=4)
        # The nav list: 141 px wide, 323 tall, at (4, 29).
        left = tk.Listbox(w, width=20, height=20, bg=_COLORS["back"],
                          fg=_COLORS["text"], borderwidth=1,
                          highlightthickness=0, relief="sunken",
                          activestyle="none")
        left.place(x=_SHELL["list_x"], y=_SHELL["list_y"],
                   width=_SHELL["list_w"], height=_SHELL["list_h"])
        # Page order = Windows Ids 10-18, labels localized via _W.
        # _PAGE_IDS maps listbox index.
        #
        # The ORDER is native's, and it is NOT the numeric order of the ids:
        # native's Options nav list reads
        #   Basics, Hotkeys, Internet, Services, Languages, Appearance,
        #   Exceptions, Advanced, Updates
        # -- Hotkeys is SECOND, not seventh. Measured off the native
        # capture (docs/review/native_screens/2140.png, whose eighth nav
        # row is the selected one); the id -> name mapping is the locale
        # pack's (English lang.json: 10=Basics, 11=Internet, 12=Services,
        # 13=Languages, 14=Appearance, 15=Exceptions, 16=Hotkeys,
        # 17=Advanced, 18=Updates).
        _PAGES = [("Basics", 10), ("Hotkeys", 16), ("Internet", 11),
                  ("Services", 12), ("Languages", 13), ("Appearance", 14),
                  ("Exceptions", 15), ("Advanced", 17), ("Updates", 18)]
        pages = [p for p, _ in _PAGES]
        _PAGE_IDS = {p: i for i, (p, _) in enumerate(_PAGES)}
        for p, wid in _PAGES:
            left.insert("end", _W(wid, p))
        body = tk.Frame(w, bg=_COLORS["back"])
        body.place(x=_SHELL["body_x"], y=_SHELL["body_y"],
                   width=_SHELL["body_w"],
                   height=_SHELL["list_h"])

        def _combo_items(page, cid, default):
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

        # Native's ComboBoxes on the Advanced page are 175 px wide and
        # their right edge is x = 629 -- i.e. 6 px inside the group's
        # right edge at 635 (measured off the capture 2140: the sunken
        # border columns are 455 and 629). A ttk.Combobox's width is in
        # CHARACTERS, so the pixel width is what has to be requested;
        # at the dialog's own font that is 25 characters.
        _ADV_COMBO_CHARS = 25

        def _labelframe(parent, page, cid, default, height=None):
            """A native GROUP BOX.

            Native's groups are DLGITEMTEMPLATEEX `Button(AUTORADIOBUTTON)`
            -- a Win32 group box: a sunken frame with the caption inset
            into its top edge. The Tk equivalent is a LabelFrame, and the
            port's bold Label was the wrong control (it drew a caption
            with no frame at all).

            The port's LabelFrame then drew the caption in BOLD, which is
            not what native draws either. Measured on the native capture
            2140:

              * the frame is a full rectangle -- the columns 152 and 635
                run the group's whole height, and the top and bottom
                edges are horizontal lines across the group's width;
              * the caption sits IN the top edge, at the group's left
                plus 9 px, in the SAME regular weight as the rest of the
                dialog's text (native's "Advanced" is not bold);
              * the group is 483 px wide, i.e. the full body width.
            """
            lf = tk.LabelFrame(parent, text=_Cw(page, cid, default),
                               bg=_COLORS["back"], fg=_COLORS["text"],
                               font=("MS Shell Dlg", 8),
                               highlightthickness=1, borderwidth=1)
            lf.pack(fill="x", pady=(6, 2))
            if height:
                lf.pack_propagate(False)
                lf.configure(height=height)
            return lf

        def _groupbox(parent, page, cid, default, height=None):
            """A native GROUP BOX, drawn the way native draws it.

            Native's group box is a Win32 `BS_GROUPBOX`: a 1-pixel
            sunken frame in #7e7e7e around a WHITE interior, with the
            caption sitting ON the top edge (the edge is broken where the
            caption is). Measured on the capture 2140:

              * the frame's left edge is the column 152, its right edge
                the column 635, its top edge the row 35 and its bottom
                edge the row 214 -- all of them a single #7e7e7e pixel;
              * the interior just inside the frame is WHITE, not the
                dialog's #f0f0f0 face;
              * the caption starts 9 pixels inside the frame's left edge
                and sits ON the top edge, in the regular dialog font;
              * the first content row starts 11 pixels below the frame's
                top edge, so it clears the caption.

            A Tk LabelFrame cannot do this: it paints a border the theme
            chooses, keeps the parent's face colour inside, and puts the
            caption in a title strip. So the frame is drawn by hand --
            four 1-pixel edges plus a caption label that overlaps the
            top edge -- which is also what the native pixel comparison
            needs.

            The CONTENT goes into an inner frame, whose background is the
            group's white interior; the row and checkbox helpers take
            their background from their parent, so they come out white
            too.
            """
            caption = _Cw(page, cid, default)
            # The box's own face is WHITE: the strip above the content
            # (where the caption sits) must not show the frame colour.
            box = tk.Frame(parent, bg="#ffffff")
            box.pack(fill="x", pady=(6, 2), padx=(0, 0))
            if height:
                box.pack_propagate(False)
                box.configure(height=height)
            inner = tk.Frame(box, bg="#ffffff")
            inner.pack(fill="both", expand=True, pady=(11, 2))
            edges = []

            def _draw_edges():
                for e in edges:
                    e.destroy()
                edges.clear()
                w = box.winfo_width()
                h = box.winfo_height()
                if w <= 1 or h <= 1:
                    return
                for ex, ey, ew, eh in ((0, 0, w, 1), (0, h - 1, w, 1),
                                       (0, 0, 1, h), (w - 1, 0, 1, h)):
                    f = tk.Frame(box, bg="#7e7e7e")
                    f.place(x=ex, y=ey, width=ew, height=eh)
                    f.lift()
                    edges.append(f)
                # The caption breaks the top edge: a white patch the
                # caption's width, then the caption itself.
                lab = tk.Label(box, text=caption, bg="#ffffff",
                               fg=_COLORS["text"], font=("MS Shell Dlg", 8))
                lab.place(x=9, y=-6)
                lab.lift()
                edges.append(lab)
                # the rest of the top edge, after the caption
                gap = tk.Frame(box, bg="#ffffff")
                gap.place(x=9 + lab.winfo_reqwidth() + 2, y=0,
                          width=max(1, w - 11 - lab.winfo_reqwidth()),
                          height=1)
                gap.lift()
                edges.append(gap)
                # ...and the part BEFORE the caption, which the caption
                # overlaps: the top edge is BROKEN where the caption
                # sits, exactly as native draws it.
                lead = tk.Frame(box, bg="#ffffff")
                lead.place(x=0, y=0, width=9, height=1)
                lead.lift()
                edges.append(lead)

            box.after_idle(_draw_edges)
            box.bind("<Configure>", lambda _e: _draw_edges())
            return inner

        def _group(parent, page, cid, default, height=None):
            """The native group box (see `_groupbox` for the drawing)."""
            return _groupbox(parent, page, cid, default, height=height)

        def _row(parent, page, cid, default, value="", width=22,
                 values=None, label_width=22, combo_width=None):
            """One label + control row, the shape native uses throughout:
            a fixed-width Static on the left, the control on the right.

            Native's controls are RIGHT-ALIGNED: on the Advanced page the
            four ComboBoxes all end at x = 629, with their left edge at
            x = 455 (measured off 2140). The port packed the control
            immediately after the label, so its combos sat in the middle
            of the page and their width followed the label's.
            """
            # The background comes from the PARENT, so a row inside a
            # group box takes the group's white interior and a row on
            # the page face takes the face colour.
            _bg = parent.cget("bg")
            r = tk.Frame(parent, bg=_bg)
            r.pack(fill="x", pady=1)
            tk.Label(r, text=_Cw(page, cid, default), width=label_width,
                     anchor="w", bg=_bg,
                     fg=_COLORS["text"]).pack(side="left")
            if values is not None:
                w = ttk.Combobox(r, values=values, width=width,
                                 state="readonly")
                if combo_width:
                    w.pack(side="right")
                    w.configure(width=combo_width)
                else:
                    w.pack(side="left")
                if value:
                    w.set(str(value))
            else:
                w = tk.Entry(r, width=width)
                if combo_width:
                    w.pack(side="right")
                    w.configure(width=combo_width)
                else:
                    w.pack(side="left")
                w.insert(0, "" if value is None else str(value))
            return w

        def _check(parent, page, cid, default, var, command=None):
            _bg = parent.cget("bg")
            tk.Checkbutton(parent, text=_Cw(page, cid, default),
                           variable=var, bg=_bg,
                           fg=_COLORS["text"], selectcolor=_bg,
                           command=command).pack(anchor="w")

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
            gen = _group(body, 10, 1046, "General")
            self.app._opt_vars = getattr(self, "_opt_vars", {})
            # Start-with-Windows via startup_entry (Win HKCU Run; honest
            # no-op off-Windows). Same key/value as before the refactor.
            _startup, _set_startup = startup_entry()
            _sv = tk.BooleanVar(value=_startup)
            self.app._opt_vars["startup"] = _sv  # keep ref: no GC-uncheck

            def _toggle_startup():
                _set_startup(bool(_sv.get()))

            tk.Checkbutton(gen, text=_Cw(10, 1045, "Start with Windows"),
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
                r = tk.Frame(gen, bg=_COLORS["back"])
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
            adg = _group(body, 10, 1063, "Auto-detect languages")
            _IDX2NAME = {57: "Vietnamese", 17: "English"}
            for lab, key in ((_Cw(10, 1068, "First language:"), "LanguageFirst"),
                             (_Cw(10, 1069, "Second language:"), "LanguageSecond"),
                             (_Cw(10, 1071, "Speech input:"),
                              "LanguageSpeechRecognition")):
                r = tk.Frame(adg, bg=_COLORS["back"])
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
            hist = _group(body, 10, 1064, "History")
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
                     _gen.get("ExpandHistoryItems", True))):
                v = tk.BooleanVar(value=bool(default))
                self.app._opt_vars[lab] = v  # keep ref: no GC-uncheck
                tk.Checkbutton(
                    hist, text=lab, variable=v, bg=_COLORS["back"],
                    fg=_COLORS["text"], selectcolor=_COLORS["back"],
                    command=lambda k=key, vv=v: _save_history_flag(
                        k, vv)).pack(anchor="w")

        def show_appearance():
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
            # The documented native defaults are the fallback for a key
            # the config file does not carry: native's own Options.json
            # always has all 13, but a fresh port config has none, and
            # every checkbox then read as "off" instead of native's
            # "Enable auto size" / "Enable auto position" / "Pin when
            # dragging" / "Auto-hide delay 5".
            try:
                from qtranslate import config as _CAF
                _ap = dict(_CAF.DEFAULT_APPEARANCE)
                _ap.update(cfg.get("Appearance", {}))
            except Exception:
                _ap = dict(cfg.get("Appearance", {}))
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
            _keep = []
            # The four glyphs, as native draws them (measured off the
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
                    _doc_icon = tk.PhotoImage(master=body, file=_p)
                    _keep.append(_doc_icon)
            except Exception:
                _doc_icon = ""
            for cid, bit, glyph in ((1138, 2, "\u25a4"),
                                    (1139, 4, None),
                                    (1140, 8, "\u29c9"),
                                    (1141, 16, "b\u2090")):
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
                _b.pack(side="left", padx=1)

                def _flip(b=bit, btn=_b, cid=cid):
                    nonlocal _cur_mask
                    _cur_mask = (_cur_mask | b) if not (_cur_mask & b) \
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
                _sw = tk.Frame(_r, width=52, height=16,
                               bg="#%06x" % int(_ap.get(key, default)),
                               relief="sunken", borderwidth=2)
                _sw.pack(side="left", padx=(0, 4))
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
            # Native DLG 173 -- Options page 12 ("Services").
            #
            #   1080  SysListView32   the service list
            #   1139  Button          (no text -- an icon button)
            #   1140  Button          (no text -- an icon button)
            #   1177  Button          'Add dictionary...'
            #   1180  Button          'Remove dictionary'
            #
            # ONE list, with the two groups native shows in it:
            # "Translation" (Google, Microsoft, Promt, Babylon, Yandex,
            # youdao, Baidu, Papago, DeepL) and "Dictionary" (Google
            # Search, WordReference, Babylon Dictionary, Wikipedia, ...).
            # Each row is a checkbox -- checked = enabled -- plus the
            # service icon.
            #
            # The port drew two listboxes with 'On/Off' and 'All' buttons
            # (native has neither) and filled them from `ServicesOrder`
            # alone, so on a fresh config -- where that key is absent --
            # BOTH LISTS WERE EMPTY. The order now falls back to the
            # canonical one, which is the same list the native capture
            # shows.
            for c in body.winfo_children():
                c.destroy()
            try:
                from qtranslate import config as C2
                _order = list(cfg.get("ServicesOrder")
                              or C2.DEFAULT_SERVICES_ORDER)
                _dis = set(cfg.get("DisabledServices", []))
                _dorder = list(cfg.get("DictionariesOrder")
                               or C2.DEFAULT_DICTIONARIES_ORDER)
                _ddis = set(cfg.get("DisabledDictionaries", []))
                _names = dict(C2.SERVICE_DISPLAY)
                _dnames = dict(C2.DICT_DISPLAY)
            except Exception:
                _order, _dis, _dorder, _ddis = [], set(), [], set()
                _names, _dnames = {}, {}

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

            _fr = tk.Frame(body, bg=_COLORS["back"])
            _fr.pack(fill="both", expand=True)
            _tv = ttk.Treeview(_fr, show="tree", height=12,
                                selectmode="browse")
            _tv.pack(side="left", fill="both", expand=True)
            _sb = tk.Scrollbar(_fr, orient="vertical", command=_tv.yview)
            _sb.pack(side="right", fill="y")
            _tv.configure(yscrollcommand=_sb.set)
            _g_t = _tv.insert("", "end", text=_Cw(12, 1130, "Translation"),
                              open=True)
            _g_d = _tv.insert("", "end", text=_Cw(12, 1131, "Dictionary"),
                              open=True)
            # (tree item, service id, is-dictionary, disabled set)
            _rows = []

            # The icons must be HELD: a PhotoImage that is only passed to
            # `insert(image=...)` is garbage-collected, and the image
            # disappears from the tree. `_imgs` keeps them alive.
            _imgs = []
            # Native's icon for the Papago service is the one recovered
            # as `naver.png` (Papago is Naver's translator); the manifest
            # names the file after the service directory.
            _ICON_ALIAS = {"papago": "naver"}

            def _icon(name):
                try:
                    import os as _os
                    _name = _ICON_ALIAS.get(name, name)
                    _p = _os.path.join(_os.path.dirname(
                        _os.path.abspath(__file__)), "assets",
                        "service_icons", _name + ".png")
                    if not _os.path.exists(_p):
                        return ""
                    _ph = tk.PhotoImage(master=body, file=_p)
                    _imgs.append(_ph)
                    return _ph
                except Exception:
                    return ""

            def _fill():
                # Only the ROWS are rebuilt -- the two group headers
                # (_g_t / _g_d) are the tree's roots and must survive.
                for _g in (_g_t, _g_d):
                    for _it in _tv.get_children(_g):
                        _tv.delete(_it)
                del _rows[:]
                for _i in _order:
                    _n = _names.get(_i, "id:%s" % _i)
                    _on = _i not in _dis
                    _it = _tv.insert(_g_t, "end",
                                     text=("\u2611 " if _on else "\u2610 ")
                                     + _n, image=_icon(_n.lower()))
                    _rows.append((_it, _i, False, _dis))
                for _i in _dorder:
                    _n = _dnames.get(_i, "id:%s" % _i)
                    _on = _i not in _ddis
                    _it = _tv.insert(_g_d, "end",
                                     text=("\u2611 " if _on else "\u2610 ")
                                     + _n, image=_icon(_n.lower()))
                    _rows.append((_it, _i, True, _ddis))
            _fill()

            def _toggle(_ev=None):
                _sel = _tv.selection()
                if not _sel:
                    return
                for _it, _i, _isdict, _dis_set in _rows:
                    if _it != _sel[0]:
                        continue
                    if _i in _dis_set:
                        _dis_set.discard(_i)
                    else:
                        _dis_set.add(_i)
                    _save()
                    _fill()
                    return
            _tv.bind("<<TreeviewSelect>>", _toggle)

            def _add_dict():
                """1177 'Add dictionary...' -- native opens a picker of the
                dictionary services that are not in the list yet."""
                _sel = _tv.selection()
                _have = set(_dorder)
                _todo = [i for i in C2.DICT_DISPLAY if i not in _have]
                if not _todo:
                    return
                _pick = tk.Toplevel(body)
                _pick.title(_Cw(12, 1177, "Add dictionary..."))
                _lb2 = tk.Listbox(_pick, height=8, width=28)
                for _i in _todo:
                    _lb2.insert("end", C2.DICT_DISPLAY.get(_i, str(_i)))
                _lb2.pack(fill="both", expand=True)

                def _ok():
                    _s = _lb2.curselection()
                    if not _s:
                        return
                    _dorder.append(_todo[_s[0]])
                    _save()
                    _fill()
                    _pick.destroy()
                _b = tk.Frame(_pick)
                _b.pack(fill="x")
                tk.Button(_b, text="OK", command=_ok).pack(side="right",
                                                            padx=2)
                tk.Button(_b, text="Cancel",
                          command=_pick.destroy).pack(side="right", padx=2)

            def _remove_dict():
                """1180 'Remove dictionary' -- drops the selected
                dictionary service from the list."""
                _sel = _tv.selection()
                if not _sel:
                    return
                for _it, _i, _isdict, _dis_set in _rows:
                    if _it != _sel[0]:
                        continue
                    if not _isdict:
                        return
                    _dorder.remove(_i)
                    _dis_set.discard(_i)
                    _save()
                    _fill()
                    return

            def _move(_d):
                _sel = _tv.selection()
                if not _sel:
                    return
                for _it, _i, _isdict, _dis_set in _rows:
                    if _it != _sel[0]:
                        continue
                    _seq = _dorder if _isdict else _order
                    try:
                        _k = _seq.index(_i)
                    except ValueError:
                        return
                    _j2 = _k + _d
                    if 0 <= _j2 < len(_seq):
                        _seq[_k], _seq[_j2] = _seq[_j2], _seq[_k]
                        _save()
                        _fill()
                    return
            _br = tk.Frame(body, bg=_COLORS["back"])
            _br.pack(fill="x", pady=(4, 0))
            tk.Button(_br, text="\u25b2", width=3,
                      command=lambda: _move(-1)).pack(side="left", padx=1)
            tk.Button(_br, text="\u25bc", width=3,
                      command=lambda: _move(1)).pack(side="left", padx=1)
            tk.Button(_br, text=_Cw(12, 1177, "Add dictionary..."),
                      command=lambda: _add_dict()).pack(side="left", padx=6)
            tk.Button(_br, text=_Cw(12, 1180, "Remove dictionary"),
                      command=_remove_dict).pack(side="left", padx=1)

        def show_languages():
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
            # Four columns, filled top-to-bottom (column-major) -- the
            # order native's list view uses, and the order the captured
            # page shows.
            _cols = 4
            _nrows = (len(_rows) + _cols - 1) // _cols

            # Native draws the checklist itself, not a column of Tk
            # checkbuttons: a LIST VIEW with a checkbox in front of each
            # language, 14px per row, four columns filled top-to-bottom.
            # A Tk Checkbutton is ~23px tall, so eighteen of them do not
            # fit the page -- the "Check / Uncheck all" button was pushed
            # off the bottom. The grid is therefore drawn on a Canvas at
            # native's row pitch, with native's blue checkbox.
            _ROW = 14
            # Native's list is 484px wide for four columns (121 each) --
            # see the measured native capture 2137.
            _COLW = 124
            _cv = tk.Canvas(body, bg=_COLORS["back"], highlightthickness=0,
                             height=_nrows * _ROW + 6)
            _cv.pack(fill="both", expand=True)

            def _draw():
                _cv.delete("all")
                for _k, (_n, _i) in enumerate(_rows):
                    _c, _r = divmod(_k, _nrows)
                    _x = _c * _COLW
                    _y = _r * _ROW
                    _on = _i not in _dis
                    _cv.create_rectangle(
                        _x + 1, _y + 1, _x + 12, _y + 12,
                        fill="#0078d7" if _on else "#ffffff",
                        outline="#0078d7" if _on else "#7e7e7e")
                    if _on:
                        _cv.create_line(_x + 3, _y + 6, _x + 5, _y + 9,
                                        _x + 10, _y + 3, fill="#ffffff",
                                        width=2)
                    _cv.create_text(_x + 17, _y + 7, text=_n, anchor="w",
                                    fill=_COLORS["text"],
                                    font=("Segoe UI", 8))
            _draw()

            def _click(e):
                _c = int(e.x) // _COLW
                _r = int(e.y) // _ROW
                _k = _c * _nrows + _r
                if not (0 <= _k < len(_rows)):
                    return
                _i = _rows[_k][1]
                if _i in _dis:
                    _dis.discard(_i)
                else:
                    _dis.add(_i)
                _save()
                _draw()
            _cv.bind("<Button-1>", _click)

            def _check_all():
                # 1099 'Check / Uncheck all': enable all if any language
                # is disabled, else disable them all.
                if _dis:
                    _dis.clear()
                else:
                    _dis.update(_i for _n, _i in _rows)
                _save()
                _draw()
            tk.Button(body, text=_Cw(13, 1099, "Check / Uncheck all"),
                      command=_check_all).pack(anchor="w", pady=(8, 0))

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

            con = _group(body, 11, 1049, "Connection")
            r = tk.Frame(con, bg=_COLORS["back"])
            r.pack(fill="x", pady=1)
            # 1084 is a COMBOBOX and its label says "Timeout, sec:", but
            # Options.json stores MILLISECONDS (10000). Native shows the
            # seconds and stores the milliseconds, so the port does the
            # same: the field shows 10 and writes 10000 back.
            tk.Label(r, text=_Cw(11, 1084, "Timeout, sec:"), width=18,
                     anchor="w", bg=_COLORS["back"],
                     fg=_COLORS["text"]).pack(side="left")
            _to_secs = [str(i) for i in range(1, 121)]
            _te = ttk.Combobox(r, values=_to_secs, width=10,
                               state="readonly")
            _te.pack(side="left")
            try:
                _te.set(str(max(1, int(_inet.get("Timeout", 10000))
                                 // 1000)))
            except Exception:
                _te.set("10")
            _te.bind("<<ComboboxSelected>>", lambda e: (
                _inet.__setitem__("Timeout", int(_te.get()) * 1000),
                _save_n()))
            px = _group(body, 11, 1048, "Proxy")
            # Native ProxyType combo (W11/1135): system/no/manual/
            # auto-detect; manual details below map Proxy.Host/Port
            # (HTTP/SOCKS distinguished by Scheme in our stack).
            _pt_vals = ["Use system proxy settings", "No proxy",
                        "Manual proxy configuration",
                        "Auto-detect proxy settings"]
            _pt = ttk.Combobox(px, values=_pt_vals, width=26,
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
                rr = tk.Frame(px, bg=_COLORS["back"])
                rr.pack(fill="x", pady=1)
                tk.Label(rr, text=lab, width=18, anchor="w",
                         bg=_COLORS["back"],
                         fg=_COLORS["text"]).pack(side="left")
                ee = tk.Entry(rr, width=26,
                              show="*" if key == "Password" else "")
                ee.pack(side="left")
                ee.insert(0, str(_px.get(key, "")))
                _entries[key] = ee
            _sch = ttk.Combobox(px, values=["http", "https"], width=26,
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
            # Native DLG 176 -- Options page 15 ("Exceptions").
            #
            #   1162  ComboBox   the MODE: "Disabled for these programs:"
            #                       / "Enabled for these programs:"
            #   1104  SysListView32  the rows for that mode
            #   1101  Button     'Add'
            #   1103  Button     'Modify'
            #   1102  Button     'Delete'
            #   1113  Button     'Enable smart detection'
            #
            # The port drew the combo's two states as TWO lists
            # ("Blocked (Disabled)" and "Allowed (Enabled)"), which is
            # why it needed a caption the native does not have.
            for c in body.winfo_children():
                c.destroy()
            _ex = cfg.get("Exceptions", {})
            _dis_list = [list(p) for p in _ex.get("Disabled", [])]
            _en_list = [list(p) for p in _ex.get("Enabled", [])]
            self.app._opt_vars = getattr(self, "_opt_vars", {})

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

            # 1162 is the MODE combo. The pack lists its items as
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

            _r = tk.Frame(body, bg=_COLORS["back"])
            _r.pack(fill="x")
            _cb = ttk.Combobox(_r, values=list(_modes), width=48,
                               state="readonly")
            _cb.pack(side="left")
            _cb.set(_mode.get())
            _cb.bind("<<ComboboxSelected>>",
                     lambda e: (_mode.set(_cb.get()),
                                _ex.__setitem__("DisabledMode",
                                                _mode.get() == _MODE_D),
                                _save_x(), _refresh()))

            _tbl = tk.Frame(body, bg="white", highlightthickness=1,
                            highlightbackground="#7e7e7e")
            _tbl.pack(fill="both", expand=True, pady=4)
            tk.Label(_tbl, text="Program Name", bg="white", fg="black",
                     anchor="w").place(x=6, y=4)
            tk.Label(_tbl, text="Window Class Name", bg="white", fg="black",
                     anchor="w").place(x=246, y=4)
            _lb = tk.Listbox(_tbl, bg="white", fg="black", borderwidth=0,
                             highlightthickness=0)
            _lb.place(x=4, y=22, relwidth=0.98, relheight=0.92)

            def _refresh():
                _lb.delete(0, "end")
                for _exe, _cls in _pairs():
                    _lb.insert("end", "%-24s %s" % (_exe or "* All Programs *",
                                                    _cls or "* All Windows *"))
            _refresh()

            # 1101 / 1103 / 1102 open DLG178 -- a separate "Exception"
            # dialog with a Program name combo (1112) + a '...' browse
            # button (1109), a Window class name edit (1107) + its own
            # '...' (1110), and OK / Cancel. The port drew the two fields
            # inline under the table instead, which is a different page.
            def _entry_dialog(title, exe="", cls=""):
                """DLG178: the add/modify entry editor."""
                _d = tk.Toplevel(body)
                _d.title(title)
                _d.configure(bg=_COLORS["back"])
                _d.transient(body)
                _f = tk.Frame(_d, bg=_COLORS["back"])
                _f.pack(fill="both", expand=True, padx=8, pady=6)
                tk.Label(_f, text="Program name:", bg=_COLORS["back"],
                         fg=_COLORS["text"], anchor="w").pack(fill="x")
                _r1 = tk.Frame(_f, bg=_COLORS["back"])
                _r1.pack(fill="x", pady=1)
                _pe = tk.Entry(_r1, width=44)
                _pe.pack(side="left", fill="x", expand=True)
                _pe.insert(0, exe)

                def _browse_prog():
                    try:
                        from tkinter import filedialog as _fd
                        _p = _fd.askopenfilename(
                            title="Program name",
                            filetypes=[("Programs", "*.exe *.bat *.cmd"),
                                       ("All files", "*.*")])
                        if _p:
                            _pe.delete(0, "end")
                            _pe.insert(0, _p)
                    except Exception:
                        pass
                tk.Button(_r1, text="...", width=3,
                          command=_browse_prog).pack(side="left", padx=2)
                tk.Label(_f, text="Window class name:", bg=_COLORS["back"],
                         fg=_COLORS["text"],
                         anchor="w").pack(fill="x", pady=(6, 0))
                _r2 = tk.Frame(_f, bg=_COLORS["back"])
                _r2.pack(fill="x", pady=1)
                _ce = tk.Entry(_r2, width=44)
                _ce.pack(side="left", fill="x", expand=True)
                _ce.insert(0, cls)
                _known = sorted({c for _p in (_dis_list + _en_list)
                                 for _c in [_p[1]] if c})

                def _browse_cls():
                    """Native's 1110 lists the window classes in use; the
                    port has no window enumerator, so it offers the
                    classes already configured."""
                    if not _known:
                        return
                    _top = tk.Toplevel(_d)
                    _top.title("Window class name")
                    _lb2 = tk.Listbox(_top, height=min(8, len(_known)),
                                      width=40)
                    for _c in _known:
                        _lb2.insert("end", _c)
                    _lb2.pack(fill="both", expand=True)

                    def _pick():
                        _s = _lb2.curselection()
                        if _s:
                            _ce.delete(0, "end")
                            _ce.insert(0, _known[_s[0]])
                        _top.destroy()
                    _b = tk.Frame(_top)
                    _b.pack(fill="x")
                    tk.Button(_b, text="OK", command=_pick).pack(
                        side="right", padx=2)
                    tk.Button(_b, text="Cancel",
                              command=_top.destroy).pack(side="right",
                                                         padx=2)
                tk.Button(_r2, text="...", width=3,
                          command=_browse_cls).pack(side="left", padx=2)
                _out = {}

                def _ok():
                    _out["value"] = [_pe.get().strip(), _ce.get().strip()]
                    _d.destroy()
                _bt = tk.Frame(_d, bg=_COLORS["back"])
                _bt.pack(fill="x", padx=8, pady=(0, 8))
                tk.Button(_bt, text="OK", command=_ok).pack(side="right",
                                                            padx=2)
                tk.Button(_bt, text="Cancel",
                          command=_d.destroy).pack(side="right", padx=2)
                _d.grab_set()
                _d.wait_window(_d)
                return _out.get("value")

            def _add():
                _v = _entry_dialog(_W(5, "Exception"), "", "")
                if not _v:
                    return
                _pairs().append([_v[0], _v[1]])
                _refresh()
                _save_x()

            def _modify():
                _s = _lb.curselection()
                if not _s:
                    return
                _i = _s[0]
                _v = _entry_dialog(_W(5, "Exception"), _pairs()[_i][0],
                                   _pairs()[_i][1])
                if not _v:
                    return
                _pairs()[_i] = [_v[0], _v[1]]
                _refresh()
                _lb.selection_set(_i)
                _save_x()

            def _dele():
                _s = _lb.curselection()
                if not _s:
                    return
                _pairs().pop(_s[0])
                _refresh()
                _save_x()

            _fr = tk.Frame(body, bg=_COLORS["back"])
            _fr.pack(fill="x")
            tk.Button(_fr, text=_Cw(15, 1101, "Add"),
                      command=_add).pack(side="left", padx=2)
            tk.Button(_fr, text=_Cw(15, 1103, "Modify"),
                      command=_modify).pack(side="left", padx=2)
            tk.Button(_fr, text=_Cw(15, 1102, "Delete"),
                      command=_dele).pack(side="left", padx=2)

            # 1113 'Enable smart detection' (General.UseSmartDetection)
            try:
                _genx = cfg.get("General", {})
            except Exception:
                _genx = {}
            _sv = tk.BooleanVar(
                value=bool(_genx.get("UseSmartDetection", True)))
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
            # Native DLG 185 -- Options page 17 ("Advanced").
            #
            #   1146 'Advanced'   1151 'Open links with:'    1152 ComboBox
            #                      1147 'Copy action:'       1148 ComboBox
            #                      1149 'Keyboard layout indicator:' 1150
            #                      1157 'Google domain:'     1153 ComboBox
            #                      1154 'Enable GUI translation'
            #                      1159 'Enable listening to the same text
            #                            at a slower speed'
            #                      1160 'Remove line breaks'
            #   1186 'Mouse mode'  1155 'Enable mouse mode only when Ctrl
            #                            is pressed'
            #                      1156 'Click on system tray icon
            #                            switches mouse mode'
            #   1158 'API keys'    1195 'OCR API key:'  1196 Edit
            #                      1197 SysLink
            #
            # The port drew a flat list of five checkboxes and ten text
            # entries, with the same config key under two different
            # labels ("Preferred domain:" and "Google domain:" both
            # wrote PreferredDomain, "Default browser id:" and "Open
            # links with:" both wrote DefaultBrowserId, and so on), and
            # the page overflowed the window so the Apply button was
            # pushed off the bottom.
            for c in body.winfo_children():
                c.destroy()
            try:
                from qtranslate import config as _CAD
                _ad2 = dict(_CAD.DEFAULT_ADVANCED)
                _ad2.update(cfg.get("Advanced", {}))
            except Exception:
                _ad2 = dict(cfg.get("Advanced", {}))
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

            def _set(key, value):
                _ad2[key] = value
                _save_a()

            adv = _group(body, 17, 1146, "Advanced")
            # The four native ComboBoxes. Two of them store a STRING
            # (DefaultBrowserId, PreferredDomain) and two store an INDEX
            # (CopyAction, LayoutIndicator), so the two shapes are bound
            # differently. Native's capture 2140 shows the values
            # "Internet Explorer", "Ctrl + C", "None" and "com".
            for cid, key, vals, indexed in (
                    (1151, "DefaultBrowserId",
                     ["Internet Explorer", "Firefox", "Chrome", "Opera",
                      "Safari", "Edge"], False),
                    (1147, "CopyAction",
                     ["Ctrl + C", "Ctrl + Shift + C", "Ctrl + Insert"], True),
                    (1149, "LayoutIndicator", ["None", "JCUKEN"], True),
                    (1157, "PreferredDomain",
                     ["com", "co.uk", "de", "fr", "co.jp"], False)):
                _cur = _ad2.get(key, "")
                if indexed:
                    try:
                        _shown = vals[int(_cur or 0)]
                    except (ValueError, IndexError):
                        _shown = vals[0]
                else:
                    _shown = _cur if _cur in vals else vals[0]
                _w = _row(adv, 17, cid, "", value=_shown, width=18,
                          values=vals, label_width=20,
                          combo_width=_ADV_COMBO_CHARS)

                def _pick(e=None, k=key, w=_w, v=vals, ix=indexed):
                    if ix:
                        try:
                            _set(k, v.index(w.get()))
                        except ValueError:
                            pass
                    else:
                        _set(k, w.get())
                _w.bind("<<ComboboxSelected>>", _pick)
            for cid, key in ((1154, "EnableGuiTranslation"),
                             (1159, "EnableSlowerListening"),
                             (1160, "RemoveLineBreaks")):
                _v = tk.BooleanVar(value=bool(_ad2.get(key, False)))
                self.app._opt_vars[key] = _v
                _check(adv, 17, cid, "", _v,
                       lambda k=key, v=_v: _set(k, v.get()))

            mm = _group(body, 17, 1186, "Mouse mode")
            for cid, key in ((1155, "EnableMouseModeOnCtrl"),
                             (1156, "SwitchMouseModeOnTrayClick")):
                _v = tk.BooleanVar(value=bool(_ad2.get(key, False)))
                self.app._opt_vars[key] = _v
                _check(mm, 17, cid, "", _v,
                       lambda k=key, v=_v: _set(k, v.get()))

            api = _group(body, 17, 1158, "API keys")
            _w = _row(api, 17, 1195, "OCR API key:",
                      value=_ad2.get("OcrApiKey", ""), width=26,
                      label_width=26)
            _w.bind("<FocusOut>",
                    lambda e: _set("OcrApiKey", _w.get()))
            # 1197 SysLink
            _link = tk.Label(api, text=_Cw(17, 1198,
                                           "Register here for free OCR API key"),
                             fg="blue", cursor="hand2", bg=_COLORS["back"],
                             font=("Segoe UI", 9, "underline"))
            _link.pack(anchor="w")
            _link.bind("<Button-1>",
                       lambda e: _open_url("https://ocr.space/ocrapi"))

        def show_updates():
            # Native DLG 205 -- Options page 18 ("Updates").
            #
            #   1188  Button        'Automatically check for updates'
            #   1189  RichEdit50W   the changelog
            #   1190  Button        'Check now'
            #   1191  Button        'Install'
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
            self.app._opt_vars = getattr(self, "_opt_vars", {})
            self.app._opt_vars["CheckForUpdates"] = vv
            tk.Checkbutton(body, text=_Cw(18, 1188,
                                          "Automatically check for updates"),
                           variable=vv, bg=_COLORS["back"],
                           fg=_COLORS["text"], selectcolor=_COLORS["back"],
                           command=lambda: (
                               _up.__setitem__("CheckForUpdates", vv.get()),
                               _save_u())).pack(anchor="w")
            # 1189 RichEdit50W -- native shows the changelog here.
            _log = tk.Text(body, height=12, wrap="word", bg="white",
                           fg="black", relief="solid", borderwidth=1)
            _log.pack(fill="both", expand=True, pady=4)
            _log.insert("1.0", "QTranslate 6.10.0")

            def _check_now():
                # Native R1/R2: GET the update manifest and parse it.
                # The host retired in 2022 -> normally BLOCKED; parse the
                # payload if one is ever served (uses updater.parse_manifest,
                # FUN_00461ADE).
                try:
                    import urllib.request as _ur
                    from qtranslate import updater as _UP
                    _u = "https://quest-app.appspot.com/update?v=6.10.0"
                    _req = _ur.Request(_u, headers={"User-Agent": "QTranslate"})
                    with _ur.urlopen(_req, timeout=8) as _r:
                        _txt = _r.read().decode("utf-8", "replace")
                    _man = _UP.parse_manifest(_txt)
                    if _man.get("valid"):
                        _log.delete("1.0", "end")
                        _log.insert("1.0", _man.get("notes", "") or "")
                    else:
                        _log.delete("1.0", "end")
                        _log.insert("1.0", "Update check: %s"
                                    % (_man.get("reason", "BLOCKED")))
                except Exception as _exc:
                    _log.delete("1.0", "end")
                    _log.insert("1.0", "Update check: BLOCKED (%s)" % _exc)

            _br = tk.Frame(body, bg=_COLORS["back"])
            _br.pack(fill="x")
            tk.Button(_br, text=_Cw(18, 1190, "Check now"),
                      command=_check_now).pack(side="right", padx=2)
            tk.Button(_br, text=_Cw(18, 1191, "Install"),
                      command=_check_now).pack(side="right", padx=2)

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
        return w


class MainWindow:
    """The main window (DLG129) -- the app's own window.

    Phase 7 asks for *"Split `App` into `MainWindow`, ..."*. This
    is that class. It is not a window hanging off the app -- it IS the
    app's own window -- so it is handed the live ``App`` and reads and
    writes its state there, exactly as the other Phase 7 classes are
    handed ``root`` and ``app``.

    **A split is a MOVE, not a rewrite.** The bodies below are the
    ``app.py`` bodies, with the mechanical substitutions spelled out in
    ``app.py``'s Phase 7 note:

      ``self``        -> ``self.app``   (the App owns the state)
      ``self.X = ...``-> ``self.app.X = ...``
      an internal call to another moved method stays ``self.X``

    No window is created on import (pinned by
    ``tests/regress_windows.py``).
    """

    def __init__(self, app):
        self.app = app
    def _build_main(self):
        bg = _COLORS["back"]
        # nav row
        nav = tk.Frame(self.app.root, bg=bg)
        nav.pack(fill="x", padx=4, pady=(2, 0))
        # Native's nav arrows are BS_ICON buttons -- the EXE's own RT_ICON
        # resources -- not text. Drawn as text they came out 47 pixels
        # wide on macOS (the fallback font's arrow glyph is that wide)
        # where native's are 20.
        self._icon_button(nav, "back", "◀",
                          self.app.hist_back).pack(side="left", padx=1)
        self._icon_button(nav, "forward", "▶",
                          self.app.hist_forward).pack(side="left", padx=1)
        self.app.svc_link = tk.Label(nav, text=self.app.service.title(),
                                 fg="blue", cursor="hand2", bg=bg,
                                 font=("Segoe UI", 9, "underline"))
        self.app.svc_link.pack(side="left", padx=6)
        self.app.svc_link.bind("<Button-1>",
                           lambda e: self.app.open_service_page())
        # 1009: the ':' menu. Native draws the three dots as an icon
        # (the EXE's RT_ICON group), and as text the glyph is wide
        # enough to make the button three characters across.
        self._icon_button(nav, "menu", "⋮",
                          self.app.show_nav_menu).pack(side="right", padx=1)
        # source pane (id1000) + mic/headphone overlay at right edge.
        # The id here used to read 1017; DLG129 has three RichEdits and the
        # two Play buttons settle the mapping -- 1027 sits inside the top
        # pane, so the top pane (1000) is the source.
        # docs/review/MAIN_WINDOW_LAYOUT_DIVERGED_2026-10-16.md
        srcfrm = tk.Frame(self.app.root, bg="white")
        srcfrm.pack(fill="x", padx=4)
        # Native's source pane is DLG129's control 1000 -- 66 DU tall -- and
        # in its own capture (2131, a 516x423 window) it measures **153px**,
        # showing ten and a half lines of the same help text the port
        # renders at the same line pitch (14.6px there, 14.2px here). The
        # port's Text asks for twelve lines (170px), so the port showed a
        # line and a half MORE of the help text than native and a result
        # pane 21px shorter. The frame is given native's height and stops
        # propagating the Text's request; the eleventh line is clipped
        # exactly as native's is.
        #
        # Native's own value moves a little with the window height (153px
        # at 423, 142px at 402, 145px at 409 across the three captures);
        # 153 is the value at the reference window size.
        srcfrm.pack_propagate(False)
        srcfrm.grid_propagate(False)
        # The frame's HEIGHT is the pane's height, and the Text's line
        # count follows it: the Text is gridded with a weighted row, so
        # its own `-height` no longer decides the visible size, and the
        # scrollbar's viewport has to be the visible size for the bar
        # to appear when the content does not fit.
        try:
            _pitch = max(1, tkfont.Font(font=_pane_font()).metrics(
                "linespace"))
        except Exception:
            _pitch = 14

        def _set_src_height(px):
            px = max(60, int(px))
            srcfrm.configure(height=px)
            try:
                self.app.src.config(height=max(3, int(px / _pitch)))
            except Exception:
                pass

        # kept on the app so the sash and the tests can move the pane
        self.app._set_src_height = _set_src_height
        self.app._src_pane_base = _src_pane_px()
        _set_src_height(self.app._src_pane_base)
        self.app._panes = getattr(self.app, "_panes", {})
        self.app._panes["src"] = srcfrm
        self.app.src = tk.Text(srcfrm, height=12, wrap="word", bg="white",
                           fg="black", insertbackground="black",
                           font=_pane_font(), borderwidth=0,
                           highlightthickness=0, undo=True,
                           maxundo=100)
        # GRID, not pack: the pane's scrollbar is shown and hidden as the
        # content overflows, and grid is the only one of the two that can
        # add and remove a column without the text losing the cavity.
        srcfrm.columnconfigure(0, weight=1)
        srcfrm.rowconfigure(0, weight=1)
        self.app.src.grid(row=0, column=0, sticky="nsew")
        self.app._src_scroll = _text_scrollbar(srcfrm, self.app.src)
        # Contents.EditSource cache wins over the default help text
        # (native restores last session panes on boot).
        try:
            from qtranslate import config as _CC
            _es = (_CC.load().get("Contents", {}).get("EditSource")
                   or "").strip()
        except Exception:
            _es = ""
        self.app.src.insert("1.0", _es if _es else self.app.default_source_text())
        self.app.src.bind("<KeyRelease>", lambda e: self.app.on_type())
        # General.MidSplitterPos: native drag-sash between the source and
        # result panes, persisted as a pixel/line offset (was previously
        # unconsumed -- no sash existed at all).
        try:
            from qtranslate import config as _CMS
            _mid_pos = int(_CMS.load().get("General", {}).get(
                "MidSplitterPos", 0) or 0)
        except Exception:
            _mid_pos = 0
        if _mid_pos:
            # General.MidSplitterPos is a PIXEL offset from native's
            # measured pane height (the sash writes the same unit).
            try:
                _set_src_height(self.app._src_pane_base + _mid_pos)
            except Exception:
                pass
        # Native OVERLAYS these buttons ON the source pane's bottom-right
        # corner rather than giving them a side column: DLG129 puts `Fav`
        # 1029 / `Speech` 1030 / `Play` 1027 at y=64-77, which is INSIDE
        # pane 1000 (y 16-82), 5 DU below its bottom edge and 13/28/43 DU
        # left of its right edge. A side column steals width from the pane
        # and changes the reading order, which is the visual "lệch" the user
        # reported. `place()` with relx/rely reproduces the overlay.
        # docs/review/MAIN_WINDOW_LAYOUT_DIVERGED_2026-10-16.md
        # Native overlays a MICROPHONE and a HEADPHONE on the source pane's
        # bottom-right (native glyph boxes x 453..464 and 474..487 in a pane
        # whose right edge is at ~500, bottoms 9px above the pane's bottom).
        # The icons are native's own, recovered from the EXE's RT_ICON
        # resources and bundled under qtranslate/assets/ui_icons/.
        _ovl = dict(borderwidth=0, bg="white", relief="flat",
                    highlightthickness=0, takefocus=0)
        for _i, (_key, _fn, _dx) in enumerate(
                (("mic", self.app.on_mic, 36), ("headphone", self.app.on_listen, 13))):
            _photo = self.app._ui_icon(_key)
            b = tk.Button(srcfrm, command=_fn, **_ovl)
            if _photo is not None:
                b.config(image=_photo, width=SVC_ICON_PX, height=SVC_ICON_PX)
            else:
                b.config(text="Mic" if _key == "mic" else "Head",
                         font=("Tahoma", 7), width=6)
            b.place(relx=1.0, rely=1.0, anchor="se", x=-_dx, y=-9)
        # Drag sash: resize the source pane, persisting the delta to
        # General.MidSplitterPos (native mid-pane splitter).
        sash = tk.Frame(self.app.root, bg="#c1c1c2", height=3,
                        cursor="sb_v_double_arrow")
        sash.pack(fill="x")
        self.app._mid_splitter_base = [_mid_pos]

        def _sash_drag(e):
            try:
                delta_px = e.y_root - sash.winfo_rooty()
            except Exception:
                return
            try:
                base = self.app._src_pane_base + \
                    self.app._mid_splitter_base[0]
                new_h = max(60, min(400, base + delta_px))
                if new_h != srcfrm.winfo_height():
                    _set_src_height(new_h)
                    self.app._mid_splitter_base[0] = \
                        new_h - self.app._src_pane_base
            except Exception:
                pass

        def _sash_release(_e=None):
            try:
                from qtranslate import config as _CMS2
                import json as _jms
                full = _CMS2.load()
                full.setdefault("General", {})["MidSplitterPos"] = \
                    self.app._mid_splitter_base[0]
                with open(_CMS2.DEFAULT_PATH, "w",
                          encoding="utf-8") as fh:
                    _jms.dump(full, fh, ensure_ascii=False, indent=1)
            except Exception:
                pass

        sash.bind("<B1-Motion>", _sash_drag)
        sash.bind("<ButtonRelease-1>", _sash_release)
        # toolbar row: [paste] [kebab] [Auto-Detect] [swap] [target]
        # [Translate] — no mic/headphone here (they live on the panes)
        bar = tk.Frame(self.app.root, bg=bg)
        bar.pack(fill="x", padx=4, pady=2)
        # GRID, not pack: native's tool row always fits -- the Translate
        # button sits at the right edge (native x 438..510 of 516). Packed
        # left to right, the row overflowed a 516px window and the Translate
        # button was cut off (the port drew it at x 481..497). The two
        # combobox columns carry the weight, so they share whatever is left.
        bar.columnconfigure(2, weight=1)
        bar.columnconfigure(4, weight=1)
        # id1021 "New": clears source for a fresh translation
        self._icon_button(bar, "new", "\U0001f4cb", self.app.on_new).grid(
            row=0, column=0, sticky="w", padx=1)
        self._icon_button(bar, "menu", "⋮", self.app.show_nav_menu).grid(
            row=0, column=1, sticky="w", padx=1)
        # width is in CHARACTERS for a ttk combobox; native's Auto-Detect
        # combo is 150px wide and shows the whole label, so 13 characters
        # clipped it to "Auto-Detec".
        self.app.src_lang = ttk.Combobox(bar, values=_lang_names(LANGS),
                                     width=16, state="readonly")
        self.app.src_lang.set(LANG_DISPLAY.get(self.app.source, "Auto-Detect"))
        self.app.src_lang.grid(row=0, column=2, sticky="ew", padx=2)
        tk.Button(bar, text="⇄", width=3, font=("Segoe UI Symbol", 10),
                  command=self.app.on_swap).grid(row=0, column=3, sticky="w",
                                             padx=1)
        self.app.tgt = ttk.Combobox(bar, values=_lang_names(TO_LANGS,
                                                        False),
                                width=18, state="readonly")
        self.app.tgt.set(LANG_DISPLAY.get(self.app.target, self.app.target))
        self.app.tgt.grid(row=0, column=4, sticky="ew", padx=2)
        self.app.tgt.bind("<<ComboboxSelected>>",
                      lambda e: self.app._persist_langs(
                          LANG_CODES.get(self.app.src_lang.get().strip(),
                                         "auto"),
                          LANG_CODES.get(self.app.tgt.get().strip(), "vi")))
        self.app.src_lang.bind("<<ComboboxSelected>>",
                           lambda e: self.app._persist_langs(
                               LANG_CODES.get(
                                   self.app.src_lang.get().strip(), "auto"),
                               LANG_CODES.get(self.app.tgt.get().strip(),
                                              "vi")))
        tk.Button(bar, text=_Cw(1, 1004, "Translate"),
                  command=self.app.on_go).grid(row=0, column=5, sticky="e", padx=4)
        self.app.suggest = tk.Label(self.app.root, text="", bg=bg, fg="gray",
                                anchor="w", font=("Tahoma", 7),
                                cursor="hand2")
        # NOT packed: native has no permanent suggestion band -- the
        # capture (2131) shows the main window without one -- so the line
        # is packed only while it carries a suggestion. Packing it
        # unconditionally left a 17px empty grey band under the tool row.
        self.app.suggest.bind("<Button-1>",
                          lambda e: self.app.accept_suggestion())
        self.app._suggestions = []
        # result pane (id1017) + headphone overlay bottom-right.
        # Was labelled 1018; that is DLG129's small BOTTOM pane, which this
        # port does not build. Native also has no side column for these
        # buttons -- they overlay the pane.
        # docs/review/MAIN_WINDOW_LAYOUT_DIVERGED_2026-10-16.md
        outfrm = tk.Frame(self.app.root, bg="white")
        outfrm.pack(fill="both", expand=True, padx=4)
        self.app._panes["mid"] = outfrm
        # ShowTopPane/Middle/Services (native 0x8071/0x8064/0x8065,
        # Ctrl+F1/F2/F3): srcfrm=top, bar+outfrm=middle, strip=services.
        # _gp must be bound here, before the first Show* test below reads it.
        try:
            from qtranslate import config as _CP
            _gp = _CP.load().get("General", {})
        except Exception:
            _gp = {}
        try:
            if not _gp.get("ShowTopPane", True) and self.app._panes.get(
                    "src") is not None:
                self.app._panes["src"].pack_forget()
            if not _gp.get("ShowMiddlePane", True):
                outfrm.pack_forget()
        except Exception:
            pass
        self.app.out = tk.Text(outfrm, height=6, wrap="word", bg="white",
                           fg="black", insertbackground="black",
                           font=_pane_font(), borderwidth=0,
                           highlightthickness=0, undo=True,
                           maxundo=100)
        outfrm.columnconfigure(0, weight=1)
        outfrm.rowconfigure(0, weight=1)
        self.app.out.grid(row=0, column=0, sticky="nsew")
        self.app._out_scroll = _text_scrollbar(outfrm, self.app.out)
        self.app.out.bind("<Button-3>", self.app.show_result_menu)
        # Contents.EditTranslation / EditBackTranslation cache: restore the
        # last result and back-translation content on boot. These are TWO
        # SEPARATE native fields (+0x178 / +0x17c,
        # D10_SPOTCHECK_Contents_2026-10-10.md §2) feeding TWO SEPARATE
        # controls (1017 / 1018), so they are restored to their own panes
        # instead of being concatenated with a separator the image does not
        # contain.
        try:
            from qtranslate import config as _CET
            _cc = _CET.load().get("Contents", {})
            _et = (_cc.get("EditTranslation") or "").strip()
            _ebt = (_cc.get("EditBackTranslation") or "").strip()
            if _et:
                self.app.out.insert("1.0", _et)
            if _ebt:
                # held for the aux pane, which is built just below
                self.app._ebt_restore = _ebt
        except Exception:
            pass
        # Same overlay as the source pane: native's `Play` 1028 sits INSIDE
        # result pane 1017 (y 101-152) at y=134, 5 DU below its bottom and
        # 13 DU left of its right edge.
        # Native draws the same HEADPHONE icon on the result pane's
        # bottom-right as on the source pane's (the glyph is native's own,
        # recovered from the EXE's RT_ICON resources); the port used a music
        # note, which is a different symbol entirely.
        _b = tk.Button(outfrm, borderwidth=0, bg="white", relief="flat",
                       highlightthickness=0, takefocus=0,
                       command=self.app.on_listen)
        _hp = self.app._ui_icon("headphone")
        if _hp is not None:
            _b.config(image=_hp, width=SVC_ICON_PX, height=SVC_ICON_PX)
        else:
            _b.config(text="♫", width=4, font=("Tahoma", 9))
        _b.place(relx=1.0, rely=1.0, anchor="se", x=-13, y=-9)
        # --- the THIRD pane: DLG129's RichEdit50W id 1018, cy=27 DU ---
        # Native has three text panes, and the three Contents keys map onto
        # them in order: EditSource->1000, EditTranslation->1017,
        # EditBackTranslation->1018 (D10_SPOTCHECK_Contents_2026-10-10.md
        # §2). This pane was missing from the port entirely, and the
        # back-translation was instead concatenated into the result pane with
        # a separator that is not in the image. Built here, below the result
        # pane with its own Play button beside it, exactly like the template's
        # [1017][separator 1135][1018] stack.
        self.app._panes["aux_sep"] = tk.Frame(self.app.root, bg="#c1c1c2", height=3)
        self.app._panes["aux_sep"].pack(fill="x", padx=4)
        auxfrm = tk.Frame(self.app.root, bg="white")
        self.app._panes["aux"] = auxfrm
        # NOT packed: native's capture shows DLG129's third RichEdit (1018)
        # COLLAPSED to zero height when there is no back-translation --
        # the separator 1135 is there, the pane is not -- so the port's
        # always-visible 16px empty band was a divergence. The pane is
        # packed only while it carries a back-translation.
        auxfrm.pack_forget()
        self.app.aux = tk.Text(auxfrm, height=1, wrap="word", bg="#fafafa",
                           fg="#333333", insertbackground="#333333",
                           font=_pane_font(), borderwidth=0,
                           highlightthickness=0, undo=False)
        self.app.aux.pack(side="left", fill="both", expand=True)
        self.app.aux.bind("<Button-3>", self.app.show_result_menu)
        auxside = tk.Frame(auxfrm, bg="white")
        auxside.pack(side="right", fill="y", padx=2)
        # Play 1028 sits beside the RESULT pane natively; the aux pane has no
        # Play of its own, so this is a spacing frame, not a control.
        tk.Frame(auxside, bg="white", height=4).pack()
        # restore the cached back-translation into the new pane
        _ebt0 = getattr(self.app, "_ebt_restore", "") or ""
        if _ebt0:
            self.app.aux.insert("1.0", _ebt0)
            # ...and the pane has to be SHOWN: the third pane is packed
            # only while it carries a back-translation, so a restored one
            # that never unpacks it leaves the text invisible.
            self._set_aux_visible(True)
        # service icon strip at the bottom (icons from Services/*/Service.ico,
        # click = switch + re-translate like FUN_0045CDBA; middle-click =
        # browser, right-click = multi-select per help.txt Actions).
        # Native shows icon above a short name (Go.., Mi.., Pr.., ...).
        strip = tk.Frame(self.app.root, bg=bg)
        strip.pack(fill="x", padx=4, pady=(2, 4))
        # The dict is UPDATED, not replaced. Replacing it dropped "src"
        # and "mid" back to None, and the pane toggles (Ctrl+F1/F2/F3 and
        # the menu items) read exactly those two keys -- so they did
        # nothing at all.
        self.app._panes.update({"svc": strip})
        if not _gp.get("ShowServicesPane", True):
            strip.pack_forget()
        self.app.svc_btns = {}
        self.app.svc_icons = {}
        # short names exactly like native: Go.. Mi.. Pr.. Ba.. Ya..
        # yo.. Ba.. Pa.. De.. (icon folder names truncated to 2 chars)
        _SHORT = {"google": "Go..", "microsoft": "Mi..", "promt": "Pr..",
                  "babylon": "Ba..", "yandex": "Ya..", "youdao": "yo..",
                  "baidu": "Ba..", "naver": "Pa..", "deepl": "DeepL",
                  "reverso": "Re.."}
        for name in self.app.ordered_services():
            # native: small icon + short name side-by-side in one row
            cell = tk.Frame(strip, bg=bg)
            cell.pack(side="left", padx=2)
            # width/height are PIXELS here because the button always ends up
            # with an image (see _load_svc_icon). A text button would read
            # them as characters and be 10x too wide.
            b = tk.Button(cell, width=SVC_ICON_PX, height=SVC_ICON_PX,
                          borderwidth=0, bg=bg, activebackground=bg,
                          highlightthickness=0,
                          command=lambda n=name: self.app.switch_service(n))
            b.pack(side="left")
            b.bind("<Button-2>",
                   lambda e, n=name: self.app.open_service_page_n(n))
            b.bind("<Button-3>",
                   lambda e, n=name: self.app.toggle_multi_service(n))
            tk.Label(cell, text=_SHORT.get(name, name[:2] + ".."), bg=bg,
                     fg="black", font=("Tahoma", 8)).pack(side="left",
                                                          padx=(1, 0))
            self.app.svc_btns[name] = b
            self.app._load_svc_icon(name, b)
        self.app._mark_service()
        # key bindings mirror help.txt Main window hotkeys
        self.app.root.bind("<Control-Return>", lambda e: self.app.on_go())
        self.app.root.bind("<Control-k>", lambda e: self.app.open_keyboard())
        self.app.root.bind("<Control-n>", lambda e: self.app.on_clear())
        self.app.root.bind("<Control-d>", lambda e: self.app.open_dict_window())
        self.app.root.bind("<Control-h>", lambda e: self.app.open_history_window())
        self.app.root.bind("<Control-i>", lambda e: self.app.on_swap())
        self.app.root.bind("<F1>", lambda e: self.app.show_hotkeys())
        # Shift+Esc = reset pair to auto-detected (native 0x8052 Reset)
        self.app.root.bind("<Shift-Escape>", lambda e: self.app.reset_pair())
        # Ctrl+1..9 = 1..9th service (accel 0x8042-0x804A),
        # Ctrl+Shift+1..9 = select language pair (help.txt)
        for _i in range(1, 10):
            self.app.root.bind(f"<Control-Key-{_i}>",
                           lambda e, i=_i: self.app.slot_service(i))
            self.app.root.bind(f"<Control-Shift-Key-{_i}>",
                           lambda e, i=_i: self.app.slot_pair(i))
        # Ctrl+Tab / Ctrl+Shift+Tab = next/prev service (accel 170)
        self.app.root.bind("<Control-Tab>", lambda e: self.app.cycle_service(1))
        self.app.root.bind("<Control-Shift-Tab>",
                       lambda e: self.app.cycle_service(-1))
        self.app.root.bind("<Control-space>",
                       lambda e: self.app.accept_suggestion())
        # Alt+Left/Right = history back/forward, Ctrl+Up = copy
        # translation to input (help.txt Main window hotkeys)
        self.app.root.bind("<Alt-Left>", lambda e: self.app.hist_back())
        self.app.root.bind("<Alt-Right>", lambda e: self.app.hist_forward())
        self.app.root.bind("<Control-Up>", lambda e: self.app.copy_to_source())
        # F11 = fullscreen toggle (help.txt Main window hotkeys)
        self.app.root.bind("<F11>", lambda e: self.app.toggle_fullscreen())
        # native pane toggles Ctrl+F1/F2/F3 (0x8071/0x8064/0x8065)
        self.app.root.bind("<Control-F1>",
                       lambda e: self.app.toggle_pane("ShowTopPane", "src"))
        self.app.root.bind("<Control-F2>",
                       lambda e: self.app.toggle_pane("ShowMiddlePane", "mid"))
        self.app.root.bind("<Control-F3>",
                       lambda e: self.app.toggle_pane("ShowServicesPane",
                                                   "svc"))
        # Ctrl+B = back-translation toggle+run (accel 0x8034);
        # Ctrl+Alt+1..9 = dictionary with n-th service (help.txt)
        self.app.root.bind("<Control-b>", lambda e: self.app.toggle_backtr())
        for _i in range(1, 10):
            self.app.root.bind(f"<Control-Alt-Key-{_i}>",
                           lambda e, i=_i: self.app.dict_with_service(i))
        # Shift+1..9 = dictionary with n-th service (accel 0x8082-0x808A)
        for _i in range(1, 10):
            self.app.root.bind(f"<Shift-Key-{_i}>",
                           lambda e, i=_i: self.app.dict_with_service(i))
        # Ctrl+Left/Right = prev/next service (accel 0x8069/0x806A)
        self.app.root.bind("<Control-Left>",
                       lambda e: self.app.cycle_service(-1))
        self.app.root.bind("<Control-Right>",
                       lambda e: self.app.cycle_service(1))
    def toggle_backtr(self):
        try:
            v = not self.app.opt_backtr.get()
            self.app.opt_backtr.set(v)
            from qtranslate import config as _C
            import json as _j
            full = _C.load()
            full.setdefault("General", {})["BackTranslation"] = v
            with open(_C.DEFAULT_PATH, "w",
                      encoding="utf-8") as f:
                _j.dump(full, f, ensure_ascii=False, indent=1)
            if v:
                self.app.on_go()
        except Exception:
            pass
    def dict_with_service(self, n):
        """Ctrl+Alt+1..9: dictionary lookup with the n-th service."""
        try:
            names = self.app.ordered_services()
            if 1 <= n <= len(names):
                self.app.switch_service(names[n - 1])
            self.app.open_dict_window()
        except Exception:
            pass
    def toggle_fullscreen(self):
        try:
            cur = bool(self.app.root.attributes("-fullscreen"))
            self.app.root.attributes("-fullscreen", not cur)
        except Exception:
            pass
    def reset_pair(self):
        """Shift+Esc: reset language pair to auto-detected (native
        Reset 0x8052 + AutoDetection first/second)."""
        try:
            from qtranslate import config as _C
            _ad = _C.load().get("AutoDetection", {})
            _table = list(__import__(
                "qtranslate.services.google_translate",
                fromlist=["SUPPORTED_LANGS"]).SUPPORTED_LANGS)
            _fi, _si = _ad.get("LanguageFirst", 57), _ad.get(
                "LanguageSecond", 17)
            _fn = {c: n for c, n in LANG_DISPLAY.items()}
            _rev = {_table[i] if 0 <= i < len(_table) else "auto"
                    for i in (_fi, _si)}
            self.app.src_lang.set(_fn.get(_table[_fi]
                                      if 0 <= _fi < len(_table) else "auto",
                                      "Auto-Detect"))
            self.app.tgt.set(_fn.get(_table[_si]
                                 if 0 <= _si < len(_table) else "vi",
                                 "Vietnamese"))
        except Exception:
            self.app.src_lang.set("Auto-Detect")
    def slot_service(self, n):
        """Ctrl+1..9: switch to the n-th service (accel 0x8042-0x804A;
        native Ctrl+Alt+1..9 dictionary variant opens dict window)."""
        try:
            names = self.app.ordered_services()
            if 1 <= n <= len(names):
                self.app.switch_service(names[n - 1])
        except Exception:
            pass
    def slot_pair(self, n):
        """Ctrl+Shift+1..9: select the n-th language pair."""
        try:
            from qtranslate import config as _C
            pairs = _C.load().get("LanguagePairs", [])
            if not (1 <= n <= len(pairs)):
                return
            a, b = pairs[n - 1]
            _table = list(__import__(
                "qtranslate.services.google_translate",
                fromlist=["SUPPORTED_LANGS"]).SUPPORTED_LANGS)
            ca = _table[a] if 0 <= a < len(_table) else "auto"
            cb = _table[b] if 0 <= b < len(_table) else "vi"
            self.app.src_lang.set(LANG_DISPLAY.get(ca, ca))
            self.app.tgt.set(LANG_DISPLAY.get(cb, cb))
        except Exception:
            pass
    def cycle_service(self, direction=1):
        """Ctrl+Tab / Ctrl+Shift+Tab: next/previous service (accel 170
        0x8069/0x806A + Ctrl+1..9 slots 0x8042-0x804A)."""
        try:
            names = self.app.ordered_services()
            if not names:
                return
            i = names.index(self.app.service) if self.app.service in names else 0
            self.app.switch_service(names[(i + direction) % len(names)])
        except Exception:
            pass
    def toggle_pane(self, key, pane):
        """Show/hide a main-window pane, persisting General.<key>.

        The read and the write of the settings file are each in their own
        ``try``: a machine with no Options.json yet made ``_C.load()``
        raise, and because the whole body shared one ``except``, the
        pane never toggled either. The file's absence is not a reason to
        refuse to show the pane.
        """
        w = (self.app._panes or {}).get(pane)
        if w is None:
            return
        from qtranslate import config as _C
        import json as _j
        try:
            full = _C.load()
        except Exception:
            full = {}
        if not isinstance(full, dict):
            full = {}
        _gen = full.get("General")
        if not isinstance(_gen, dict):
            _gen = {}
            full["General"] = _gen
        # The CURRENT state is what the PANE shows, not what the file
        # says: if the write fails, the next toggle would read the same
        # value back and undo this one, leaving the pane stuck.
        _state = getattr(self.app, "_pane_state", None)
        if not isinstance(_state, dict):
            _state = {}
            self.app._pane_state = _state
        cur = _state.get(key)
        if cur is None:
            cur = bool(_gen.get(key, True))
        new = not cur
        _state[key] = new
        _gen[key] = new
        try:
            with open(_C.DEFAULT_PATH, "w", encoding="utf-8") as f:
                _j.dump(full, f, ensure_ascii=False, indent=1)
        except Exception:
            pass
        try:
            if cur:
                w.pack_forget()
            else:
                if pane == "mid":
                    w.pack(fill="both", expand=True, padx=4)
                else:
                    w.pack(fill="x", padx=4, pady=(2, 4)
                           if pane == "svc" else 0)
        except Exception:
            pass
    def open_service_page_n(self, name):
        import webbrowser
        try:
            _open_url(_dict_service_link(name))
        except Exception as e:
            self.app.render(f"[error] {e}")
    def _icon_button(self, parent, name, text, command, **kw):
        """A button carrying one of the bundled native icons.

        Native's nav arrows, its ':' menu and its 'New' button are
        BS_ICON buttons -- the EXE's own RT_ICON resources, bundled under
        ``qtranslate/assets/ui_icons/``. Drawn as TEXT they came out 47
        pixels wide on macOS, because the fallback font's arrow glyph is
        that wide, where native's buttons are 20.
        """
        img = self._ui_icon(name)
        bg = kw.pop("bg", _COLORS["back"])
        if img is not None:
            return tk.Button(parent, image=img, width=SVC_ICON_PX,
                             height=SVC_ICON_PX, relief="flat", bd=0,
                             highlightthickness=0, bg=bg,
                             command=command, **kw)
        return tk.Button(parent, text=text, width=3, command=command,
                         bg=bg, **kw)

    def _ui_icon(self, name):
        """The bundled native UI icon (``mic`` / ``headphone``), or None.

        These are native's own icons, recovered from the QTranslate 6.10.0
        EXE's RT_ICON resources and committed under
        ``qtranslate/assets/ui_icons/`` — the same 16x16 bitmaps the native
        main window draws. The result is cached on the app so the
        PhotoImage is not rebuilt per button.

        The PhotoImage is created against the app's OWN root: a
        PhotoImage belongs to the interpreter that made it, and Tk frees
        every image of an interpreter when it is destroyed. Building the
        image on the default root while drawing it on a second App's
        window handed Tk an image it had already deleted, and it raised
        `image "pyimage16" doesn't exist` while building the window.
        """
        cache = getattr(self.app, "_ui_icons", None)
        if cache is None:
            cache = {}
            self.app._ui_icons = cache
        if name in cache:
            return cache[name]
        photo = None
        try:
            import os
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "assets", "ui_icons", name + ".png")
            if os.path.exists(path):
                photo = tk.PhotoImage(master=self.app.root, file=path)
                if (photo.width() != SVC_ICON_PX
                        or photo.height() != SVC_ICON_PX):
                    photo = photo.subsample(
                        max(1, photo.width() // SVC_ICON_PX),
                        max(1, photo.height() // SVC_ICON_PX))
        except Exception:
            photo = None
        cache[name] = photo
        return photo
    def _load_svc_icon(self, name, button):
        """Give the strip button the service's own icon.

        The icons are the native ones, recovered from the QTranslate 6.10.0
        installer payload and committed under
        ``qtranslate/assets/service_icons/`` — pixel-identical to the icons
        the native main window draws in its bottom strip (see
        ``docs/review/rea/service_icons/_pairs.png``). Bundling them is what
        makes the strip render on every platform: the previous code only ever
        looked at ``C:/Program Files (x86)/QTranslate/Services/<Name>/
        Service.ico``, so off Windows no icon was loaded at all.

        The button is always given an IMAGE, because Tk reads a button's
        ``width``/``height`` as **characters** for a text button and as
        **pixels** for an image button. Without an image, ``width=22`` became
        a 230-pixel-wide text button and six of the nine services were pushed
        off the end of the strip.
        """
        import os
        photo = None
        bundled = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "assets", "service_icons", name + ".png")
        if name == "bing":
            bundled = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "assets", "service_icons",
                                    "microsoft.png")
        try:
            if os.path.exists(bundled):
                photo = tk.PhotoImage(master=self.app.root, file=bundled)
                if photo.width() != SVC_ICON_PX or photo.height() != SVC_ICON_PX:
                    photo = photo.subsample(
                        max(1, photo.width() // SVC_ICON_PX),
                        max(1, photo.height() // SVC_ICON_PX))
            else:
                # Fall back to a real installed copy (Windows).
                pats = {
                    "google": "Google Translate", "deepl": "DeepL",
                    "yandex": "Yandex", "baidu": "Baidu", "naver": "Naver",
                    "youdao": "youdao", "bing": "Microsoft Translator",
                    "microsoft": "Microsoft Translator", "promt": "Promt",
                    "reverso": "Reverso", "babylon": "Babylon",
                }
                folder = pats.get(name, name)
                ico = os.path.join(
                    "C:/Program Files (x86)/QTranslate/Services",
                    folder, "Service.ico")
                if not os.path.exists(ico):
                    button.config(text=name[:4])
                    return
                try:
                    from PIL import Image, ImageTk
                    im = Image.open(ico)
                    im = im.convert("RGBA").resize((SVC_ICON_PX, SVC_ICON_PX),
                                                    Image.LANCZOS)
                    photo = ImageTk.PhotoImage(im)
                except Exception:
                    photo = tk.PhotoImage(master=self.app.root, file=ico)
                    w, h = photo.width(), photo.height()
                    if w > 24 or h > 24:
                        photo = photo.subsample(max(1, w // SVC_ICON_PX),
                                                max(1, h // SVC_ICON_PX))
            self.app.svc_icons[name] = photo  # keep ref
            button.config(image=photo, text="")
        except Exception:
            try:
                button.config(text=name[:4])
            except Exception:
                pass
    def _init_opt_flags(self):
        try:
            from qtranslate import config as _C0
            _g0 = _C0.load().get("General", {})
        except Exception:
            _g0 = {}
        self.app.opt_detect = tk.BooleanVar(
            value=bool(_g0.get("AlwaysDetectLanguage", False)))
        self.app.opt_backtr = tk.BooleanVar(
            value=bool(_g0.get("BackTranslation", False)))
    def show_result_menu(self, event=None):
        """Result-pane context menu (native history-item menu Id 3:
        Open/Copy-text/Copy-translation/Delete/Listen)."""
        m = tk.Menu(self.app.root, tearoff=False)
        m.add_command(label=_T("Menus", 20, "Copy translation", menu=3),
                      command=self.app.on_copy)
        m.add_command(label=_T("Menus", 40, "Listen to text", menu=3),
                      command=self.app.on_listen)
        m.add_separator()
        m.add_command(label=_T("Menus", 30, "Clear", menu=3),
                      command=self.app.on_clear)
        try:
            m.tk_popup(self.app.root.winfo_pointerx(),
                       self.app.root.winfo_pointery())
        finally:
            m.grab_release()
    def ordered_services(self):
        """Exact native strip order: Go.. Mi.. Pr.. Ba.. Ya.. yo.. Ba..
        Pa.. De.. = ServicesOrder [1,5,12,13,11,26,28,30,31] verified
        against the real Options.json + screenshot (Pr before Ya)."""
        try:
            from qtranslate import config as C
            ids = C.services_order(None)
            try:
                dis = set(C.load().get("DisabledServices", []))
            except Exception:
                dis = set()
            names = [C.SERVICE_NAMES.get(i) for i in ids
                     if i not in dis]
            # exactly the native strip — no extras appended
            return [n for n in names if n in TRANSLATORS]
        except Exception:
            return ["google", "microsoft", "promt", "babylon", "yandex",
                    "youdao", "baidu", "naver", "deepl"]
    def default_source_text(self):
        """Default source-pane text: version line + full help.txt.

        The header is native's ``%s %s %s`` format (`FUN_0042F2CC`) with its
        three fields ``QTranslate`` / ``Version `` / ``6.10.0``. The middle
        field is a **resource string that ends in a space** (recovered from
        the image's UTF-16 string table, immediately after ``\\x08About``:
        ``"Version "``), and the format joins with a space too -- so the
        rendered line carries **two** spaces before the version number:
        ``QTranslate Version  6.10.0``. Collapsing them to one (as this did
        until 2026-10-16) reads better and is not what native shows.

        Verified side-by-side vs the native window: it shows the whole
        help.txt (Global hotkeys + Main window hotkeys + mouse modes +
        Actions), not just 4 lines.
        """
        lines = ["QTranslate Version  6.10.0", ""]
        # The native's own help.txt, recovered from the installer payload and
        # bundled under qtranslate/assets/locales/en/. Reading it from the
        # Windows install only meant the port opened with a three-line stub
        # everywhere else -- and the native opens with the WHOLE help text
        # (Global hotkeys + Main window hotkeys + mouse modes + Actions).
        import os
        for _path in (
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "assets", "locales", "English", "help.txt"),
                "C:/Program Files (x86)/QTranslate/Locales/English/help.txt"):
            try:
                with open(_path, encoding="utf-8-sig") as f:
                    lines.append(f.read().strip())
                return "\n".join(lines)
            except Exception:
                continue
        lines.append("Double Ctrl => Show main window\n"
                     "Ctrl+Q => Translate selected text\n"
                     "Ctrl+E => Listen to selected text")
        return "\n".join(lines)
    def hist_back(self):
        """Alt+Left: previous translation in session history."""
        try:
            idx = getattr(self.app, "_hist_pos", len(self.app.history)) - 1
            if 0 <= idx < len(self.app.history):
                self.app._hist_pos = idx
                _, src, res = self.app.history[idx][:3]
                self.app.src.delete("1.0", "end")
                self.app.src.insert("1.0", src)
                self.app.render(res)
        except Exception:
            pass
    def hist_forward(self):
        """Alt+Right: next translation in session history."""
        try:
            idx = getattr(self.app, "_hist_pos",
                           len(self.app.history) - 1) + 1
            if 0 <= idx < len(self.app.history):
                self.app._hist_pos = idx
                _, src, res = self.app.history[idx][:3]
                self.app.src.delete("1.0", "end")
                self.app.src.insert("1.0", src)
                self.app.render(res)
        except Exception:
            pass
    def copy_to_source(self):
        """Ctrl+Up: copy translation to the text input box."""
        try:
            txt = self.app.out.get("1.0", "end").strip()
            if txt:
                self.app.src.delete("1.0", "end")
                self.app.src.insert("1.0", txt)
        except Exception:
            pass
    def open_service_page(self):
        import webbrowser
        try:
            _open_url(_dict_service_link(self.app.service))
        except Exception as e:
            self.app.render(f"[error] {e}")
    def show_nav_menu(self):
        # Main-window options menu (native FUN_0042DF28 IDs): toggles
        # write back to General so hotkeys/popup honor them too.
        def _set_general(key, value):
            try:
                from qtranslate import config as _C
                import json as _j
                full = _C.load()
                full.setdefault("General", {})[key] = bool(value)
                with open(_C.DEFAULT_PATH, "w",
                          encoding="utf-8") as f:
                    _j.dump(full, f, ensure_ascii=False, indent=1)
            except Exception:
                pass

        def _toggle_detect():
            v = not self.app.opt_detect.get()
            self.app.opt_detect.set(v)
            _set_general("AlwaysDetectLanguage", v)

        def _toggle_backtr():
            v = not self.app.opt_backtr.get()
            self.app.opt_backtr.set(v)
            _set_general("BackTranslation", v)

        m = tk.Menu(self.app.root, tearoff=False)
        m.add_command(label=_T("Menus", 10, "Show dictionary window",
                               menu=5),
                      command=self.app.open_dict_window)
        m.add_command(label=_T("Menus", 20, "Show history window",
                               menu=5),
                      command=self.app.open_history_window)
        m.add_separator()
        m.add_checkbutton(label=_T("Menus", 30, "Always detect language",
                                   menu=4),
                          variable=self.app.opt_detect,
                          command=_toggle_detect)
        m.add_checkbutton(label=_T("Menus", 30, "Back translation",
                                   menu=1),
                          variable=self.app.opt_backtr,
                          command=_toggle_backtr)

        def _toggle_phonetic():
            # ReadPhonetically (menu Id 1/50). FUN_0042ED3F consumes it to
            # append "\r\r" + "Romanization: " + entry[5] to the RESULT
            # PANE when the phonetics field is non-empty (J7) — the flag is
            # not a TTS control, though the earlier "no-op for TTS" note
            # implied that. do_translate applies the append for Google,
            # whose `dt=rm` response fills the phonetics field; providers
            # that return no romanization get no append, as natively.
            try:
                from qtranslate import config as _C
                import json as _j
                full = _C.load()
                cur = not full.setdefault("General", {}).get(
                    "ReadPhonetically", False)
                full["General"]["ReadPhonetically"] = cur
                with open(_C.DEFAULT_PATH, "w",
                          encoding="utf-8") as f:
                    _j.dump(full, f, ensure_ascii=False, indent=1)
            except Exception:
                pass

        try:
            from qtranslate import config as _CP
            _ph = bool(_CP.load().get("General", {}).get(
                "ReadPhonetically", False))
        except Exception:
            _ph = False
        _ph_v = tk.BooleanVar(value=_ph)
        m.add_checkbutton(label=_T("Menus", 50, "Read phonetically",
                                   menu=1),
                          variable=_ph_v, command=_toggle_phonetic)

        def _toggle_instant():
            try:
                from qtranslate import config as _C
                import json as _j
                full = _C.load()
                cur = not full.setdefault("General", {}).get(
                    "InstantTranslation", False)
                full["General"]["InstantTranslation"] = cur
                with open(_C.DEFAULT_PATH, "w",
                          encoding="utf-8") as f:
                    _j.dump(full, f, ensure_ascii=False, indent=1)
            except Exception:
                pass

        try:
            from qtranslate import config as _CI
            _inst = bool(_CI.load().get("General", {}).get(
                "InstantTranslation", False))
        except Exception:
            _inst = False
        _inst_v = tk.BooleanVar(value=_inst)
        m.add_checkbutton(label=_T("Menus", 20, "Instant translation",
                                   menu=1),
                          variable=_inst_v, command=_toggle_instant)

        # --- native Extended section + remaining menu commands -----------
        # Each checkbutton flips and persists the same Options.json key the
        # native menu item writes (ids from FUN_0042DF28).
        def _persist_bool(section, key):
            def _flip():
                try:
                    from qtranslate import config as _C
                    import json as _j
                    full = _C.load()
                    sec = full.setdefault(section, {})
                    sec[key] = not sec.get(key, False)
                    with open(_C.DEFAULT_PATH, "w",
                              encoding="utf-8") as f:
                        _j.dump(full, f, ensure_ascii=False, indent=1)
                except Exception:
                    pass
            return _flip

        def _bool_var(section, key):
            try:
                from qtranslate import config as _C
                return tk.BooleanVar(
                    value=bool(_C.load().get(section, {}).get(key, False)))
            except Exception:
                return tk.BooleanVar(value=False)

        # Spell checking (0x802b)
        _spell_v = _bool_var("General", "SpellChecking")
        m.add_checkbutton(label=_T("Menus", 25, "Spell checking", menu=1),
                          variable=_spell_v,
                          command=lambda: (_spell_v.set(not _spell_v.get()),
                                           _persist_bool("General",
                                                         "SpellChecking")()))
        # Clear input on Drag && Drop (0x8063)
        _drag_v = _bool_var("General", "ClearOnDragDrop")
        m.add_checkbutton(label=_T("Menus", 60, "Clear input on Drag & Drop",
                                   menu=1),
                          variable=_drag_v,
                          command=lambda: (_drag_v.set(not _drag_v.get()),
                                           _persist_bool("General",
                                                         "ClearOnDragDrop")()))
        # Auto-cleanup of translation (0x8077)
        _ac_v = _bool_var("General", "AutoCleanupOfTranslation")
        m.add_checkbutton(label=_T("Menus", 61, "Auto-cleanup of translation",
                                   menu=1),
                          variable=_ac_v,
                          command=lambda: (_ac_v.set(not _ac_v.get()),
                                           _persist_bool(
                                               "General",
                                               "AutoCleanupOfTranslation")()))
        # Save contents on exit (0x8075) — native key under "Contents"
        _se_v = _bool_var("Contents", "SaveOnExit")
        m.add_checkbutton(label=_T("Menus", 62, "Save contents on exit",
                                   menu=1),
                          variable=_se_v,
                          command=lambda: (_se_v.set(not _se_v.get()),
                                           _persist_bool("Contents",
                                                         "SaveOnExit")()))
        m.add_separator()
        # Show panes (0x8071 top / 0x8064 middle / 0x8065 services)
        m.add_command(label=_T("Menus", 70, "Show top pane", menu=1),
                      command=lambda: self.app.toggle_pane("ShowTopPane", "src"))
        m.add_command(label=_T("Menus", 71, "Show middle pane", menu=1),
                      command=lambda: self.app.toggle_pane("ShowMiddlePane",
                                                       "mid"))
        m.add_command(label=_T("Menus", 72, "Show services pane", menu=1),
                      command=lambda: self.app.toggle_pane("ShowServicesPane",
                                                       "svc"))
        m.add_separator()
        # Minimize to tray (0x806f on minimize / 0x8070 on close)
        _mm_v = _bool_var("General", "MinimizeToTrayOnMinimize")
        m.add_checkbutton(label=_T("Menus", 75, "Minimize to tray on "
                                                 "minimize", menu=1),
                          variable=_mm_v,
                          command=lambda: (_mm_v.set(not _mm_v.get()),
                                           _persist_bool(
                                               "General",
                                               "MinimizeToTrayOnMinimize")()))
        _mc_v = _bool_var("General", "MinimizeToTrayOnClose")
        m.add_checkbutton(label=_T("Menus", 76, "Minimize to tray on close",
                                   menu=1),
                          variable=_mc_v,
                          command=lambda: (_mc_v.set(not _mc_v.get()),
                                           _persist_bool(
                                               "General",
                                               "MinimizeToTrayOnClose")()))
        m.add_separator()
        # Keyboard (0x802f) + Help (0x8030)
        m.add_command(label=_T("Menus", 85, "Keyboard", menu=1),
                      command=self.app.open_keyboard)
        m.add_command(label=_T("Menus", 86, "Help", menu=1),
                      command=self.app.show_hotkeys)
        m.add_separator()
        m.add_command(label=_T("Menus", 80, "Options...", menu=5),
                      command=self.app.open_options)
        m.add_command(label=_T("Menus", 90, "About", menu=5),
                      command=self.app.show_about)
        try:
            m.tk_popup(self.app.root.winfo_pointerx(),
                       self.app.root.winfo_pointery())
        finally:
            m.grab_release()
    def on_new(self):
        """id1021 New: clear source + result for a fresh translation."""
        self.app.src.delete("1.0", "end")
        self.app.render("")
    def on_paste(self):
        if _HAS_KEYS:
            try:
                self.app.src.delete("1.0", "end")
                self.app.src.insert("1.0", pyperclip.paste())
            except Exception as e:
                self.app.render(f"[clipboard error] {e}")
    def on_mic(self):
        # Speech input chain (docs/NATIVE_ARCH.md): mic -> FLAC ->
        # Google full-duplex (needs dead API key). Offline fallback:
        # Windows SAPI shared recognizer when comtypes is installed
        # (pip install comtypes); otherwise explain.
        try:
            import comtypes.client  # type: ignore
        except ImportError:
            self.app.render("[speech input — needs: pip install comtypes "
                        "(offline SAPI) — Google voice API key retired]")
            return

        def _work():
            try:
                reco = comtypes.client.CreateObject(
                    "SAPI.SpSharedRecognizer")
                ctx = reco.CreateRecoContext()
                grammar = ctx.CreateGrammar()
                grammar.DictationLoad()
                grammar.DictationSetState(1)
                heard = []

                class _Events:
                    def OnRecognition(self, *a):
                        try:
                            heard.append(str(a[-1]))
                        except Exception:
                            pass

                import comtypes.client as _cc
                _cc.GetEvents(ctx, _Events())
                import time as _t
                self.app.root.after(0, lambda: self.app.render(
                    "[listening... speak now (10s)]"))
                _t.sleep(10)
                grammar.DictationSetState(0)
                txt = " ".join(heard).strip()
                self.app.root.after(0, lambda: (
                    self.app.src.delete("1.0", "end"),
                    self.app.src.insert("1.0", txt)
                    if txt else self.app.render(
                        "[speech input — nothing recognized]")))
            except Exception as e:
                _speech_err = f"[speech error] {e}"
                self.app.root.after(
                    0, lambda: self.app.render(_speech_err))

        import threading as _th
        _th.Thread(target=_work, daemon=True).start()
    def _mark_service(self):
        # current = sunken; multi-selected = groove highlight.
        for name, b in self.app.svc_btns.items():
            if name == self.app.service:
                b.config(relief="sunken")
            elif name in getattr(self.app, "multi_services", set()):
                b.config(relief="groove")
            else:
                b.config(relief="raised")
    def switch_service(self, name):
        """FUN_0045CDBA + FUN_0043A121: switch provider, re-run."""
        self.app.service = name
        self.app._mark_service()
        try:
            from qtranslate import config as _C
            _disp = _C.SERVICE_DISPLAY.get(
                {v: k for k, v in _C.SERVICE_NAMES.items()}.get(name),
                name.title())
            self.app.svc_link.config(text=_disp)
        except Exception:
            pass
        # persist ActiveServices (native keeps last service)
        try:
            from qtranslate import config as _C
            import json as _j
            _inv = {v: k for k, v in _C.SERVICE_NAMES.items()}
            full = _C.load()
            full.setdefault("General", {})["ActiveServices"] = [
                _inv.get(name, 1)]
            with open(_C.DEFAULT_PATH, "w",
                      encoding="utf-8") as f:
                _j.dump(full, f, ensure_ascii=False, indent=1)
        except Exception:
            pass
        text = self.app.src.get("1.0", "end").strip()
        if text:
            self.app.on_go()
    def apply_theme(self, name):
        # ThemeName persists to Appearance (native popup theming);
        # main-window bg follows for preview (native needs
        # EnableWindowStyle for full chrome theming).
        try:
            from qtranslate import config as _C
            import json as _j
            full = _C.load()
            full.setdefault("Appearance", {})["ThemeName"] = name
            with open(_C.DEFAULT_PATH, "w",
                      encoding="utf-8") as f:
                _j.dump(full, f, ensure_ascii=False, indent=1)
        except Exception:
            pass
        try:
            from qtranslate.theme import load_theme, tk_colors, window_colors
            global _COLORS
            _COLORS = tk_colors(window_colors(load_theme(name)))
            self.app.root.configure(bg=_COLORS["back"])
        except Exception:
            pass
    def current(self):
        return (self.app.service,
                self.app.src.get("1.0", "end").strip(),
                LANG_CODES.get(self.app.tgt.get().strip(), "vi"),
                LANG_CODES.get(self.app.src_lang.get().strip(), "auto"))
    @staticmethod
    def tag_links(widget, text, on_click):
        """Shared auto-URL tagger (native EM_AUTOURLDETECT): qtdp: +
        http links, blue/underline/hand-cursor.

        A STATICMETHOD on purpose: the body was a module-level function
        that took the widget to tag as its first argument, and the Phase
        7 split moved it into the class without changing that. Left as a
        plain method, `instance.tag_links(widget, ...)` would bind the
        INSTANCE as the widget and tag the MainWindow instead of the
        text pane.
        """
        import re as _re
        try:
            widget.tag_delete("link")
        except Exception:
            pass
        try:
            widget.tag_config("link", foreground="blue",
                              underline=True)
            widget.tag_bind("link", "<Button-1>", on_click)
            widget.tag_bind("link", "<Enter>",
                            lambda e: widget.config(cursor="hand2"))
            widget.tag_bind("link", "<Leave>",
                            lambda e: widget.config(cursor=""))
            for m in _re.finditer(
                    r"(qtdp:\S+|https?://\S+|www\.\S+)", text):
                s, e = m.span()
                widget.tag_add("link", f"1.0+{s}c", f"1.0+{e}c")
        except Exception:
            pass
    def render(self, text, back=""):
        """Fill the result pane (1017) and the back-translation pane (1018).

        DLG129 has THREE RichEdits, and the three `Contents` keys map 1:1 onto
        them in order: `EditSource`->1000, `EditTranslation`->1017,
        `EditBackTranslation`->1018
        (`D10_SPOTCHECK_Contents_2026-10-10.md` §2: three adjacent string
        fields at `+0x174`/`+0x178`/`+0x17c`). So the back-translation is its
        own CONTROL, not a section concatenated into the result pane.

        ``back`` is the back-translation segment. A single-argument call
        still splits a combined string on the port's old separator, so
        existing callers keep working -- but new code should pass the two
        segments separately, and the separator is no longer needed.
        """
        if back == "" and BACKTR_MARKER in (text or ""):
            text, back = text.split(BACKTR_MARKER, 1)
        self.app.out.delete("1.0", "end")
        self.app.out.insert("1.0", text or "")
        self.app.tag_links(self.app.out, text or "", self.app._click_link)
        # The aux pane exists only where native's does; on a port build
        # without it the segment is dropped rather than concatenated back in.
        if getattr(self.app, "aux", None) is not None:
            self.app.aux.delete("1.0", "end")
            self.app.aux.insert("1.0", (back or "").strip())
            self.app.tag_links(self.app.aux, (back or "").strip(), self.app._click_link)
            # Native shows the third pane only when it has something to
            # show: its capture has the separator (1135) and no pane.
            self._set_aux_visible(bool((back or "").strip()))
    def _set_aux_visible(self, visible):
        """Show or hide DLG129's third pane (1018).

        Native's capture (2131) shows the separator 1135 and a ZERO-height
        third pane -- the RichEdit is collapsed when there is no
        back-translation -- so the port's always-visible 16px empty band
        was a divergence from the native's own pixels.
        """
        try:
            auxfrm = (self.app._panes or {}).get("aux")
            if auxfrm is None:
                return
            if visible:
                if auxfrm.winfo_manager() != "pack":
                    # `before=` needs a reference that is MANAGED by the
                    # same manager; the service strip can be hidden
                    # (General.ShowServicesPane), and the TclError would
                    # be swallowed -- leaving the pane packed nowhere.
                    _ref = self.app._panes.get("svc")
                    if _ref is not None and _ref.winfo_manager() == "pack":
                        auxfrm.pack(fill="both", expand=False, padx=4,
                                    before=_ref)
                    else:
                        auxfrm.pack(fill="both", expand=False, padx=4)
            elif auxfrm.winfo_manager() == "pack":
                auxfrm.pack_forget()
        except Exception:
            pass
    def _set_suggest_text(self, text):
        """Show or hide the suggestion line.

        Native has no permanent suggestion band: the capture (2131) shows
        the main window with no such row, so the label is packed only
        while it carries a suggestion. Packing it unconditionally left a
        17px empty grey band under the tool row.
        """
        lbl = getattr(self.app, "suggest", None)
        if lbl is None:
            return
        try:
            if text:
                lbl.config(text=text)
                if lbl.winfo_manager() != "pack":
                    _before = (self.app._panes or {}).get("mid")
                    if _before is not None \
                            and _before.winfo_manager() == "pack":
                        lbl.pack(fill="x", padx=4, pady=0, before=_before)
                    else:
                        lbl.pack(fill="x", padx=4, pady=0)
            else:
                lbl.config(text="")
                if lbl.winfo_manager() == "pack":
                    lbl.pack_forget()
        except Exception:
            pass
    def _apply_backtr_split(self, text):
        """DEPRECATED -- kept only so an old caller does not crash.

        This method used to simulate a splitter *inside* the result pane,
        because its comment asserted "DLG129 has 17 ctls total, only one
        result pane". That is false: DLG129 has THREE RichEdits (1000, 1017,
        1018) and the back-translation has its own control, so the splitter
        widget this built was solving a problem native does not have.

        `render()` now writes the two segments to their own panes. The
        `General.BackTranslationSplitterPos` option is still read and
        written, because native stores the key and D10 spot-check §1/§3 shows
        it round-trips -- it scrolls the AUX pane rather than the result one.

        No behavior depends on this method any more; it returns without
        touching anything.
        """
        return
    def _click_link_dict(self, widget, event=None):
        try:
            idx = widget.index(f"@{event.x},{event.y}")
            ranges = widget.tag_ranges("link")
            for i in range(0, len(ranges), 2):
                if widget.compare(ranges[i], "<=", idx) and \
                        widget.compare(idx, "<=", ranges[i + 1]):
                    url = widget.get(ranges[i], ranges[i + 1])
                    if not url.startswith("qtdp:"):
                        _open_url(url)
                    break
        except Exception:
            pass
    def _click_link(self, event=None):
        try:
            idx = self.app.out.index(f"@{event.x},{event.y}")
            ranges = self.app.out.tag_ranges("link")
            for i in range(0, len(ranges), 2):
                if self.app.out.compare(ranges[i], "<=", idx) and \
                        self.app.out.compare(idx, "<=", ranges[i + 1]):
                    url = self.app.out.get(ranges[i], ranges[i + 1])
                    if url.startswith("qtdp:"):
                        word = url[5:]
                        self.app.src.delete("1.0", "end")
                        self.app.src.insert("1.0", word)
                        self.app.open_dict_window()
                    else:
                        _open_url(url)
                    break
        except Exception:
            pass
    def on_swap(self):
        a, b = self.app.src_lang.get(), self.app.tgt.get()
        if LANG_CODES.get(a, "auto") != "auto":
            self.app.tgt.set(a)
        self.app.src_lang.set(b if b else LANG_DISPLAY.get("auto", "auto"))
        self.app._persist_langs(
            LANG_CODES.get(self.app.src_lang.get().strip(), "auto"),
            LANG_CODES.get(self.app.tgt.get().strip(), "vi"))
    def toggle_multi_service(self, name):
        """Right-click: add/remove service from the multi-select set."""
        if name in self.app.multi_services:
            self.app.multi_services.discard(name)
        else:
            self.app.multi_services.add(name)
        self.app._mark_service()
    def on_go(self):
        svc, text, tgt, src = self.app.current()
        targets = [s for s in self.app.ordered_services()
                   if s in self.app.multi_services] or [svc]
        if len(targets) == 1:
            res = do_translate(targets[0], text, tgt, src,
                               self.app.opt_detect.get(),
                               self.app.opt_backtr.get())
            self.app.render(res.text)
            self.app.push_hist(targets[0], text[:120], res.text[:200])
        else:
            import threading as _th

            def _work():
                parts = []
                for s in targets:
                    try:
                        r = do_translate(s, text, tgt, src,
                                         self.app.opt_detect.get(),
                                         self.app.opt_backtr.get())
                    except Exception as e:
                        # do_translate returns core.Result since 5f18daa, so
                        # the failure branch must build one too — assigning a
                        # bare str here made the very next line (`r.text`)
                        # raise AttributeError on the multi-service path.
                        from qtranslate.core import Result
                        r = Result(s, f"[error] {e}", s,
                                   note="exception before translate")
                    parts.append(f"===== {s} =====\n{r.text}")
                    try:
                        self.app.push_hist(s, text[:120], r.text[:200])
                    except Exception:
                        pass
                combined = "\n\n".join(parts)
                try:
                    self.app.root.after(
                        0, lambda: self.app.render(combined))
                except Exception:
                    pass

            self.app.render(f"translating via {len(targets)} services...")
            _th.Thread(target=_work, daemon=True).start()
            return
        # AutoCleanupOfTranslation: clear the source pane after a
        # successful translate (native 0x8077).
        try:
            from qtranslate import config as _C
            if _C.load().get("General", {}).get(
                    "AutoCleanupOfTranslation", False) and res \
                    and not res.text.startswith("No data"):
                self.app.src.delete("1.0", "end")
        except Exception:
            pass
    def on_clear(self):
        """Ctrl+N => Clear current translation (per help.txt)."""
        self.app.render("")
    def on_listen(self):
        txt = self.app.out.get("1.0", "end").strip()
        if not txt:
            return
        _, _, tgt, _ = self.app.current()
        threading.Thread(target=speak, args=(txt[:500], tgt),
                         daemon=True).start()
    def on_copy(self):
        if _HAS_KEYS:
            pyperclip.copy(self.app.out.get("1.0", "end").strip())
    def on_layout(self):
        from qtranslate.layout import convert_layout
        txt = self.app.src.get("1.0", "end").strip()
        if not txt and _HAS_KEYS:
            txt = pyperclip.paste()
        fixed = convert_layout(txt)
        self.app.src.delete("1.0", "end")
        self.app.src.insert("1.0", fixed)
        if _HAS_KEYS:
            pyperclip.copy(fixed)
    def on_type(self):
        # Suggest menu (Ctrl+Space shows it; auto-fill honors
        # General.SpellChecking like the native edit control) +
        # Instant translation (General.InstantTranslation, native
        # 0x802C): debounced re-translate on every keystroke.
        try:
            from qtranslate import config as _C
            _g = _C.load().get("General", {})
            _spell_on = _g.get("SpellChecking", True)
            _instant = _g.get("InstantTranslation", False)
        except Exception:
            _spell_on, _instant = True, False
        cur = self.app.src.get("1.0", "end").strip()
        if _instant and len(cur) >= 2:
            try:
                if getattr(self.app, "_instant_after", None):
                    self.app.root.after_cancel(self.app._instant_after)
            except Exception:
                pass
            try:
                self.app._instant_after = self.app.root.after(
                    600, self.app.on_go)
            except Exception:
                pass
        if not _spell_on:
            return
        if len(cur) < 3 or len(cur) > 60:
            return
        try:
            from qtranslate import registry as _RG
            sug = _RG.google_suggest(cur)
            self.app._suggestions = list(sug[:5])
            self._set_suggest_text(" | ".join(self.app._suggestions))
        except Exception:
            pass
    def accept_suggestion(self):
        """Ctrl+Space: accept the first suggestion into the source pane
        (native suggestion/autocomplete menu, help.txt)."""
        try:
            sug = getattr(self.app, "_suggestions", [])
            if sug:
                self.app.src.delete("1.0", "end")
                self.app.src.insert("1.0", sug[0])
                self._set_suggest_text("")
                self.app._suggestions = []
        except Exception:
            pass
    def show_hotkeys(self):
        try:
            from qtranslate import config as C
            doc = C.DEFAULT_HOTKEY_DOC
        except Exception:
            doc = ("Double Ctrl => Show main window; Ctrl+Q => popup; "
                   "Ctrl+Shift+Q => dictionary; Ctrl+E => listen; "
                   "Ctrl+Enter => translate; Ctrl+N => clear")
        self.app.render("Hotkeys (from Locales/English/help.txt):\n" + doc)
    def show_about(self):
        # DLG 133: About + OK + 2 SysLinks (homepage, services credit).
        w = tk.Toplevel(self.app.root)
        w.title(_W(4, "About"))
        w.configure(bg=_COLORS["back"])
        w.geometry("360x200")
        tk.Label(w, text="QTranslate Version 6.10.0",
                 bg=_COLORS["back"], fg=_COLORS["text"],
                 font=("Segoe UI", 11, "bold")).pack(pady=(12, 2))
        tk.Label(w, text="qtranslate-re — clean-room RE\n"
                         f"{len(TRANSLATORS)} translate + {len(DICTS)} "
                         "dictionary providers",
                 bg=_COLORS["back"], fg=_COLORS["text"],
                 justify="center").pack(pady=2)

        def _link(url, text):
            lb = tk.Label(w, text=text, fg="blue", cursor="hand2",
                          bg=_COLORS["back"],
                          font=("Segoe UI", 9, "underline"))
            lb.pack()
            lb.bind("<Button-1>", lambda e: _open_url(url))

        _link("https://quest-app.appspot.com/",
              "QTranslate homepage")
        _link("https://quest-app.appspot.com/services",
              "Translation services")
        tk.Button(w, text="OK",
                  command=w.destroy).pack(pady=10)
    def show_override_conflicts(self):
        """D18: pick the winner when extensions collide (override UI).

        Loads the per-user extensions into a throwaway manager (isolated from
        the live registry), presents the conflicts, and saves the user's
        choice to Options.json. The saved winners pre-empt discovery-order
        resolution at the next startup.
        """
        try:
            from qtranslate.extensions import (
                ExtensionManager, write_saved_overrides)
            # `override_ui` is a MODULE (`qtranslate/override_ui.py`), not a
            # name in extensions.py -- importing it from there raised
            # ImportError, which the surrounding `except Exception: return`
            # swallowed, so this dialog silently never opened. Importing it
            # from its own module also lets PyInstaller's Analysis see the
            # dependency (a `from X import Y` where Y is a submodule is
            # invisible to a static import walk).
            from qtranslate import override_ui
            from qtranslate import platforms as _P
            ext_dir = _P.current().extensions_dir()
        except Exception:
            return
        manager = ExtensionManager()
        manager.load_dir(ext_dir)
        conflicts = manager.override_conflicts()
        if not conflicts:
            return
        winners = override_ui.pick_override_winners(self.app.root, conflicts)
        if winners:
            write_saved_overrides(winners)
    def on_ocr(self):
        # Default = ScreenCaptureWindow region select (native flow).
        self.app._ocr_region()
    def on_ocr_file(self):
        path = filedialog.askopenfilename(title="Image for OCR")
        if not path:
            return
        try:
            with open(path, "rb") as f:
                self.app._ocr_bytes(f.read())
        except Exception as e:
            self.app.render(f"[ocr error] {e}")
    def _ocr_bytes(self, data: bytes):
        from qtranslate.services.ocr import ocr_text
        try:
            from qtranslate import config as _C
            _cfg = _C.load()
            _key = _cfg.get("Advanced",
                            {}).get("OcrApiKey", "") or "helloworld"
            # Ocr.OcrLanguage = Google index (17=en default) -> ocr.space
            # code; Ocr.SaveImagePath archives the capture.
            _oi = _cfg.get("Ocr", {}).get("OcrLanguage", 17)
            try:
                _table = list(__import__(
                    "qtranslate.services.google_translate",
                    fromlist=["SUPPORTED_LANGS"]).SUPPORTED_LANGS)
            except Exception:
                _table = []
            _code = _table[_oi] if 0 <= _oi < len(_table) else "eng"
            # ocr.space's own 3-letter language codes, which the image
            # carries as one wide string: ara bul chs cht hrv cze dan dut
            # eng fin fre ger gre hun ita jpn kor nor pol por rus spa swe
            # tur (22 values, verified by tests/regress_ocr_languages.py).
            # Mapped from Google's 2-letter codes; an unmapped language
            # falls back to eng as native does for a language it lacks.
            _lang = {"en": "eng", "vi": "vie", "fr": "fre",
                     "de": "ger", "es": "spa", "ru": "rus",
                     "ja": "jpn", "ko": "kor",
                     "zh-CN": "chs", "zh-TW": "cht", "ar": "ara",
                     "bg": "bul", "hr": "hrv", "cs": "cze",
                     "da": "dan", "nl": "dut", "fi": "fin",
                     "el": "gre", "hu": "hun", "it": "ita",
                     "no": "nor", "pl": "pol", "pt": "por",
                     "sv": "swe", "tr": "tur",
                     "zh": "chs"}.get(_code, "eng")
            _savep = _cfg.get("Ocr", {}).get("SaveImagePath", "")
            if _savep:
                try:
                    import datetime as _dt
                    import os as _o
                    _fn = "ocr_%s.png" % _dt.datetime.now().strftime(
                        "%Y%m%d_%H%M%S")
                    open(_o.path.join(_savep, _fn), "wb").write(data)
                except Exception:
                    pass
        except Exception:
            _key, _lang = "helloworld", "eng"
        try:
            txt = ocr_text(data, api_key=_key, lang=_lang)
            self.app.src.delete("1.0", "end")
            self.app.src.insert("1.0", txt)
        except Exception as e:
            self.app.render(f"[ocr error] {e}")
    def _ocr_region(self):
        """Rubber-band screen region -> ImageGrab -> OCR (native
        ScreenCaptureWindow selection flow). Esc cancels."""
        try:
            from PIL import ImageGrab
        except ImportError:
            self.app.render("[ocr needs Pillow: pip install Pillow]")
            return
        ov = tk.Toplevel(self.app.root)
        ov.attributes("-fullscreen", True)
        ov.attributes("-alpha", 0.3)
        ov.configure(bg="gray")
        ov.attributes("-topmost", True)
        cv = tk.Canvas(ov, highlightthickness=0)
        cv.pack(fill="both", expand=True)
        _start = [None]
        _rect = [None]

        def _down(e):
            _start[0] = (e.x, e.y)
            _rect[0] = cv.create_rectangle(e.x, e.y, e.x, e.y,
                                           outline="red", width=2)

        def _drag(e):
            if _start[0] and _rect[0]:
                x0, y0 = _start[0]
                cv.coords(_rect[0], x0, y0, e.x, e.y)

        def _up(e):
            try:
                x0, y0 = _start[0]
                x1, y1 = e.x, e.y
                x, y = min(x0, x1), min(y0, y1)
                w, h = abs(x1 - x0), abs(y1 - y0)
                ov.destroy()
                if w < 5 or h < 5:
                    return
                sx, sy = ov.winfo_rootx() + x, ov.winfo_rooty() + y
                img = ImageGrab.grab(bbox=(sx, sy, sx + w, sy + h))
                import io as _io
                buf = _io.BytesIO()
                img.save(buf, format="PNG")
                import threading as _th
                _th.Thread(target=self.app._ocr_bytes,
                           args=(buf.getvalue(),),
                           daemon=True).start()
            except Exception as ex:
                self.app.render(f"[ocr error] {ex}")

        def _grab_png():
            # Current rubber-band rect -> PNG bytes (shared by OCR-send,
            # S-save, and C-copy so all three consume one capture path).
            try:
                x0, y0 = _start[0]
                x1, y1 = cv.coords(_rect[0])[:2], cv.coords(_rect[0])[2:]
                x, y = min(x0, x1), min(y0, y1)
                w, h = abs(x1 - x0), abs(y1 - y0)
                if w < 5 or h < 5:
                    return None
                sx, sy = ov.winfo_rootx() + x, ov.winfo_rooty() + y
                img = ImageGrab.grab(bbox=(sx, sy, sx + w, sy + h))
                import io as _io2
                buf = _io2.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()
            except Exception:
                return None

        def _keys(e):
            # Native overlay keys (FUN_004377CB): S = save-as
            # (FUN_0043845C), C = copy (FUN_004383A2), arrows adjust the
            # selection, Esc/Del close. Enter sends to OCR like release.
            ks = (e.keysym or "").lower()
            if ks == "escape":
                ov.destroy()
            elif ks == "delete":
                ov.destroy()
            elif ks in ("s", "c", "return"):
                data = _grab_png()
                ov.destroy()
                if not data:
                    return
                if ks == "s":
                    try:
                        import datetime as _dt
                        import os as _o
                        _dir = _o.path.expanduser("~")
                        try:
                            from qtranslate import config as _Cs
                            _dir = _Cs.load().get(
                                "Ocr", {}).get("SaveImagePath", "") or _dir
                        except Exception:
                            pass
                        _fn = "ocr_%s.png" % _dt.datetime.now().strftime(
                            "%Y%m%d_%H%M%S")
                        open(_o.path.join(_dir, _fn), "wb").write(data)
                    except Exception as ex:
                        self.app.render(f"[ocr error] {ex}")
                elif ks == "c":
                    # Native FUN_004383A2 copies the bitmap to the
                    # CLIPBOARD (not to a viewer): PNG bytes -> BMP/DIB
                    # via the clipboard. Pillow-only, no new dependency.
                    try:
                        import io as _io3
                        from PIL import Image as _Im
                        _im = _Im.open(_io3.BytesIO(data)).convert("RGB")
                        _out = _io3.BytesIO()
                        _im.save(_out, "BMP")
                        _dib = _out.getvalue()[14:]  # strip BMP header
                        import ctypes as _ct
                        _u = _ct.windll.user32
                        _u.OpenClipboard(None)
                        try:
                            _u.EmptyClipboard()
                            _h = _ct.windll.kernel32.GlobalAlloc(
                                0x0042, len(_dib))
                            _p = _ct.windll.kernel32.GlobalLock(_h)
                            _ct.memmove(_p, _dib, len(_dib))
                            _ct.windll.kernel32.GlobalUnlock(_h)
                            _u.SetClipboardData(8, _h)  # CF_DIB
                        finally:
                            _u.CloseClipboard()
                    except Exception as ex:
                        self.app.render(f"[ocr error] {ex}")
                else:
                    import threading as _th2
                    _th2.Thread(target=self.app._ocr_bytes, args=(data,),
                               daemon=True).start()
            elif ks.startswith("left"):
                _nudge(-1, 0)
            elif ks.startswith("right"):
                _nudge(1, 0)
            elif ks.startswith("up"):
                _nudge(0, -1)
            elif ks.startswith("down"):
                _nudge(0, 1)

        def _nudge(dx, dy):
            try:
                if _start[0] and _rect[0]:
                    x0, y0, x1, y1 = cv.coords(_rect[0])
                    cv.coords(_rect[0], x0 + dx, y0 + dy, x1 + dx, y1 + dy)
                    _start[0] = (x0 + dx, y0 + dy)
            except Exception:
                pass

        cv.bind("<Button-1>", _down)
        cv.bind("<B1-Motion>", _drag)
        cv.bind("<ButtonRelease-1>", _up)
        ov.bind("<Key>", _keys)
        ov.bind("<Escape>", lambda e: ov.destroy())
        ov.focus_force()
    def open_keyboard(self):
        """Virtual keyboard window (DLG 162: 308x102).

        Clicking a key types it into the source pane (like the native
        on-screen keyboard feeding the edit control). Key labels follow
        General.LanguageKeyboard via the JCUKEN map (17=en default).

        Native's DLG 162 declares only the language combo (1064) and a
        small static (1155) -- the KEY GRID is built at run time -- so the
        layout is transcribed from native's own capture
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

        The keys are LABELS, not buttons: a Tk button carries a platform
        minimum width (48 pixels for a two-character key on macOS, where
        native's is 29), so the keys would not fit native's layout. A
        label sizes to its text, and its padding is in pixels, so the
        widths below are native's own.
        """
        w = tk.Toplevel(self.app.root)
        w.title(_W(7, "Virtual keyboard"))
        w.configure(bg=_COLORS["back"])
        _applied = _place_aux(w, "WindowKeyboardPlacement",
                              _TEMPLATE_GEOMETRY("keyboard"))
        w.attributes("-topmost", True)
        try:
            from qtranslate import config as _C
            _kb = _C.load().get("General", {}).get(
                "LanguageKeyboard", LANG_DEFAULTS["LanguageKeyboard"])
        except Exception:
            _kb = 17
        try:
            from qtranslate.layout import EN2RU
        except Exception:
            EN2RU = {}
        _ru = [(_kb != 17)]
        _shift = [False]
        _caps = [False]
        _kf = ("Tahoma", 8)
        _font = tkfont.Font(family="Tahoma", size=8)

        def _type(ch):
            try:
                self.app.src.insert("insert", ch)
            except Exception:
                pass

        def _label(ch):
            """The key's glyph in the selected language."""
            if EN2RU and _ru[0] and len(ch) == 1:
                return EN2RU.get(ch, ch)
            return ch

        def _edit(fn):
            try:
                fn(self.app.src)
            except Exception:
                pass

        # (label, width in pixels, what it does)
        _SPEC = (
            (("Esc", 34, None), ("F1", 30, None), ("F2", 30, None),
             ("F3", 30, None), ("F4", 30, None), ("", 14, None),
             ("F5", 30, None), ("F6", 30, None), ("F7", 30, None),
             ("F8", 30, None), ("", 14, None),
             ("F9", 30, None), ("F10", 30, None), ("F11", 30, None),
             ("F12", 30, None)),
            (("`", 29, "char"), ("1", 29, "char"), ("2", 29, "char"),
             ("3", 29, "char"), ("4", 29, "char"), ("5", 29, "char"),
             ("6", 29, "char"), ("7", 29, "char"), ("8", 29, "char"),
             ("9", 29, "char"), ("0", 29, "char"), ("-", 29, "char"),
             ("=", 29, "char"), ("BkSp", 56, "back")),
            (("Tab", 44, "tab"), ("q", 29, "char"), ("w", 29, "char"),
             ("e", 29, "char"), ("r", 29, "char"), ("t", 29, "char"),
             ("y", 29, "char"), ("u", 29, "char"), ("i", 29, "char"),
             ("o", 29, "char"), ("p", 29, "char"), ("[", 29, "char"),
             ("]", 29, "char"), ("\\", 29, "char")),
            (("Caps", 52, "caps"), ("a", 29, "char"), ("s", 29, "char"),
             ("d", 29, "char"), ("f", 29, "char"), ("g", 29, "char"),
             ("h", 29, "char"), ("j", 29, "char"), ("k", 29, "char"),
             ("l", 29, "char"), (";", 29, "char"), ("'", 29, "char"),
             ("Enter", 64, "enter")),
            (("Shift", 62, "shift"), ("z", 29, "char"), ("x", 29, "char"),
             ("c", 29, "char"), ("v", 29, "char"), ("b", 29, "char"),
             ("n", 29, "char"), ("m", 29, "char"), (",", 29, "char"),
             (".", 29, "char"), ("/", 29, "char"), ("Shift", 68, "shift")),
            (("Ctrl", 40, None), ("Win", 34, None), ("Alt", 34, None),
             ("Space", 118, "space"), ("AltGr", 40, None), ("Apps", 40, None),
             ("^", 29, "up"), ("v", 29, "down"), ("<", 29, "left"),
             (">", 29, "right")),
        )
        _rows = []
        _key_labels = []          # (label widget, the Latin character)
        for _row in _SPEC:
            frm = tk.Frame(w, bg=_COLORS["back"])
            frm.pack()
            _rows.append(frm)
            for _lbl, _wd, _kind in _row:
                if _kind == "char":
                    # The SHIFTED character goes through the layout map
                    # too: `EN2RU` carries the uppercase mirrors, so a
                    # Cyrillic layout types Cyrillic capitals.
                    _cmd = (lambda c=_lbl: _type(
                        _label(c.upper()) if (_shift[0] or _caps[0])
                        else _label(c)))
                elif _kind == "space":
                    _cmd = lambda: _type(" ")
                elif _kind == "back":
                    _cmd = lambda: _edit(
                        lambda t: t.delete("insert-1c", "insert"))
                elif _kind == "enter":
                    _cmd = lambda: _type("\n")
                elif _kind == "tab":
                    _cmd = lambda: _type("\t")
                elif _kind == "caps":
                    _cmd = lambda: _caps.__setitem__(0, not _caps[0])
                elif _kind == "shift":
                    _cmd = lambda: _shift.__setitem__(0, not _shift[0])
                elif _kind == "up":
                    _cmd = lambda: _edit(lambda t: t.mark_set(
                        "insert", "insert lineup"))
                elif _kind == "down":
                    _cmd = lambda: _edit(lambda t: t.mark_set(
                        "insert", "insert linedown"))
                elif _kind == "left":
                    _cmd = lambda: _edit(lambda t: t.mark_set(
                        "insert", "insert -1 chars"))
                elif _kind == "right":
                    _cmd = lambda: _edit(lambda t: t.mark_set(
                        "insert", "insert +1 chars"))
                else:
                    _cmd = lambda: None
                if not _lbl:
                    # a gap between the function-key groups, as in native
                    tk.Frame(frm, bg=_COLORS["back"], width=_wd).pack(
                        side="left", padx=1, pady=1)
                    continue
                _padx = max(1, (_wd - _font.measure(_lbl)) // 2)
                lb = tk.Label(frm, text=_lbl, font=_kf, bg=_COLORS["back"],
                              fg=_COLORS["text"], relief="raised",
                              borderwidth=1, padx=_padx, pady=5,
                              cursor="hand2")
                lb.pack(side="left", padx=1, pady=1)
                lb.bind("<Button-1>", lambda e, c=_cmd: c())
                if _kind == "char":
                    _key_labels.append((lb, _lbl))

        # 1064: the language combo, bottom-left, as in native's capture.
        _row = tk.Frame(w, bg=_COLORS["back"])
        _row.pack(anchor="w", padx=2, pady=2)
        try:
            from qtranslate.services.google_translate import SUPPORTED_LANGS \
                as _SL
            _names = [LANG_DISPLAY.get(c, c) for c in _SL]
        except Exception:
            _names = []
        _combo = ttk.Combobox(_row, values=list(_names), width=24,
                              state="readonly", font=_kf)
        try:
            _combo.set(_names[_kb] if 0 <= _kb < len(_names)
                       else (_names[0] if _names else ""))
        except Exception:
            pass
        _combo.pack(side="left")

        def _relabel():
            """Re-label the letter keys for the selected language."""
            for _w, _c in _key_labels:
                try:
                    _w.config(text=_label(_c))
                except Exception:
                    pass

        def _on_language(_e=None):
            name = _combo.get()
            try:
                idx = _names.index(name)
            except ValueError:
                idx = 17
            _ru[0] = (idx != 17)
            _relabel()
            self._keyboard_language(name, _names)

        _combo.bind("<<ComboboxSelected>>", _on_language)
        # Native's keyboard window is sized to its runtime key grid, not to
        # the template (the capture is 464x198 where the template
        # converts to 539x191). A SAVED placement still wins.
        if not _applied:
            try:
                w.update_idletasks()
                _gw = max(f.winfo_reqwidth() for f in _rows)
                w.geometry("%dx%d" % (_gw, w.winfo_reqheight()))
            except Exception:
                pass
        return w

    def _keyboard_language(self, name, names):
        """Persist the keyboard's language and switch the key labels."""
        try:
            from qtranslate import config as _C
            import json as _j
            full = _C.load()
            idx = names.index(name) if name in names else 17
            full.setdefault("General", {})["LanguageKeyboard"] = idx
            with open(_C.DEFAULT_PATH, "w", encoding="utf-8") as f:
                _j.dump(full, f, ensure_ascii=False, indent=1)
        except Exception:
            pass
