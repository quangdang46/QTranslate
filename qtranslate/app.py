"""Runnable clone of the QTranslate main window (Windows).

Faithful to DLG 129 in QTranslate.exe `.rsrc` (340x201, 17 controls):
  - service icon row (custom Dl control id108 — here as small buttons
    with service names; same function: click = switch + re-translate,
    cf. FUN_0045CDBA service switcher)
  - source RichEdit (id1017) / result RichEdit (id1018) with separator
    statics (id1134/1135)
  - lang row: src ComboBox (id1001) + swap `<` (id1015) + tgt ComboBox
    (id1002) + Translate (id1004)
  - small buttons: Favorites/Speech/Play icons (id1027-1030) -> Listen
  - menus mirror RT_MENU resources (tray/history/options/edit)

Features that live in OTHER original windows stay in other windows:
  - History window (DLG 164) -> History menu (list + export, FUN_004287B6)
  - Dictionary window (DLG 184) -> Tools menu (multi-service cards)
  - Options (DLG 154) -> Options menu (theme, Detect, BackTr toggles)
  - OCR, layout fix -> Tools menu + hotkeys (documented in help.txt)

Pipeline mirrors native Task chain in docs/NATIVE_ARCH.md.
Hotkeys: Ctrl+Alt+Q translate clipboard, Ctrl+Alt+L fix layout.

Requires: pip install keyboard pyperclip
  python -I qtranslate/app.py [service] [target_lang] [theme]
  (or: python -I start_app.py ...)
"""
import sys
import threading
import tkinter as tk
from tkinter import filedialog, ttk

sys.path.insert(0, ".")

try:
    import keyboard
    import pyperclip
    _HAS_KEYS = True
except ImportError:
    _HAS_KEYS = False

from qtranslate.services import google_translate as _google
from qtranslate.services import deepl as _deepl
from qtranslate.services import yandex as _yandex
from qtranslate.services import baidu as _baidu
from qtranslate.services import naver as _naver
from qtranslate.services import youdao as _youdao
from qtranslate.services import microsoft as _ms
from qtranslate.services import promt as _promt
from qtranslate.services import dictionary as _dict
from qtranslate.services import spell as _spell
from qtranslate.session import bing_translate as _bing_tr

SERVICE = sys.argv[1] if len(sys.argv) > 1 else "google"
TARGET = sys.argv[2] if len(sys.argv) > 2 else "vi"
THEME = sys.argv[3] if len(sys.argv) > 3 else "Flat Dark"

try:
    from qtranslate.theme import load_theme, window_colors, list_themes
    _COLORS = window_colors(load_theme(THEME))
    _THEMES = list_themes()
except Exception:
    _COLORS = {"back": "#202020", "text": "#bbbbbb", "border": "#333333"}
    _THEMES = [THEME]

LANGS = ["auto", "en", "ru", "fr", "de", "es", "zh-CHS", "vi", "ja", "ko"]
TO_LANGS = ["vi", "en", "ru", "fr", "de", "es", "zh-CHS", "ja", "ko"]


def _strip_html(h):
    import html as _html
    import re
    h = re.sub(r"<script.*?</script>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<style.*?</style>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<[^>]+>", " ", h)
    return _html.unescape(re.sub(r"\s+", " ", h)).strip()


# ------------------------------------------------------- service registry
def _t_google(t, sl, tl):
    return _google.translate(t, "auto", tl)


def _t_deepl(t, sl, tl):
    # Native sends codeFromLanguage(index); "auto" must stay lowercase.
    sl_c = "auto" if sl == "auto" else sl.upper()
    return _deepl.translate(t, sl_c, tl.upper())


def _t_yandex(t, sl, tl):
    return _yandex.translate(t, "en" if sl == "auto" else sl, tl)


def _t_baidu(t, sl, tl):
    return _baidu.translate(t, sl, tl) if hasattr(_baidu, "translate") else ""


def _t_naver(t, sl, tl):
    out, _ = _naver.translate(t, sl, tl)
    return out


def _t_youdao(t, sl, tl):
    return _youdao.translate_web(t, "en" if sl == "auto" else sl, tl)


def _t_bing(t, sl, tl):
    return _bing_tr(t, "en" if sl == "auto" else sl, tl)


def _t_reverso(t, sl, tl):
    return _dict.reverso_translate(t, "en" if sl == "auto" else sl, tl)


def _t_promt(t, sl, tl):
    try:
        paft, xsrf, op = _promt.session(sl, tl)
        out, _, _ = _promt.translate(t, sl, tl, paft, "", xsrf, op)
        return out
    except Exception as e:
        return f"[error] {e}"


