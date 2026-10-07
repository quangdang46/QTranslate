"""Full runnable clone of the QTranslate pipeline (Windows).

Mirrors the native Task pipeline in docs/NATIVE_ARCH.md:
  hotkey / button -> capture (clipboard + exclusion gate FUN_004631DE)
  -> translate via service plugin (9 JS invokers) -> popup render
  -> TTS listen (BASS online -> SAPI offline fallback).

Features (mirrors QTranslate 6.10 main window):
  - 10 translate providers (google/deepl/bing/yandex/baidu/naver/promt/
    youdao/imtranslator... via dictionary module) + dictionary mode
    (oxford/lingvo/urban/wikipedia/multitran/wordreference/reverso/...)
  - history list with export (csv/html/json/txt via history.py)
  - spell suggest (google_suggest / yandex_spell)
  - themes (Themes/*.json via theme.py)
  - keyboard-layout convert (Ctrl+Alt+L, FUN_00404E09 port)
  - exclusion gate (exclusions.py, FUN_004631DE)
  - OCR via file (ocr_space) pasting recognized text into source box

Requires: pip install keyboard pyperclip
  python -I qtranslate/app.py [service] [target_lang] [theme]
Hotkeys: Ctrl+Alt+Q translate clipboard, Ctrl+Alt+L fix layout.
"""
import html as _html
import re
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
from qtranslate.services import promt as _promt
from qtranslate.services import microsoft as _ms
from qtranslate.services import dictionary as _dict
from qtranslate.services import spell as _spell
from qtranslate.session import bing_translate as _bing_tr
from qtranslate import tts as _tts

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


def _strip_html(h: str) -> str:
    h = re.sub(r"<script.*?</script>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<style.*?</style>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<[^>]+>", " ", h)
    return _html.unescape(re.sub(r"\s+", " ", h)).strip()


# ---------------------------------------------------------------- registry
def _t_google(t, sl, tl):
    return _google.translate(t, "auto", tl)


def _t_deepl(t, sl, tl):
    return _deepl.translate(t, "AUTO" if sl == "auto" else sl.upper(), tl.upper())


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
    "multitran": lambda w, sl, tl: _dict.multitran_lookup(w, 17, 57),
    "wordreference": lambda w, sl, tl: _dict.wordreference_lookup(w, sl, tl),
    "reverso": lambda w, sl, tl: _dict.reverso_lookup(w, sl, tl),
    "babylon": lambda w, sl, tl: _dict.babylon_lookup(w, sl, tl),
    "imtranslator": lambda w, sl, tl: _dict.imtranslator_lookup(w, sl, tl),
    "google-search": lambda w, sl, tl: _dict.google_search_lookup(w, sl, tl),
}


# ---------------------------------------------------------------- backend ops
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


def do_translate(service, text, target, mode):
    text = (text or "").strip()
    if not text:
        return ""
    if mode == "dict":
        fn = DICTS.get(service, DICTS["oxford"])
        try:
            return _strip_html(fn(text[:500], "en", target)) or "[empty]"
        except Exception as e:
            return f"[error] {e}"
    fn = TRANSLATORS.get(service, _t_google)
    try:
        return fn(text[:5000], "auto", target) or "[empty]"
    except Exception as e:
        return f"[error] {e}"


