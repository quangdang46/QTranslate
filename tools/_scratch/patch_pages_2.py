"""Rewrite the remaining Options pages to native's DLGs (2026-10-21).

Second half of the DLG174/175 batch: the pages whose STRUCTURE, not
just their labels, was wrong.

* **Services (DLG173)** -- native has ONE list with two group headers
  ("Translation", "Dictionary"), each row a checkbox + the service icon,
  and TWO small buttons plus 'Add dictionary...' / 'Remove dictionary'.
  The port had two separate listboxes with 'On/Off' and 'All' buttons --
  neither of which native has -- and, worse, the lists were EMPTY on a
  fresh config, because they were filled from `ServicesOrder` alone and
  that key is absent until the user reorders something. The page looked
  broken.
* **Exceptions (DLG176)** -- native has a MODE COMBO (1162, "Disabled
  for these programs:") over ONE list (1104) with Add/Modify/Delete.
  The port had two lists (Blocked / Allowed), i.e. the combo's two
  states drawn as two lists.
* **Advanced (DLG185)** -- native has three group boxes ('Advanced',
  'Mouse mode', 'API keys'), four COMBOBOXES at the top, three radios,
  and the OCR API key + link in their own group. The port drew a flat
  list of five checkboxes and ten text entries, two of them duplicated
  (the same config key under two labels), and the page overflowed its
  window so the Apply button was pushed off the bottom.
* **Updates (DLG205)** -- native has 'Automatically check for updates',
  a RichEdit changelog area, 'Check now' and 'Install'. The port had a
  checkbutton and a static label.
"""

from __future__ import annotations

from pathlib import Path

WIN = Path("qtranslate/windows.py")

SERVICES = '''        def show_services():
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

            def _icon(name):
                try:
                    import os as _os
                    from PIL import Image as _I  # noqa: F401
                except Exception:
                    pass
                try:
                    _p = _os.path.join(_os.path.dirname(
                        _os.path.abspath(__file__)), "assets",
                        "service_icons", name + ".png")
                    if not _os.path.exists(_p):
                        return ""
                    return tk.PhotoImage(file=_p)
                except Exception:
                    return ""

            def _fill():
                for _it in _tv.get_children(""):
                    _tv.delete(_it)
                del _rows[:]
                for _i in _order:
                    _n = _names.get(_i, "id:%s" % _i)
                    _on = _i not in _dis
                    _it = _tv.insert(_g_t, "end",
                                     text=("\\u2611 " if _on else "\\u2610 ")
                                     + _n, image=_icon(_n.lower()))
                    _rows.append((_it, _i, False, _dis))
                for _i in _dorder:
                    _n = _dnames.get(_i, "id:%s" % _i)
                    _on = _i not in _ddis
                    _it = _tv.insert(_g_d, "end",
                                     text=("\\u2611 " if _on else "\\u2610 ")
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
            tk.Button(_br, text="\\u25b2", width=3,
                      command=lambda: _move(-1)).pack(side="left", padx=1)
            tk.Button(_br, text="\\u25bc", width=3,
                      command=lambda: _move(1)).pack(side="left", padx=1)
            tk.Button(_br, text=_Cw(12, 1177, "Add dictionary..."),
                      command=lambda: _add_dict()).pack(side="left", padx=6)
            tk.Button(_br, text=_Cw(12, 1180, "Remove dictionary"),
                      command=_remove_dict).pack(side="left", padx=1)

'''

EXCEPTIONS = '''        def show_exceptions():
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

            _MODE_D = _Cw(15, 1162, "Disabled for these programs:")
            _MODE_E = _Cw(15, 1163, "Enabled for these programs:")
            _mode = tk.StringVar(value=_MODE_D)

            def _pairs():
                return _dis_list if _mode.get() == _MODE_D else _en_list

            _r = tk.Frame(body, bg=_COLORS["back"])
            _r.pack(fill="x")
            _cb = ttk.Combobox(_r, values=[_MODE_D, _MODE_E], width=48,
                               state="readonly")
            _cb.pack(side="left")
            _cb.set(_MODE_D)
            _cb.bind("<<ComboboxSelected>>",
                     lambda e: (_mode.set(_cb.get()), _refresh()))

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

            _fr = tk.Frame(body, bg=_COLORS["back"])
            _fr.pack(fill="x")
            _er = tk.Entry(_fr, width=16)
            _er.pack(side="left", padx=1)
            _er.insert(0, "exe or empty")
            _cr = tk.Entry(_fr, width=16)
            _cr.pack(side="left", padx=1)
            _cr.insert(0, "class or empty")

            def _add():
                _exe = _er.get().strip()
                _cls = _cr.get().strip()
                if _exe == "exe or empty":
                    _exe = ""
                if _cls == "class or empty":
                    _cls = ""
                _pairs().append([_exe, _cls])
                _refresh()
                _save_x()

            def _modify():
                _s = _lb.curselection()
                if not _s:
                    return
                _i = _s[0]
                _exe = _er.get().strip()
                _cls = _cr.get().strip()
                if _exe in ("", "exe or empty"):
                    _exe = _pairs()[_i][0]
                if _cls in ("", "class or empty"):
                    _cls = _pairs()[_i][1]
                _pairs()[_i] = [_exe, _cls]
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

'''

ADVANCED = '''        def show_advanced():
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

            def _set(key, value):
                _ad2[key] = value
                _save_a()

            adv = _group(body, 17, 1146, "Advanced")
            for cid, key, vals in (
                    (1151, "DefaultBrowserId",
                     ["Internet Explorer", "Firefox", "Chrome", "Opera",
                      "Safari", "Edge", ""]),
                    (1147, "CopyAction",
                     ["Ctrl + C", "Ctrl + Shift + C", "Ctrl + Insert", ""]),
                    (1149, "LayoutIndicator", ["None", "JCUKEN", ""]),
                    (1157, "GoogleDomain", ["com", "co.uk", "de", "fr",
                                            "co.jp", ""])):
                _w = _row(adv, 17, cid, "", value=_ad2.get(key, ""),
                          width=26, values=vals, label_width=26)
                _w.bind("<<ComboboxSelected>>",
                        lambda e, k=key, w=_w: _set(k, w.get()))
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

'''

UPDATES = '''        def show_updates():
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

'''


def replace_block(text: str, start: str, end: str, new: str) -> str:
    i = text.index(start)
    j = text.index(end, i)
    return text[:i] + new + text[j:]


def main() -> int:
    src = WIN.read_text(encoding="utf-8")
    src = replace_block(src, "        def show_services():",
                        "        def show_languages():", SERVICES)
    src = replace_block(src, "        def show_exceptions():",
                        "        def show_advanced():", EXCEPTIONS)
    src = replace_block(src, "        def show_advanced():",
                        "        def show_updates():", ADVANCED)
    src = replace_block(src, "        def show_updates():",
                        "        def on_select(_e=None):", UPDATES)
    WIN.write_text(src, encoding="utf-8")
    print("patched", WIN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