TRANSLATORS = {
    "google": _t_google,
    "deepl": _t_deepl,
    "yandex": _t_yandex,
    "baidu": _t_baidu,
    "naver": _t_naver,
    "youdao": _t_youdao,
    "bing": _t_bing,
    "microsoft": _t_bing,
    "promt": _t_promt,
    "reverso": _t_reverso,
}

DICTS = {
    "oxford": lambda w, sl, tl: _dict.oxford_lookup(w),
    "lingvo": lambda w, sl, tl: _dict.lingvo_lookup(w, sl, tl),
    "urban": lambda w, sl, tl: _dict.urban_lookup(w),
    "wikipedia": lambda w, sl, tl: _dict.wikipedia_lookup(w, sl, tl),
    "multitran": lambda w, sl, tl: _dict.multitran_lookup(
        w, {"en": 1, "ru": 2}.get(sl, 1), {"en": 1, "ru": 2}.get(tl, 2)),
    "wordreference": lambda w, sl, tl: _dict.wordreference_lookup(w, sl, tl),
    "reverso": lambda w, sl, tl: _dict.reverso_lookup(w, sl, tl),
    "babylon": lambda w, sl, tl: _dict.babylon_lookup(w, sl, tl),
    "imtranslator": lambda w, sl, tl: _dict.imtranslator_lookup(w, sl, tl),
    "google-search": lambda w, sl, tl: _dict.google_search_lookup(w, sl, tl),
}


# ------------------------------------------------------------ backend ops
def detect_language(text):
    """Port of FUN_00460354 detect-retry loop: providers in order.

    detect() across providers returns mixed types (DeepL/Yandex return
    lang indices like the native languageFromCode; Naver/Baidu return
    code strings), so normalize everything to a code string here.
    """
    candidates = (
        lambda t: _deepl.detect_code(t),
        lambda t: _naver.detect_code(t),
        lambda t: _baidu.detect_code(t),
        lambda t: _yandex.detect_code(t),
    )
    for fn in candidates:
        try:
            lang = fn(text[:500])
            if lang and lang != -1:
                return lang
        except Exception:
            pass
    return "auto"


def speak(text, lang):
    """Online mp3 -> BASS; on failure fall back to offline SAPI."""
    try:
        from qtranslate.player import play_text
        play_text(text, lang)
    except Exception as e:
        print(f"TTS failed ({e}); trying SAPI")
        try:
            from qtranslate.sapi import speak as sapi_speak
            sapi_speak(text)
        except Exception as e2:
            print(f"SAPI failed: {e2}")


def do_translate(service, text, target, src="auto", auto_detect=False,
                 back_translate=False):
    """Mirrors FUN_00404A12 orchestrator: pick -> execute -> fallbacks."""
    text = (text or "").strip()
    if not text:
        return ""
    fn = TRANSLATORS.get(service, _t_google)
    try:
        if auto_detect:
            src = detect_language(text)
        out = fn(text[:5000], src, target) or "[empty]"
        if back_translate and out and not out.startswith("["):
            try:
                back = fn(out[:5000], target,
                           "en" if src == "auto" else src)
                if back:
                    out += f"\n\n--- back-translation ---\n{back}"
            except Exception:
                pass
        return out
    except Exception as e:
        return f"[error] {e}"