# ---------------------------------------------------------------- UI
class App:
    def __init__(self, root):
        self.root = root
        root.title(f"QTranslate-re [{SERVICE} -> {TARGET}]")
        root.attributes("-topmost", True)
        root.configure(bg=_COLORS["back"])
        self.history = []  # (service, src, result)

        top = tk.Frame(root, bg=_COLORS["back"])
        top.pack(fill="x", padx=8, pady=(8, 4))
        tk.Label(top, text="Service:", bg=_COLORS["back"],
                 fg="gray").pack(side="left")
        self.svc = ttk.Combobox(top, values=sorted(
            list(TRANSLATORS) + list(DICTS)), width=16)
        self.svc.set(SERVICE if SERVICE in
                     list(TRANSLATORS) + list(DICTS) else "google")
        self.svc.pack(side="left", padx=4)
        tk.Label(top, text="Target:", bg=_COLORS["back"],
                 fg="gray").pack(side="left")
        self.tgt = tk.Entry(top, width=6)
        self.tgt.insert(0, TARGET)
        self.tgt.pack(side="left", padx=4)
        self.mode = tk.StringVar(value="translate")
        tk.Radiobutton(top, text="Translate", variable=self.mode,
                       value="translate", bg=_COLORS["back"],
                       fg="gray", selectcolor=_COLORS["back"]).pack(side="left")
        tk.Radiobutton(top, text="Dict", variable=self.mode,
                       value="dict", bg=_COLORS["back"],
                       fg="gray", selectcolor=_COLORS["back"]).pack(side="left")
        tk.Label(top, text="Theme:", bg=_COLORS["back"],
                 fg="gray").pack(side="left")
        self.theme = ttk.Combobox(top, values=_THEMES, width=12)
        self.theme.set(THEME if THEME in _THEMES else (_THEMES[0] if _THEMES else ""))
        self.theme.pack(side="left", padx=4)
        self.theme.bind("<<ComboboxSelected>>", lambda e: self.apply_theme())

        mid = tk.Frame(root, bg=_COLORS["back"])
        mid.pack(fill="both", expand=True, padx=8)
        self.src = tk.Text(mid, height=5, wrap="word", bg=_COLORS["back"],
                           fg=_COLORS["text"],
                           insertbackground=_COLORS["text"])
        self.src.pack(fill="x")
        self.src.bind("<KeyRelease>", lambda e: self.on_type())

        btns = tk.Frame(root, bg=_COLORS["back"])
        btns.pack(fill="x", padx=8, pady=4)
        tk.Button(btns, text="Translate (Ctrl+Enter)",
                  command=self.on_go).pack(side="left", padx=2)
        tk.Button(btns, text="Dict", command=self.on_dict).pack(side="left", padx=2)
        tk.Button(btns, text="Listen", command=self.on_listen).pack(side="left", padx=2)
        tk.Button(btns, text="Copy result",
                  command=self.on_copy).pack(side="left", padx=2)
        tk.Button(btns, text="Fix layout",
                  command=self.on_layout).pack(side="left", padx=2)
        tk.Button(btns, text="OCR file...",
                  command=self.on_ocr).pack(side="left", padx=2)
        tk.Button(btns, text="Export history...",
                  command=self.on_export).pack(side="left", padx=2)
        self.root.bind("<Control-Return>", lambda e: self.on_go())

        self.suggest = tk.Label(root, text="", bg=_COLORS["back"],
                                fg="gray", anchor="w")
        self.suggest.pack(fill="x", padx=8)

        self.out = tk.Text(mid, height=10, wrap="word", bg=_COLORS["back"],
                           fg=_COLORS["text"],
                           insertbackground=_COLORS["text"],
                           font=("Segoe UI", 12))
        self.out.pack(fill="both", expand=True, pady=(4, 0))

        tk.Label(root, text="History:", bg=_COLORS["back"],
                 fg="gray").pack(anchor="w", padx=8)
        self.hist = tk.Listbox(root, height=5, bg=_COLORS["back"],
                               fg=_COLORS["text"])
        self.hist.pack(fill="x", padx=8, pady=(0, 8))
        self.hist.bind("<<ListboxSelect>>", lambda e: self.on_hist())

    # -- actions
    def apply_theme(self):
        try:
            from qtranslate.theme import load_theme, window_colors
            global _COLORS
            _COLORS = window_colors(load_theme(self.theme.get()))
            self.root.configure(bg=_COLORS["back"])
        except Exception:
            pass

    def current(self):
        return (self.svc.get().strip().lower() or "google",
                self.src.get("1.0", "end").strip(),
                self.tgt.get().strip() or "vi", self.mode.get())

    def render(self, text):
        self.out.delete("1.0", "end")
        self.out.insert("1.0", text)

    def push_hist(self, svc, src, res):
        self.history.append((svc, src, res))
        self.hist.insert("end", f"[{svc}] {src[:60]}")
        self.hist.see("end")

    def on_go(self):
        svc, text, tgt, _ = self.current()
        res = do_translate(svc, text, tgt, "translate")
        self.render(res)
        self.push_hist(svc, text[:120], res[:200])

    def on_dict(self):
        svc, text, tgt, _ = self.current()
        res = do_translate(svc, text, tgt, "dict")
        self.render(res)
        self.push_hist(svc + "/dict", text[:120], res[:200])

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

    def on_type(self):
        txt = self.src.get("1.0", "end").strip().split()[:0]
        cur = self.src.get("1.0", "end").strip()
        if len(cur) < 3 or len(cur) > 60:
            return
        try:
            sug = _spell.google_suggest(cur)
            self.suggest.config(text=" | ".join(sug[:5]))
        except Exception:
            pass

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

    def on_export(self):
        path = filedialog.asksavefilename(title="Export history",
                                          defaultextension=".html")
        if not path:
            return
        try:
            from qtranslate import history as H
            tgt = self.tgt.get().strip() or TARGET
            data = H.html_export([(s, src, "auto", res, tgt)
                                  for (s, src, res) in self.history])
            with open(path, "w", encoding="utf-8") as f:
                f.write(data if isinstance(data, str) else str(data))
            self.render(f"exported {len(self.history)} items -> {path}")
        except Exception as e:
            self.render(f"[export error] {e}")

    def on_hist(self):
        try:
            i = self.hist.curselection()[0]
            _, src, res = self.history[i]
            self.src.delete("1.0", "end")
            self.src.insert("1.0", src)
            self.render(res)
        except Exception:
            pass


def on_hotkey(app):
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
    svc, _, tgt, mode = app.current()
    print(f"translating {len(text)} chars via {svc}...")
    res = do_translate(svc, text[:5000], tgt, mode)
    app.src.delete("1.0", "end")
    app.src.insert("1.0", text[:2000])
    app.render(res)
    app.push_hist(svc, text[:120], res[:200])


def on_layout_hotkey():
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
    print(f"qtranslate-re full UI running "
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
    root.title(f"QTranslate-re [{SERVICE} -> {TARGET}]")
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