# ------------------------------------------------------------------ UI
class App:
    """Main window — mirrors DLG 129 (340x201, 17 controls)."""

    def __init__(self, root):
        self.root = root
        self.service = SERVICE if SERVICE in TRANSLATORS else "google"
        self.target = TARGET
        self.source = "auto"
        self.history = []  # (service, src, result)
        root.title("QTranslate-re")
        root.attributes("-topmost", True)
        root.configure(bg=_COLORS["back"])
        root.geometry("680x420")
        self._build_menu()
        self._build_main()

    # -- DLG 129 body --
    def _build_main(self):
        bg = _COLORS["back"]
        # service icon row (Dl control id108 stand-in: one button/service;
        # click = FUN_0045CDBA switch + re-run FUN_0043A121)
        svcbar = tk.Frame(self.root, bg=bg)
        svcbar.pack(fill="x", padx=6, pady=(6, 2))
        self.svc_btns = {}
        for name in sorted(TRANSLATORS):
            b = tk.Button(svcbar, text=name[:6], width=7,
                          command=lambda n=name: self.switch_service(n))
            b.pack(side="left", padx=1)
            self.svc_btns[name] = b
        self._mark_service()
        # source RichEdit (id1017)
        self.src = tk.Text(self.root, height=5, wrap="word", bg=bg,
                           fg=_COLORS["text"],
                           insertbackground=_COLORS["text"])
        self.src.pack(fill="x", padx=8)
        self.src.bind("<KeyRelease>", lambda e: self.on_type())
        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=8,
                                                           pady=4)
        # lang row: src combo (id1001) + swap `<` (id1015) +
        # tgt combo (id1002) + Translate (id1004)
        langrow = tk.Frame(self.root, bg=bg)
        langrow.pack(fill="x", padx=8)
        self.src_lang = ttk.Combobox(langrow, values=LANGS, width=9)
        self.src_lang.set("auto")
        self.src_lang.pack(side="left", padx=2)
        tk.Button(langrow, text="<", width=3,
                  command=self.on_swap).pack(side="left", padx=2)
        self.tgt = ttk.Combobox(langrow, values=TO_LANGS, width=9)
        self.tgt.set(self.target)
        self.tgt.pack(side="left", padx=2)
        tk.Button(langrow, text="Translate",
                  command=self.on_go).pack(side="left", padx=6)
        # small icon buttons (id1027-1030: Favorites/Speech/Play)
        tk.Button(langrow, text="Listen",
                  command=self.on_listen).pack(side="left", padx=2)
        tk.Button(langrow, text="Copy",
                  command=self.on_copy).pack(side="left", padx=2)
        self.suggest = tk.Label(self.root, text="", bg=bg, fg="gray",
                                anchor="w")
        self.suggest.pack(fill="x", padx=8)
        # result RichEdit (id1018)
        self.out = tk.Text(self.root, height=10, wrap="word", bg=bg,
                           fg=_COLORS["text"],
                           insertbackground=_COLORS["text"],
                           font=("Segoe UI", 12))
        self.out.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.root.bind("<Control-Return>", lambda e: self.on_go())

    # -- menus mirror RT_MENU resources --
    def _build_menu(self):
        mb = tk.Menu(self.root)
        self.root.config(menu=mb)
        m_file = tk.Menu(mb, tearoff=False)
        m_file.add_command(label="Export history...",
                           command=self.on_export_history)
        m_file.add_separator()
        m_file.add_command(label="Exit", command=self.root.destroy)
        mb.add_cascade(label="File", menu=m_file)
        m_tools = tk.Menu(mb, tearoff=False)
        m_tools.add_command(label="Dictionary window",
                            command=self.open_dict_window)
        m_tools.add_command(label="Fix keyboard layout",
                            command=self.on_layout)
        m_tools.add_command(label="OCR from image file...",
                            command=self.on_ocr)
        m_tools.add_separator()
        m_tools.add_command(label="Listen to result",
                            command=self.on_listen)
        mb.add_cascade(label="Tools", menu=m_tools)
        m_hist = tk.Menu(mb, tearoff=False)
        m_hist.add_command(label="Show history window",
                           command=self.open_history_window)
        m_hist.add_command(label="Clear history",
                           command=self.clear_history)
        mb.add_cascade(label="History", menu=m_hist)
        m_opt = tk.Menu(mb, tearoff=False)
        self.opt_detect = tk.BooleanVar(value=False)
        self.opt_backtr = tk.BooleanVar(value=False)
        m_opt.add_checkbutton(label="Always detect language",
                              variable=self.opt_detect)
        m_opt.add_checkbutton(label="Back translation",
                              variable=self.opt_backtr)
        m_theme = tk.Menu(m_opt, tearoff=False)
        for th in _THEMES:
            m_theme.add_command(
                label=th, command=lambda t=th: self.apply_theme(t))
        m_opt.add_cascade(label="Theme", menu=m_theme)
        m_opt.add_command(label="Hotkeys...",
                          command=self.show_hotkeys)
        mb.add_cascade(label="Options", menu=m_opt)
        m_help = tk.Menu(mb, tearoff=False)
        m_help.add_command(label="Hotkey reference",
                           command=self.show_hotkeys)
        m_help.add_command(label="About", command=self.show_about)
        mb.add_cascade(label="Help", menu=m_help)

    # -- actions --
    def _mark_service(self):
        for name, b in self.svc_btns.items():
            b.config(relief="sunken" if name == self.service else "raised")

    def switch_service(self, name):
        """FUN_0045CDBA + FUN_0043A121: switch provider, re-run."""
        self.service = name
        self._mark_service()
        text = self.src.get("1.0", "end").strip()
        if text:
            self.on_go()

    def apply_theme(self, name):
        try:
            from qtranslate.theme import load_theme, window_colors
            global _COLORS
            _COLORS = window_colors(load_theme(name))
            self.root.configure(bg=_COLORS["back"])
        except Exception:
            pass

    def current(self):
        return (self.service,
                self.src.get("1.0", "end").strip(),
                self.tgt.get().strip() or "vi",
                self.src_lang.get().strip() or "auto")

    def render(self, text):
        self.out.delete("1.0", "end")
        self.out.insert("1.0", text)

    def push_hist(self, svc, src, res):
        self.history.append((svc, src, res))

    def on_swap(self):
        a, b = self.src_lang.get(), self.tgt.get()
        if a != "auto":
            self.tgt.set(a)
        self.src_lang.set(b if b else "auto")

    def on_go(self):
        svc, text, tgt, src = self.current()
        res = do_translate(svc, text, tgt, src,
                           self.opt_detect.get(), self.opt_backtr.get())
        self.render(res)
        self.push_hist(svc, text[:120], res[:200])

    def on_listen(self):
        txt = self.out.get("1.0", "end").strip()
        if not txt:
            return
        _, _, tgt, _ = self.current()
        threading.Thread(target=speak, args=(txt[:500], tgt),
                         daemon=True).start()

    def on_copy(self):
        if _HAS_KEYS:
            pyperclip.copy(self.out.get("1.0", "end").strip())

    def on_layout(self):
        from qtranslate.layout import convert_layout
        txt = self.src.get("1.0", "end").strip()
        if not txt and _HAS_KEYS:
            txt = pyperclip.paste()
        fixed = convert_layout(txt)
        self.src.delete("1.0", "end")
        self.src.insert("1.0", fixed)
        if _HAS_KEYS:
            pyperclip.copy(fixed)

    def on_type(self):
        cur = self.src.get("1.0", "end").strip()
        if len(cur) < 3 or len(cur) > 60:
            return
        try:
            sug = _spell.google_suggest(cur)
            self.suggest.config(text=" | ".join(sug[:5]))
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
        self.render("Hotkeys (from Locales/English/help.txt):\n" + doc)

    def show_about(self):
        self.render("QTranslate-re — clean-room RE of QTranslate 6.10.0\n"
                    f"providers: {len(TRANSLATORS)} translate + "
                    f"{len(DICTS)} dict (see README provider table)")

    # -- History window (DLG 164: SysTreeView32 + Clear + Save as) --
    def open_history_window(self):
        w = tk.Toplevel(self.root)
        w.title("History")
        w.configure(bg=_COLORS["back"])
        lb = tk.Listbox(w, width=70, height=15, bg=_COLORS["back"],
                        fg=_COLORS["text"])
        lb.pack(fill="both", expand=True, padx=8, pady=8)
        for svc, src, _ in self.history:
            lb.insert("end", f"[{svc}] {src[:70]}")

        def load_sel():
            try:
                i = lb.curselection()[0]
                _, src, res = self.history[i]
                self.src.delete("1.0", "end")
                self.src.insert("1.0", src)
                self.render(res)
            except Exception:
                pass

        def clear():
            self.history.clear()
            lb.delete(0, "end")

        frm = tk.Frame(w, bg=_COLORS["back"])
        frm.pack(pady=(0, 8))
        tk.Button(frm, text="Open", command=load_sel).pack(side="left",
                                                           padx=4)
        tk.Button(frm, text="Clear", command=clear).pack(side="left",
                                                        padx=4)
        tk.Button(frm, text="Save as...",
                  command=self.on_export_history).pack(side="left", padx=4)

    def clear_history(self):
        self.history.clear()

    def on_export_history(self):
        path = filedialog.asksavefilename(title="Export history",
                                          defaultextension=".html")
        if not path:
            return
        try:
            from qtranslate import history as H
            data = H.html_export([(s, src, "auto", res, self.target)
                                  for (s, src, res) in self.history])
            with open(path, "w", encoding="utf-8") as f:
                f.write(data if isinstance(data, str) else str(data))
            self.render(f"exported {len(self.history)} items -> {path}")
        except Exception as e:
            self.render(f"[export error] {e}")

    # -- Dictionary window (DLG 184: multi-service cards) --
    def open_dict_window(self):
        w = tk.Toplevel(self.root)
        w.title("Dictionary")
        w.configure(bg=_COLORS["back"])
        w.geometry("560x420")
        frm = tk.Frame(w, bg=_COLORS["back"])
        frm.pack(fill="x", padx=8, pady=8)
        tk.Label(frm, text="Word:", bg=_COLORS["back"],
                 fg="gray").pack(side="left")
        ent = tk.Entry(frm, width=30)
        ent.pack(side="left", padx=4)
        out = tk.Text(w, wrap="word", bg=_COLORS["back"],
                      fg=_COLORS["text"],
                      insertbackground=_COLORS["text"])
        out.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        def go_all():
            word = ent.get().strip()[:500]
            if not word:
                return
            out.delete("1.0", "end")
            out.insert("1.0", f"querying {len(DICTS)} dictionaries...")

            def work():
                from qtranslate import dict_render as DR
                cards = []
                for name, fn in DICTS.items():
                    try:
                        frag = fn(word, "en", self.target)
                        if frag:
                            cards.append((name, name.title(),
                                          frag[:8000]))
                    except Exception:
                        pass
                page = DR.render_cards(cards)
                try:
                    open("dict_last.html", "w",
                         encoding="utf-8").write(page)
                except Exception:
                    pass
                summary = "\n\n".join(
                    f"===== {t} =====\n" + _strip_html(f)[:600]
                    for _, t, f in cards)
                self.root.after(
                    0, lambda: (out.delete("1.0", "end"),
                                out.insert("1.0", summary or "[empty]")))
            threading.Thread(target=work, daemon=True).start()

        tk.Button(frm, text="Look up all",
                  command=go_all).pack(side="left", padx=4)

    def on_ocr(self):
        path = filedialog.askopenfilename(title="Image for OCR")
        if not path:
            return
        try:
            from qtranslate.services.ocr import ocr_text
            with open(path, "rb") as f:
                txt = ocr_text(f.read())
            self.src.delete("1.0", "end")
            self.src.insert("1.0", txt)
        except Exception as e:
            self.render(f"[ocr error] {e}")


def on_hotkey(app):
    # Exclusion gate (FUN_004631DE): skip capture in blocked apps/classes.
    try:
        from qtranslate.exclusions import foreground_excluded
        if foreground_excluded():
            print("foreground excluded — capture suppressed")
            return
    except Exception:
        pass
    if not _HAS_KEYS:
        return
    try:
        text = pyperclip.paste().strip()
    except Exception as e:
        print("clipboard error:", e)
        return
    if not text:
        print("clipboard empty — select text + Ctrl+C first")
        return
    svc, _, tgt, _ = app.current()
    print(f"translating {len(text)} chars via {svc}...")
    res = do_translate(svc, text[:5000], tgt, "auto",
                       app.opt_detect.get(), app.opt_backtr.get())
    app.src.delete("1.0", "end")
    app.src.insert("1.0", text[:2000])
    app.render(res)
    app.push_hist(svc, text[:120], res[:200])


def on_layout_hotkey():
    # TaskConvertTextLayout: retype clipboard text in the other layout.
    if not _HAS_KEYS:
        return
    try:
        text = pyperclip.paste().strip()
    except Exception as e:
        print("clipboard error:", e)
        return
    if not text:
        print("clipboard empty — select text + Ctrl+C first")
        return
    from qtranslate.layout import convert_layout
    fixed = convert_layout(text)
    pyperclip.copy(fixed)
    print(f"layout-fixed {len(text)} chars -> clipboard: {fixed[:80]}")


def main():
    root = tk.Tk()
    app = App(root)
    print(f"qtranslate-re main window running "
          f"(services: {len(TRANSLATORS)} translate + {len(DICTS)} dict)")
    print("  Ctrl+Alt+Q: translate clipboard | Ctrl+Alt+L: fix layout")
    if _HAS_KEYS:
        keyboard.add_hotkey("ctrl+alt+q", lambda: on_hotkey(app))
        keyboard.add_hotkey("ctrl+alt+l", on_layout_hotkey)
    else:
        print("pip install keyboard pyperclip for global hotkeys")
    root.mainloop()


def show_popup(source, result):
    """Back-compat headless popup used by older flows/tests."""
    root = tk.Tk()
    root.title("QTranslate")
    root.attributes("-topmost", True)
    root.configure(bg=_COLORS["back"])
    tk.Label(root, text=source, wraplength=480, justify="left",
             fg="gray", bg=_COLORS["back"]).pack(padx=12, pady=(12, 4))
    tk.Label(root, text=result, wraplength=480, justify="left",
             font=("Segoe UI", 13),
             fg=_COLORS["text"], bg=_COLORS["back"]).pack(padx=12, pady=4)
    frm = tk.Frame(root)
    frm.pack(pady=(0, 12))
    tk.Button(frm, text="Listen",
              command=lambda: threading.Thread(
                  target=speak, args=(result, TARGET),
                  daemon=True).start()).pack(side="left", padx=6)
    tk.Button(frm, text="Close", command=root.destroy).pack(side="left")
    root.mainloop()


if __name__ == "__main__":
    main()
