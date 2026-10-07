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
from qtranslate.services import babylon as _babylon
from qtranslate.services import dictionary as _dict
from qtranslate.services import spell as _spell
from qtranslate.session import bing_translate as _bing_tr

SERVICE = sys.argv[1] if len(sys.argv) > 1 else "google"
TARGET = sys.argv[2] if len(sys.argv) > 2 else "vi"
THEME = sys.argv[3] if len(sys.argv) > 3 else "Blue"
# Explicit CLI args win over the restored session (native behavior:
# an explicit launch overrides the remembered service/pair).
_CLI_SERVICE = len(sys.argv) > 1
_CLI_TARGET = len(sys.argv) > 2

def _default_colors():
    """Main-window colors from the real Options.json Appearance section.

    The native main window does NOT use Themes/*.json (those are for
    popups); it uses ColorBack/ColorText/ColorFrame from Appearance
    (verified: ColorBack=15790320=#F0F0F0, ColorText=0, ColorFrame=8023133
    on this machine). Falls back to the THEME arg when set.
    """
    if THEME != "Blue":
        try:
            from qtranslate.theme import load_theme, window_colors
            return window_colors(load_theme(THEME))
        except Exception:
            pass
    try:
        from qtranslate import config as _C
        a = _C.load().get("Appearance", {})
        return {"back": "#%06x" % int(a.get("ColorBack", 15790320)),
                "text": "#%06x" % int(a.get("ColorText", 0)),
                "border": "#%06x" % int(a.get("ColorFrame", 8023133))}
    except Exception:
        return {"back": "#f0f0f0", "text": "#000000",
                "border": "#7a7a7a"}


try:
    from qtranslate.theme import list_themes
    _THEMES = list_themes()
except Exception:
    _THEMES = [THEME]
_COLORS = _default_colors()

# Full language table from Services/Google Translate/Service.js
# SupportedLanguages (75 codes; index 1=auto .. 57=vi). Display names
# are ISO English names (native combo shows localized names from its
# .mui resources; English mapping is equivalent for selection).
_ISO_NAMES = {
    "auto": "Auto-Detect", "af": "Afrikaans", "az": "Azerbaijani",
    "sq": "Albanian", "ar": "Arabic", "hy": "Armenian", "eu": "Basque",
    "be": "Belarusian", "bg": "Bulgarian", "ca": "Catalan",
    "zh-CN": "Chinese (Simplified)", "zh-TW": "Chinese (Traditional)",
    "hr": "Croatian", "cs": "Czech", "da": "Danish", "nl": "Dutch",
    "en": "English", "et": "Estonian", "fi": "Finnish", "tl": "Filipino",
    "fr": "French", "gl": "Galician", "de": "German", "el": "Greek",
    "ht": "Haitian Creole", "iw": "Hebrew", "hi": "Hindi",
    "hu": "Hungarian", "is": "Icelandic", "id": "Indonesian",
    "it": "Italian", "ga": "Irish", "ja": "Japanese", "ka": "Georgian",
    "ko": "Korean", "lv": "Latvian", "lt": "Lithuanian",
    "mk": "Macedonian", "ms": "Malay", "mt": "Maltese",
    "no": "Norwegian", "fa": "Persian", "pl": "Polish", "pt": "Portuguese",
    "ro": "Romanian", "ru": "Russian", "sr": "Serbian", "sk": "Slovak",
    "sl": "Slovenian", "es": "Spanish", "sw": "Swahili",
    "sv": "Swedish", "th": "Thai", "tr": "Turkish", "uk": "Ukrainian",
    "ur": "Urdu", "vi": "Vietnamese", "cy": "Welsh", "yi": "Yiddish",
    "eo": "Esperanto", "hmn": "Hmong", "la": "Latin", "lo": "Lao",
    "kk": "Kazakh", "uz": "Uzbek", "si": "Sinhala", "tg": "Tajik",
    "te": "Telugu", "km": "Khmer", "mn": "Mongolian", "kn": "Kannada",
    "ta": "Tamil", "mr": "Marathi", "bn": "Bengali", "tt": "Tatar",
    "zh-CHS": "Chinese (Simplified)",
}
try:
    from qtranslate.services.google_translate import SUPPORTED_LANGS \
        as _SL
    LANGS = [c for c in _SL if c != -1]
except Exception:
    LANGS = list(_ISO_NAMES)
TO_LANGS = [c for c in LANGS if c != "auto"]
LANG_DISPLAY = {c: _ISO_NAMES.get(c, c) for c in LANGS}
LANG_CODES = {v: k for k, v in LANG_DISPLAY.items()}


def _disabled_lang_indices() -> set:
    try:
        from qtranslate import config as _C
        return set(_C.load().get("DisabledLanguages", []))
    except Exception:
        return set()


def _lang_names(codes, include_auto=True):
    try:
        from qtranslate.services.google_translate import SUPPORTED_LANGS \
            as _SL2
        _dis = _disabled_lang_indices()
        out = []
        for c in codes:
            try:
                idx = list(_SL2).index(c)
            except ValueError:
                idx = -1
            if idx in _dis:
                continue
            if c == "auto" and not include_auto:
                continue
            out.append(LANG_DISPLAY.get(c, c))
        return out
    except Exception:
        return [LANG_DISPLAY.get(c, c) for c in codes
                if c != "auto" or include_auto]


SRC_LANG_NAMES = [LANG_DISPLAY[c] for c in LANGS]
TO_LANG_NAMES = [LANG_DISPLAY[c] for c in TO_LANGS]


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


def _t_babylon(t, sl, tl):
    return _babylon.translate(t, "en" if sl == "auto" else sl, tl)


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
    "babylon": _t_babylon,
}

DICTS = {
    "oxford": lambda w, sl, tl: _dict.oxford_lookup(w),
    "lingvo": lambda w, sl, tl: _dict.lingvo_lookup(w, sl, tl),
    "urban": lambda w, sl, tl: _dict.urban_lookup(w),
    "wikipedia": lambda w, sl, tl: _dict.wikipedia_lookup(w, sl, tl),
    "multitran": lambda w, sl, tl: _dict.multitran_lookup(w, 1, 2),
    "wordreference": lambda w, sl, tl: _dict.wordreference_lookup(w, sl, tl),
    "reverso": lambda w, sl, tl: _dict.reverso_lookup(w, sl, tl),
    "babylon": lambda w, sl, tl: _dict.babylon_dict_lookup(w, sl, tl),
    "imtranslator": lambda w, sl, tl: _dict.imtranslator_lookup(w, sl, tl),
    "google-search": lambda w, sl, tl: _dict.google_search_lookup(w, sl, tl),
}


# ------------------------------------------------------------ backend ops
_SERVICE_LINKS = {
    "google": "https://translate.google.com/",
    "deepl": "https://www.deepl.com/translator",
    "yandex": "https://translate.yandex.com/",
    "baidu": "https://fanyi.baidu.com/",
    "naver": "https://papago.naver.com/",
    "youdao": "https://fanyi.youdao.com/",
    "bing": "https://www.bing.com/translator",
    "microsoft": "https://www.bing.com/translator",
    "promt": "https://www.online-translator.com/",
    "babylon": "https://translation.babylon-software.com/",
    "reverso": "https://www.reverso.net/",
}


def _decode_placement(hexs: str):
    """Decode a WINDOWPLACEMENT hex blob -> (x, y, w, h, showCmd).

    Layout: length, flags, showCmd, ptMin(2), ptMax(2), rcNormal(4)
    little-endian LONGs. Verified vs real WindowMainPlacement
    (526x366 at 876,292, show=1).
    """
    try:
        import struct
        b = bytes.fromhex((hexs or "").strip())
        if len(b) < 44:
            return None
        _, _, show, _, _, _, _, l, t, r, bo = struct.unpack("<11i", b[:44])
        if r > l and bo > t:
            return (l, t, r - l, bo - t, show)
    except Exception:
        pass
    return None


def _encode_placement(x: int, y: int, w: int, h: int,
                      show: int = 1) -> str:
    """Tk geometry -> WINDOWPLACEMENT hex blob (length=44, flags=0,
    min/max (-1,-1))."""
    import struct
    return struct.pack("<11i", 44, 0, show, -1, -1, -1, -1,
                       x, y, x + w, y + h).hex().upper()


def _place_main(root):
    """Restore main-window geometry from General.WindowMainPlacement;
    fall back to the native default size."""
    try:
        from qtranslate import config as _C
        hexs = _C.load().get("General", {}).get("WindowMainPlacement",
                                                "")
        rc = _decode_placement(hexs)
    except Exception:
        rc = None
    if rc:
        x, y, w, h, _ = rc
        try:
            root.geometry(f"{w}x{h}+{x}+{y}")
            return
        except Exception:
            pass
    root.geometry("526x366")


def _place_aux(widget, key: str, default: str):
    """Restore aux-window geometry from General.<key> blob (native
    WindowOptions/History/Dictionary/KeyboardPlacement); save on
    close via WM_DELETE_WINDOW hook."""
    try:
        from qtranslate import config as _C
        rc = _decode_placement(
            _C.load().get("General", {}).get(key, ""))
    except Exception:
        rc = None
    if rc:
        x, y, w, h, _ = rc
        try:
            widget.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            widget.geometry(default)
    else:
        widget.geometry(default)
    try:
        _prev = widget.protocol("WM_DELETE_WINDOW")

        def _close():
            _save_placement(key, widget)
            try:
                widget.destroy()
            except Exception:
                pass

        widget.protocol("WM_DELETE_WINDOW", _close)
    except Exception:
        pass


def _save_placement(key: str, widget):
    """Persist a window's geometry into General.<key> blob."""
    try:
        from qtranslate import config as _C
        import json as _j
        g = widget.geometry()  # WxH+X+Y
        import re as _re
        m = _re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", g)
        if not m:
            return
        w, h, x, y = map(int, m.groups())
        full = _C.load()
        full.setdefault("General", {})[key] = _encode_placement(x, y, w,
                                                                h)
        with open(_C.DEFAULT_PATH, "w", encoding="utf-8") as f:
            _j.dump(full, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _pane_font(size_delta: int = 0):
    """Main-pane font from General.FontName/TextSize (native dialog
    font; empty FontName = MS Shell Dlg ~ Tahoma)."""
    try:
        from qtranslate import config as _C
        _g = _C.load().get("General", {})
        name = (_g.get("FontName", "") or "").strip() or "Tahoma"
        size = int(_g.get("TextSize", 9)) + size_delta
    except Exception:
        name, size = "Tahoma", 9 + size_delta
    return (name, max(6, size))


_PACK = {}
_PACK_NAME = [None]


def _pack():
    """Load the UI language pack per General.LocaleFoderName
    (native FUN_0045B716 path; English = built-in strings)."""
    try:
        from qtranslate import config as _C
        name = _C.load().get("General", {}).get("LocaleFoderName",
                                                "") or "English"
    except Exception:
        name = "English"
    if _PACK_NAME[0] == name and _PACK:
        return _PACK
    _PACK.clear()
    _PACK_NAME[0] = name
    if name != "English":
        try:
            from qtranslate import locale as _L
            _PACK.update(_L.load_pack(name))
        except Exception:
            pass
    return _PACK


def _T(section: str, sid: int, default: str = "",
       menu: int | None = None) -> str:
    """Localized string by section + numeric id (lang.json layout:
    Strings = [id, text]; Menus = [{Id, Items:[[id, text]]}]. Pass
    menu=Id to look inside one menu (e.g. menu=3 history-item)."""
    try:
        pack = _pack()
        items = pack.get(section, [])
        if menu is not None:
            for grp in items:
                if isinstance(grp, dict) and grp.get("Id") == menu:
                    items = grp.get("Items", [])
                    break
            else:
                return default
        if isinstance(items, dict):
            return str(items.get(str(sid), items.get(sid, default)))
        for it in items:
            if isinstance(it, (list, tuple)) and len(it) >= 2 \
                    and it[0] == sid:
                return str(it[1])
            if isinstance(it, dict) and it.get("Id") == sid:
                return str(it.get("Text", it.get("Caption", default)))
    except Exception:
        pass
    return default


def _W(wid: int, default: str = "") -> str:
    """Dialog title by Windows Id (lang.json Windows list)."""
    try:
        pack = _pack()
        for w in pack.get("Windows", []):
            if isinstance(w, dict) and w.get("Id") == wid:
                if w.get("Caption"):
                    return str(w["Caption"])
            elif isinstance(w, str) and wid == 1:
                return w
    except Exception:
        pass
    return default


def _Cw(wid: int, cid: int, default: str = "") -> str:
    """Control label by Windows Id + control id."""
    try:
        pack = _pack()
        for w in pack.get("Windows", []):
            if isinstance(w, dict) and w.get("Id") == wid:
                for c in w.get("Controls", []):
                    if isinstance(c, (list, tuple)) and len(c) >= 2 \
                            and c[0] == cid:
                        return str(c[1])
    except Exception:
        pass
    return default


def _open_url(url: str):
    """Open URL honoring Advanced.DefaultBrowserId (native browser pick).

    Empty id = system default (webbrowser.open); otherwise try the
    registered browser name, falling back to default.
    """
    import webbrowser
    try:
        from qtranslate import config as _C
        bid = (_C.load().get("Advanced", {}).get("DefaultBrowserId")
               or "").strip()
    except Exception:
        bid = ""
    if bid:
        try:
            webbrowser.get(bid).open(url)
            return
        except Exception:
            pass
    webbrowser.open(url)


def _dict_service_link(service: str) -> str:
    return _SERVICE_LINKS.get(service, "https://translate.google.com/")


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
    """Online mp3 -> BASS; on failure fall back to offline SAPI.

    Honors Advanced.EnableSlowerListening (clearer/slower TTS).
    """
    try:
        from qtranslate import config as _C
        slow = bool(_C.load().get("Advanced", {}).get(
            "EnableSlowerListening", False))
    except Exception:
        slow = False
    try:
        from qtranslate.player import play_text
        play_text(text, lang, slow=slow)
    except Exception as e:
        print(f"TTS failed ({e}); trying SAPI")
        try:
            from qtranslate.sapi import speak as sapi_speak
            sapi_speak(text, rate=-4 if slow else 0)
        except Exception as e2:
            print(f"SAPI failed: {e2}")


def do_translate(service, text, target, src="auto", auto_detect=False,
                 back_translate=False):
    """Mirrors FUN_00404A12 orchestrator: pick -> execute -> fallbacks."""
    text = (text or "").strip()
    if not text:
        return ""
    # Advanced.RemoveLineBreaks: collapse newlines before sending
    try:
        from qtranslate import config as _C
        if _C.load().get("Advanced", {}).get("RemoveLineBreaks", False):
            import re as _re
            text = _re.sub(r"\s*\n\s*", " ", text)
    except Exception:
        pass
    fn = TRANSLATORS.get(service, _t_google)
    try:
        if auto_detect:
            src = detect_language(text)
        out = fn(text[:5000], src, target)
        if not out:
            # native error string id 190 (vi: "Không có dữ liệu trả về
            # (quá thời gian chờ..."; canonical English verified)
            return _T("Strings", 190,
                      "No data returned (timeout while sending data).")
        if back_translate and not out.startswith("No data"):
            try:
                back = fn(out[:5000], target,
                           "en" if src == "auto" else src)
                if back:
                    out += f"\n\n--- back-translation ---\n{back}"
            except Exception:
                pass
        return out
    except Exception:
        return _T("Strings", 190,
                  "No data returned (timeout while sending data).")


# ------------------------------------------------------------------ UI
class App:
    """Main window — mirrors DLG 129 (340x201, 17 controls)."""

    def __init__(self, root):
        self.root = root
        # ActiveServices[0]/LanguageTo/LanguageFrom restore the last
        # session (native saves them into General on switch/exit).
        try:
            from qtranslate import config as _CA
            _ga = _CA.load().get("General", {})
            _act = (_ga.get("ActiveServices", []) or [None])[0]
            _aname = _CA.SERVICE_NAMES.get(_act)
        except Exception:
            _aname = None
        if _CLI_SERVICE and SERVICE in TRANSLATORS:
            self.service = SERVICE
        else:
            self.service = _aname if _aname in TRANSLATORS else (
                SERVICE if SERVICE in TRANSLATORS else "google")
        try:
            _table = list(__import__(
                "qtranslate.services.google_translate",
                fromlist=["SUPPORTED_LANGS"]).SUPPORTED_LANGS)
            if _CLI_TARGET:
                TARGET_EFF = TARGET
            else:
                _lt = _ga.get("LanguageTo", 57)
                TARGET_EFF = _table[_lt] if 0 <= _lt < len(_table) \
                    else TARGET
            _lf = _ga.get("LanguageFrom", 1)
            self.source = _table[_lf] if 0 <= _lf < len(_table) \
                else "auto"
        except Exception:
            TARGET_EFF, self.source = TARGET, "auto"
        self.target = TARGET_EFF
        # multi-select set (right-click toggles, help.txt Actions).
        self.multi_services = set()
        self.history = self._load_history()  # (service, src, result)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.bind("<Unmap>", self._on_minimize)
        root.title("QTranslate")
        root.configure(bg=_COLORS["back"])
        # native rect decoded from General.WindowMainPlacement
        # WINDOWPLACEMENT blob (526x366 at 876,292 on this machine)
        _place_main(root)
        self._init_opt_flags()
        self._build_main()

    # -- main window body: mirrors the real QTranslate main window --
    # nav row (back/forward + service link + overflow menu),
    # source pane (default text = version line + help.txt),
    # toolbar (paste, Auto-Detect, swap, target combo, Translate,
    # mic/headphone), result pane, service icon strip at the bottom.
    def _build_main(self):
        bg = _COLORS["back"]
        # nav row
        nav = tk.Frame(self.root, bg=bg)
        nav.pack(fill="x", padx=4, pady=(2, 0))
        tk.Button(nav, text="◀", width=3,
                  command=self.hist_back).pack(side="left", padx=1)
        tk.Button(nav, text="▶", width=3,
                  command=self.hist_forward).pack(side="left", padx=1)
        self.svc_link = tk.Label(nav, text=self.service.title(),
                                 fg="blue", cursor="hand2", bg=bg,
                                 font=("Segoe UI", 9, "underline"))
        self.svc_link.pack(side="left", padx=6)
        self.svc_link.bind("<Button-1>",
                           lambda e: self.open_service_page())
        tk.Button(nav, text="⋮", width=3,
                  command=self.show_nav_menu).pack(side="right", padx=1)
        # source pane (id1017) + mic/headphone overlay at right edge,
        # exactly like the native main window (mic above headphone,
        # top-right of the source pane)
        srcfrm = tk.Frame(self.root, bg="white")
        srcfrm.pack(fill="x", padx=4)
        self._panes = getattr(self, "_panes", {})
        self._panes["src"] = srcfrm
        # taller source pane: native shows ~9 lines (through
        # "Ctrl+N => Clear current translation")
        self.src = tk.Text(srcfrm, height=12, wrap="word", bg="white",
                           fg="black", insertbackground="black",
                           font=_pane_font(), borderwidth=0,
                           highlightthickness=0, undo=True,
                           maxundo=100)
        self.src.pack(side="left", fill="x", expand=True)
        # Contents.EditSource cache wins over the default help text
        # (native restores last session panes on boot).
        try:
            from qtranslate import config as _CC
            _es = (_CC.load().get("Contents", {}).get("EditSource")
                   or "").strip()
        except Exception:
            _es = ""
        self.src.insert("1.0", _es if _es else self.default_source_text())
        self.src.bind("<KeyRelease>", lambda e: self.on_type())
        srcside = tk.Frame(srcfrm, bg="white")
        srcside.pack(side="right", fill="y", padx=2)
        # Tahoma glyphs (emoji mic/headphone render blank on win32 Tk)
        tk.Button(srcside, text="Mic", width=4, borderwidth=0,
                  bg="white", font=("Tahoma", 7),
                  command=self.on_mic).pack(pady=(4, 1))
        tk.Button(srcside, text="♫", width=4, borderwidth=0,
                  bg="white", font=("Tahoma", 9),
                  command=self.on_listen).pack(pady=1)
        # keep the side column narrow so the text pane keeps its width
        srcside.config(width=34)
        # toolbar row: [paste] [kebab] [Auto-Detect] [swap] [target]
        # [Translate] — no mic/headphone here (they live on the panes)
        bar = tk.Frame(self.root, bg=bg)
        bar.pack(fill="x", padx=4, pady=2)
        # id1021 "New": clears source for a fresh translation
        tk.Button(bar, text="\U0001f4cb", width=3,
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
        self.tgt.bind("<<ComboboxSelected>>",
                      lambda e: self._persist_langs(
                          LANG_CODES.get(self.src_lang.get().strip(),
                                         "auto"),
                          LANG_CODES.get(self.tgt.get().strip(), "vi")))
        self.src_lang.bind("<<ComboboxSelected>>",
                           lambda e: self._persist_langs(
                               LANG_CODES.get(
                                   self.src_lang.get().strip(), "auto"),
                               LANG_CODES.get(self.tgt.get().strip(),
                                              "vi")))
        tk.Button(bar, text=_Cw(1, 1004, "Translate"),
                  command=self.on_go).pack(side="left", padx=4)
        self.suggest = tk.Label(self.root, text="", bg=bg, fg="gray",
                                anchor="w", font=("Tahoma", 7),
                                cursor="hand2")
        self.suggest.pack(fill="x", padx=4, pady=0)
        self.suggest.bind("<Button-1>",
                          lambda e: self.accept_suggestion())
        self._suggestions = []
        # result pane (id1018) + headphone overlay bottom-right
        outfrm = tk.Frame(self.root, bg="white")
        outfrm.pack(fill="both", expand=True, padx=4)
        self._panes["mid"] = outfrm
        try:
            if not _gp.get("ShowTopPane", True) and self._panes.get(
                    "src") is not None:
                self._panes["src"].pack_forget()
            if not _gp.get("ShowMiddlePane", True):
                outfrm.pack_forget()
        except Exception:
            pass
        self.out = tk.Text(outfrm, height=6, wrap="word", bg="white",
                           fg="black", insertbackground="black",
                           font=_pane_font(), borderwidth=0,
                           highlightthickness=0, undo=True,
                           maxundo=100)
        self.out.pack(side="left", fill="both", expand=True)
        self.out.bind("<Button-3>", self.show_result_menu)
        outside = tk.Frame(outfrm, bg="white")
        outside.pack(side="right", fill="y", padx=2)
        tk.Frame(outside, bg="white", height=120).pack()
        tk.Button(outside, text="♫", width=4, borderwidth=0,
                  bg="white", font=("Tahoma", 9),
                  command=self.on_listen).pack(side="bottom", pady=4)
        outside.config(width=34)
        # service icon strip at the bottom (icons from Services/*/Service.ico,
        # click = switch + re-translate like FUN_0045CDBA; middle-click =
        # browser, right-click = multi-select per help.txt Actions).
        # Native shows icon above a short name (Go.., Mi.., Pr.., ...).
        strip = tk.Frame(self.root, bg=bg)
        strip.pack(fill="x", padx=4, pady=(2, 4))
        self._panes = {"src": None, "mid": None, "svc": strip,
                       "bar": None}
        # ShowTopPane/Middle/Services (native 0x8071/0x8064/0x8065,
        # Ctrl+F1/F2/F3): srcfrm=top, bar+outfrm=middle, strip=services
        try:
            from qtranslate import config as _CP
            _gp = _CP.load().get("General", {})
        except Exception:
            _gp = {}
        if not _gp.get("ShowServicesPane", True):
            strip.pack_forget()
        self.svc_btns = {}
        self.svc_icons = {}
        # short names exactly like native: Go.. Mi.. Pr.. Ba.. Ya..
        # yo.. Ba.. Pa.. De.. (icon folder names truncated to 2 chars)
        _SHORT = {"google": "Go..", "microsoft": "Mi..", "promt": "Pr..",
                  "babylon": "Ba..", "yandex": "Ya..", "youdao": "yo..",
                  "baidu": "Ba..", "naver": "Pa..", "deepl": "DeepL",
                  "reverso": "Re.."}
        for name in self.ordered_services():
            # native: small icon + short name side-by-side in one row
            cell = tk.Frame(strip, bg=bg)
            cell.pack(side="left", padx=2)
            b = tk.Button(cell, width=22, height=22, borderwidth=0,
                          bg=bg, activebackground=bg,
                          command=lambda n=name: self.switch_service(n))
            b.pack(side="left")
            b.bind("<Button-2>",
                   lambda e, n=name: self.open_service_page_n(n))
            b.bind("<Button-3>",
                   lambda e, n=name: self.toggle_multi_service(n))
            tk.Label(cell, text=_SHORT.get(name, name[:2] + ".."), bg=bg,
                     fg="black", font=("Tahoma", 8)).pack(side="left",
                                                          padx=(1, 0))
            self.svc_btns[name] = b
            self._load_svc_icon(name, b)
        self._mark_service()
        # key bindings mirror help.txt Main window hotkeys
        self.root.bind("<Control-Return>", lambda e: self.on_go())
        self.root.bind("<Control-k>", lambda e: self.open_keyboard())
        self.root.bind("<Control-n>", lambda e: self.on_clear())
        self.root.bind("<Control-d>", lambda e: self.open_dict_window())
        self.root.bind("<Control-h>", lambda e: self.open_history_window())
        self.root.bind("<Control-i>", lambda e: self.on_swap())
        self.root.bind("<F1>", lambda e: self.show_hotkeys())
        # Shift+Esc = reset pair to auto-detected (native 0x8052 Reset)
        self.root.bind("<Shift-Escape>", lambda e: self.reset_pair())
        # Ctrl+1..9 = 1..9th service (accel 0x8042-0x804A),
        # Ctrl+Shift+1..9 = select language pair (help.txt)
        for _i in range(1, 10):
            self.root.bind(f"<Control-Key-{_i}>",
                           lambda e, i=_i: self.slot_service(i))
            self.root.bind(f"<Control-Shift-Key-{_i}>",
                           lambda e, i=_i: self.slot_pair(i))
        # Ctrl+Tab / Ctrl+Shift+Tab = next/prev service (accel 170)
        self.root.bind("<Control-Tab>", lambda e: self.cycle_service(1))
        self.root.bind("<Control-Shift-Tab>",
                       lambda e: self.cycle_service(-1))
        self.root.bind("<Control-space>",
                       lambda e: self.accept_suggestion())
        # Alt+Left/Right = history back/forward, Ctrl+Up = copy
        # translation to input (help.txt Main window hotkeys)
        self.root.bind("<Alt-Left>", lambda e: self.hist_back())
        self.root.bind("<Alt-Right>", lambda e: self.hist_forward())
        self.root.bind("<Control-Up>", lambda e: self.copy_to_source())
        # F11 = fullscreen toggle (help.txt Main window hotkeys)
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
        # native pane toggles Ctrl+F1/F2/F3 (0x8071/0x8064/0x8065)
        self.root.bind("<Control-F1>",
                       lambda e: self.toggle_pane("ShowTopPane", "src"))
        self.root.bind("<Control-F2>",
                       lambda e: self.toggle_pane("ShowMiddlePane", "mid"))
        self.root.bind("<Control-F3>",
                       lambda e: self.toggle_pane("ShowServicesPane",
                                                   "svc"))
        # Ctrl+B = back-translation toggle+run (accel 0x8034);
        # Ctrl+Alt+1..9 = dictionary with n-th service (help.txt)
        self.root.bind("<Control-b>", lambda e: self.toggle_backtr())
        for _i in range(1, 10):
            self.root.bind(f"<Control-Alt-Key-{_i}>",
                           lambda e, i=_i: self.dict_with_service(i))
        # Shift+1..9 = dictionary with n-th service (accel 0x8082-0x808A)
        for _i in range(1, 10):
            self.root.bind(f"<Shift-Key-{_i}>",
                           lambda e, i=_i: self.dict_with_service(i))
        # Ctrl+Left/Right = prev/next service (accel 0x8069/0x806A)
        self.root.bind("<Control-Left>",
                       lambda e: self.cycle_service(-1))
        self.root.bind("<Control-Right>",
                       lambda e: self.cycle_service(1))

    def toggle_backtr(self):
        try:
            v = not self.opt_backtr.get()
            self.opt_backtr.set(v)
            from qtranslate import config as _C
            import json as _j
            full = _C.load()
            full.setdefault("General", {})["BackTranslation"] = v
            with open(_C.DEFAULT_PATH, "w",
                      encoding="utf-8") as f:
                _j.dump(full, f, ensure_ascii=False, indent=1)
            if v:
                self.on_go()
        except Exception:
            pass

    def dict_with_service(self, n):
        """Ctrl+Alt+1..9: dictionary lookup with the n-th service."""
        try:
            names = self.ordered_services()
            if 1 <= n <= len(names):
                self.switch_service(names[n - 1])
            self.open_dict_window()
        except Exception:
            pass

    def toggle_fullscreen(self):
        try:
            cur = bool(self.root.attributes("-fullscreen"))
            self.root.attributes("-fullscreen", not cur)
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
            self.src_lang.set(_fn.get(_table[_fi]
                                      if 0 <= _fi < len(_table) else "auto",
                                      "Auto-Detect"))
            self.tgt.set(_fn.get(_table[_si]
                                 if 0 <= _si < len(_table) else "vi",
                                 "Vietnamese"))
        except Exception:
            self.src_lang.set("Auto-Detect")

    def slot_service(self, n):
        """Ctrl+1..9: switch to the n-th service (accel 0x8042-0x804A;
        native Ctrl+Alt+1..9 dictionary variant opens dict window)."""
        try:
            names = self.ordered_services()
            if 1 <= n <= len(names):
                self.switch_service(names[n - 1])
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
            self.src_lang.set(LANG_DISPLAY.get(ca, ca))
            self.tgt.set(LANG_DISPLAY.get(cb, cb))
        except Exception:
            pass

    def cycle_service(self, direction=1):
        """Ctrl+Tab / Ctrl+Shift+Tab: next/previous service (accel 170
        0x8069/0x806A + Ctrl+1..9 slots 0x8042-0x804A)."""
        try:
            names = self.ordered_services()
            if not names:
                return
            i = names.index(self.service) if self.service in names else 0
            self.switch_service(names[(i + direction) % len(names)])
        except Exception:
            pass

    def toggle_pane(self, key, pane):
        """Show/hide a main-window pane, persisting General.<key>."""
        try:
            w = (self._panes or {}).get(pane)
            if w is None:
                return
            from qtranslate import config as _C
            import json as _j
            full = _C.load()
            cur = bool(full.setdefault("General", {}).get(key, True))
            full["General"][key] = not cur
            with open(_C.DEFAULT_PATH, "w",
                      encoding="utf-8") as f:
                _j.dump(full, f, ensure_ascii=False, indent=1)
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
            self.render(f"[error] {e}")

    def _load_svc_icon(self, name, button):
        """Load Services/<Name>/Service.ico as the strip button image."""
        import glob
        import os
        try:
            pats = {
                "google": "Google Translate", "deepl": "DeepL",
                "yandex": "Yandex", "baidu": "Baidu", "naver": "Naver",
                "youdao": "youdao", "bing": "Microsoft Translator",
                "microsoft": "Microsoft Translator", "promt": "Promt",
                "reverso": "Reverso", "babylon": "Babylon",
            }
            folder = pats.get(name, name)
            ico = os.path.join("C:/Program Files (x86)/QTranslate/Services",
                               folder, "Service.ico")
            if not os.path.exists(ico):
                button.config(text=name[:4])
                return
            try:
                from PIL import Image, ImageTk
                im = Image.open(ico)
                im = im.convert("RGBA").resize((22, 22), Image.LANCZOS)
                photo = ImageTk.PhotoImage(im)
            except Exception:
                photo = tk.PhotoImage(file=ico)
                w, h = photo.width(), photo.height()
                if w > 24 or h > 24:
                    photo = photo.subsample(max(1, w // 22),
                                            max(1, h // 22))
            self.svc_icons[name] = photo  # keep ref
            button.config(image=photo, text="")
        except Exception:
            try:
                button.config(text=name[:4])
            except Exception:
                pass

    # -- option flags live in the nav kebab menu (show_nav_menu); the
    # native main window has NO menubar (tray + context menus only),
    # so there is deliberately no _build_menu here. --
    def _init_opt_flags(self):
        try:
            from qtranslate import config as _C0
            _g0 = _C0.load().get("General", {})
        except Exception:
            _g0 = {}
        self.opt_detect = tk.BooleanVar(
            value=bool(_g0.get("AlwaysDetectLanguage", False)))
        self.opt_backtr = tk.BooleanVar(
            value=bool(_g0.get("BackTranslation", False)))

    def show_result_menu(self, event=None):
        """Result-pane context menu (native history-item menu Id 3:
        Open/Copy-text/Copy-translation/Delete/Listen)."""
        m = tk.Menu(self.root, tearoff=False)
        m.add_command(label=_T("Menus", 20, "Copy translation", menu=3),
                      command=self.on_copy)
        m.add_command(label=_T("Menus", 40, "Listen to text", menu=3),
                      command=self.on_listen)
        m.add_separator()
        m.add_command(label=_T("Menus", 30, "Clear", menu=3),
                      command=self.on_clear)
        try:
            m.tk_popup(self.root.winfo_pointerx(),
                       self.root.winfo_pointery())
        finally:
            m.grab_release()

    # -- main-window helpers (mirror native behavior) --
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

        Verified side-by-side vs the native window: it shows the whole
        help.txt (Global hotkeys + Main window hotkeys + mouse modes +
        Actions), not just 4 lines.
        """
        lines = ["QTranslate Version 6.10.0", ""]
        try:
            with open("C:/Program Files (x86)/QTranslate/Locales/English/"
                      "help.txt", encoding="utf-8-sig") as f:
                lines.append(f.read().strip())
        except Exception:
            lines.append("Double Ctrl => Show main window\n"
                         "Ctrl+Q => Translate selected text\n"
                         "Ctrl+E => Listen to selected text")
        return "\n".join(lines)

    def hist_back(self):
        """Alt+Left: previous translation in session history."""
        try:
            idx = getattr(self, "_hist_pos", len(self.history)) - 1
            if 0 <= idx < len(self.history):
                self._hist_pos = idx
                _, src, res = self.history[idx][:3]
                self.src.delete("1.0", "end")
                self.src.insert("1.0", src)
                self.render(res)
        except Exception:
            pass

    def hist_forward(self):
        """Alt+Right: next translation in session history."""
        try:
            idx = getattr(self, "_hist_pos",
                           len(self.history) - 1) + 1
            if 0 <= idx < len(self.history):
                self._hist_pos = idx
                _, src, res = self.history[idx][:3]
                self.src.delete("1.0", "end")
                self.src.insert("1.0", src)
                self.render(res)
        except Exception:
            pass

    def copy_to_source(self):
        """Ctrl+Up: copy translation to the text input box."""
        try:
            txt = self.out.get("1.0", "end").strip()
            if txt:
                self.src.delete("1.0", "end")
                self.src.insert("1.0", txt)
        except Exception:
            pass

    def open_service_page(self):
        import webbrowser
        try:
            _open_url(_dict_service_link(self.service))
        except Exception as e:
            self.render(f"[error] {e}")

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
            v = not self.opt_detect.get()
            self.opt_detect.set(v)
            _set_general("AlwaysDetectLanguage", v)

        def _toggle_backtr():
            v = not self.opt_backtr.get()
            self.opt_backtr.set(v)
            _set_general("BackTranslation", v)

        m = tk.Menu(self.root, tearoff=False)
        m.add_command(label=_T("Menus", 10, "Show dictionary window",
                               menu=5),
                      command=self.open_dict_window)
        m.add_command(label=_T("Menus", 20, "Show history window",
                               menu=5),
                      command=self.open_history_window)
        m.add_separator()
        m.add_checkbutton(label=_T("Menus", 30, "Always detect language",
                                   menu=4),
                          variable=self.opt_detect,
                          command=_toggle_detect)
        m.add_checkbutton(label=_T("Menus", 30, "Back translation",
                                   menu=1),
                          variable=self.opt_backtr,
                          command=_toggle_backtr)

        def _toggle_phonetic():
            # ReadPhonetically (menu Id 1/50): kept as flag; Google
            # TTS has no phonetic mode (documented, no-op for TTS).
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
        m.add_separator()
        m.add_command(label=_T("Menus", 80, "Options...", menu=5),
                      command=self.open_options)
        m.add_command(label=_T("Menus", 90, "About", menu=5),
                      command=self.show_about)
        try:
            m.tk_popup(self.root.winfo_pointerx(),
                       self.root.winfo_pointery())
        finally:
            m.grab_release()

    def on_new(self):
        """id1021 New: clear source + result for a fresh translation."""
        self.src.delete("1.0", "end")
        self.render("")

    def on_paste(self):
        if _HAS_KEYS:
            try:
                self.src.delete("1.0", "end")
                self.src.insert("1.0", pyperclip.paste())
            except Exception as e:
                self.render(f"[clipboard error] {e}")

    def on_mic(self):
        # Speech input chain (docs/NATIVE_ARCH.md): mic -> FLAC ->
        # Google full-duplex (needs dead API key). Offline fallback:
        # Windows SAPI shared recognizer when comtypes is installed
        # (pip install comtypes); otherwise explain.
        try:
            import comtypes.client  # type: ignore
        except ImportError:
            self.render("[speech input — needs: pip install comtypes "
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
                self.root.after(0, lambda: self.render(
                    "[listening... speak now (10s)]"))
                _t.sleep(10)
                grammar.DictationSetState(0)
                txt = " ".join(heard).strip()
                self.root.after(0, lambda: (
                    self.src.delete("1.0", "end"),
                    self.src.insert("1.0", txt)
                    if txt else self.render(
                        "[speech input — nothing recognized]")))
            except Exception as e:
                self.root.after(
                    0, lambda: self.render(f"[speech error] {e}"))

        import threading as _th
        _th.Thread(target=_work, daemon=True).start()

    # -- actions --
    def _mark_service(self):
        # current = sunken; multi-selected = groove highlight.
        for name, b in self.svc_btns.items():
            if name == self.service:
                b.config(relief="sunken")
            elif name in getattr(self, "multi_services", set()):
                b.config(relief="groove")
            else:
                b.config(relief="raised")

    def switch_service(self, name):
        """FUN_0045CDBA + FUN_0043A121: switch provider, re-run."""
        self.service = name
        self._mark_service()
        try:
            from qtranslate import config as _C
            _disp = _C.SERVICE_DISPLAY.get(
                {v: k for k, v in _C.SERVICE_NAMES.items()}.get(name),
                name.title())
            self.svc_link.config(text=_disp)
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
        text = self.src.get("1.0", "end").strip()
        if text:
            self.on_go()

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
            from qtranslate.theme import load_theme, window_colors
            global _COLORS
            _COLORS = window_colors(load_theme(name))
            self.root.configure(bg=_COLORS["back"])
        except Exception:
            pass

    def current(self):
        return (self.service,
                self.src.get("1.0", "end").strip(),
                LANG_CODES.get(self.tgt.get().strip(), "vi"),
                LANG_CODES.get(self.src_lang.get().strip(), "auto"))

    @staticmethod
    def tag_links(widget, text, on_click):
        """Shared auto-URL tagger (native EM_AUTOURLDETECT): qtdp: +
        http links, blue/underline/hand-cursor."""
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

    def render(self, text):
        # RichEdit auto-URL (native EM_AUTOURLDETECT + FUN_004266C6):
        # qtdp: links re-lookup internally, http links open browser.
        self.out.delete("1.0", "end")
        self.out.insert("1.0", text)
        self.tag_links(self.out, text, self._click_link)

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
            idx = self.out.index(f"@{event.x},{event.y}")
            ranges = self.out.tag_ranges("link")
            for i in range(0, len(ranges), 2):
                if self.out.compare(ranges[i], "<=", idx) and \
                        self.out.compare(idx, "<=", ranges[i + 1]):
                    url = self.out.get(ranges[i], ranges[i + 1])
                    if url.startswith("qtdp:"):
                        word = url[5:]
                        self.src.delete("1.0", "end")
                        self.src.insert("1.0", word)
                        self.open_dict_window()
                    else:
                        _open_url(url)
                    break
        except Exception:
            pass

    @staticmethod
    def _history_path():
        try:
            from qtranslate import config as _C
            import os as _o
            return _o.path.join(_o.path.dirname(_C.DEFAULT_PATH),
                                "History.json")
        except Exception:
            return "History.json"

    def _load_history(self):
        # Native persists translation history (History.json) and
        # restores it unless ClearHistoryOnExit.
        try:
            from qtranslate import config as _C
            import json as _j
            _g = _C.load().get("General", {})
            if _g.get("ClearHistoryOnExit", False):
                return []
            with open(self._history_path(),
                      encoding="utf-8") as f:
                items = _j.load(f)
            out = []
            if isinstance(items, list):
                for it in items[:500]:
                    try:
                        s, a, b, *rest = it
                        fav = bool(rest[0]) if rest else False
                        out.append((str(s), str(a), str(b), fav)
                                   if fav else (str(s), str(a), str(b)))
                    except Exception:
                        pass
            return out
        except Exception:
            return []

    def _save_history(self):
        try:
            from qtranslate import config as _C
            import json as _j
            _c = _C.load()
            if not _c.get("Contents", {}).get("SaveOnExit", True):
                return
            if _c.get("General", {}).get("ClearHistoryOnExit", False):
                try:
                    import os as _o
                    _o.remove(self._history_path())
                except OSError:
                    pass
                return
            with open(self._history_path(), "w",
                      encoding="utf-8") as f:
                _j.dump(self.history[-500:], f, ensure_ascii=False)
            # Contents.Edit* pane cache (native restores panes; note
            # SaveOnExit here is bool-like in the wild: True/1/"True").
            try:
                full = _C.load()
                _so = full.get("Contents", {}).get("SaveOnExit", True)
                if str(_so).lower() not in ("0", "false", "no", "") \
                        or _so is True or _so == 1:
                    full.setdefault("Contents", {})["EditSource"] = \
                        self.src.get("1.0", "end").strip()[:5000]
                    full["Contents"]["EditTranslation"] = \
                        self.out.get("1.0", "end").strip()[:5000]
                    with open(_C.DEFAULT_PATH, "w",
                              encoding="utf-8") as f:
                        _j.dump(full, f, ensure_ascii=False, indent=1)
            except Exception:
                pass
        except Exception:
            pass

    def _on_minimize(self, _e=None):
        # MinimizeToTrayOnMinimize (native 0x8070): withdraw to tray
        # on minimize instead of the taskbar.
        try:
            from qtranslate import config as _C
            if not bool(_C.load().get("General", {}).get(
                    "MinimizeToTrayOnMinimize", False)):
                return
            self.root.after(100, self.root.withdraw)
        except Exception:
            pass

    def on_close(self):
        # MinimizeToTrayOnClose (native 0x806F): hide to tray instead
        # of exiting; tray dbl-click / Show restores.
        try:
            from qtranslate import config as _C
            _to_tray = bool(_C.load().get("General", {}).get(
                "MinimizeToTrayOnClose", False))
        except Exception:
            _to_tray = False
        self._save_history()
        _save_placement("WindowMainPlacement", self.root)
        if _to_tray:
            try:
                self.root.withdraw()
                return
            except Exception:
                pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def push_hist(self, svc, src, res):
        self.history.append((svc, src, res))
        self._hist_pos = len(self.history) - 1

    @staticmethod
    def _persist_langs(src_code: str, tgt_code: str):
        # Native remembers the pair (General.LanguageFrom/To indices
        # into SupportedLanguages).
        try:
            from qtranslate import config as _C
            import json as _j
            _table = list(__import__(
                "qtranslate.services.google_translate",
                fromlist=["SUPPORTED_LANGS"]).SUPPORTED_LANGS)
            full = _C.load()
            try:
                full.setdefault("General", {})["LanguageFrom"] = \
                    _table.index(src_code)
            except ValueError:
                pass
            try:
                full["General"]["LanguageTo"] = _table.index(tgt_code)
            except ValueError:
                pass
            with open(_C.DEFAULT_PATH, "w",
                      encoding="utf-8") as f:
                _j.dump(full, f, ensure_ascii=False, indent=1)
        except Exception:
            pass

    def on_swap(self):
        a, b = self.src_lang.get(), self.tgt.get()
        if LANG_CODES.get(a, "auto") != "auto":
            self.tgt.set(a)
        self.src_lang.set(b if b else LANG_DISPLAY.get("auto", "auto"))
        self._persist_langs(
            LANG_CODES.get(self.src_lang.get().strip(), "auto"),
            LANG_CODES.get(self.tgt.get().strip(), "vi"))

    def toggle_multi_service(self, name):
        """Right-click: add/remove service from the multi-select set."""
        if name in self.multi_services:
            self.multi_services.discard(name)
        else:
            self.multi_services.add(name)
        self._mark_service()

    def on_go(self):
        svc, text, tgt, src = self.current()
        targets = [s for s in self.ordered_services()
                   if s in self.multi_services] or [svc]
        if len(targets) == 1:
            res = do_translate(targets[0], text, tgt, src,
                               self.opt_detect.get(),
                               self.opt_backtr.get())
            self.render(res)
            self.push_hist(targets[0], text[:120], res[:200])
        else:
            import threading as _th

            def _work():
                parts = []
                for s in targets:
                    try:
                        r = do_translate(s, text, tgt, src,
                                         self.opt_detect.get(),
                                         self.opt_backtr.get())
                    except Exception as e:
                        r = f"[error] {e}"
                    parts.append(f"===== {s} =====\n{r}")
                    try:
                        self.push_hist(s, text[:120], r[:200])
                    except Exception:
                        pass
                combined = "\n\n".join(parts)
                try:
                    self.root.after(
                        0, lambda: self.render(combined))
                except Exception:
                    pass

            self.render(f"translating via {len(targets)} services...")
            _th.Thread(target=_work, daemon=True).start()
            return
        # AutoCleanupOfTranslation: clear the source pane after a
        # successful translate (native 0x8077).
        try:
            from qtranslate import config as _C
            if _C.load().get("General", {}).get(
                    "AutoCleanupOfTranslation", False) and res \
                    and not res.startswith("No data"):
                self.src.delete("1.0", "end")
        except Exception:
            pass

    def on_clear(self):
        """Ctrl+N => Clear current translation (per help.txt)."""
        self.render("")

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
        cur = self.src.get("1.0", "end").strip()
        if _instant and len(cur) >= 2:
            try:
                if getattr(self, "_instant_after", None):
                    self.root.after_cancel(self._instant_after)
            except Exception:
                pass
            try:
                self._instant_after = self.root.after(
                    600, self.on_go)
            except Exception:
                pass
        if not _spell_on:
            return
        if len(cur) < 3 or len(cur) > 60:
            return
        try:
            sug = _spell.google_suggest(cur)
            self._suggestions = list(sug[:5])
            self.suggest.config(text=" | ".join(self._suggestions))
        except Exception:
            pass

    def accept_suggestion(self):
        """Ctrl+Space: accept the first suggestion into the source pane
        (native suggestion/autocomplete menu, help.txt)."""
        try:
            sug = getattr(self, "_suggestions", [])
            if sug:
                self.src.delete("1.0", "end")
                self.src.insert("1.0", sug[0])
                self.suggest.config(text="")
                self._suggestions = []
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
        # DLG 133: About + OK + 2 SysLinks (homepage, services credit).
        w = tk.Toplevel(self.root)
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

    # -- Options dialog (DLG 154 + pages; Basics page mirrors screenshot) --
    def open_options(self):
        try:
            from qtranslate import config as C
            cfg = C.load()
        except Exception:
            cfg = {}
        w = tk.Toplevel(self.root)
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
            self._opt_vars = getattr(self, "_opt_vars", {})
            import winreg as _wr
            try:
                _rk = _wr.OpenKey(
                    _wr.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run")
                _wr.QueryValueEx(_rk, "QTranslate")
                _startup = True
            except Exception:
                _startup = False
            _sv = tk.BooleanVar(value=_startup)
            self._opt_vars["startup"] = _sv  # keep ref: no GC-uncheck
            tk.Checkbutton(body, text=_Cw(10, 1045, "Start with Windows"),
                           variable=_sv,
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
            for lab, vals, default in (
                    (_Cw(10, 1070, "Interface language:"), _langs, _cur_lang),
                    (_Cw(10, 1075, "Font name:"), ["--- Default ---"], "--- Default ---"),
                    (_Cw(10, 1074, "Text size:"), ["9"], str(_gen.get("TextSize", 9)))):
                r = tk.Frame(body, bg=_COLORS["back"])
                r.pack(fill="x", pady=1)
                tk.Label(r, text=lab, width=18, anchor="w",
                         bg=_COLORS["back"],
                         fg=_COLORS["text"]).pack(side="left")
                cb = ttk.Combobox(r, values=vals, width=26,
                                  state="readonly")
                cb.pack(side="left")
                cb.set(default)
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
            tk.Label(body, text=_Cw(10, 1064, "History"), bg=_COLORS["back"],
                     fg=_COLORS["text"],
                     font=("Segoe UI", 10, "bold")).pack(anchor="w",
                                                         pady=(8, 0))
            for lab, default in (
                    (_Cw(10, 1122, "Enable history"),
                     _gen.get("EnableHistory", True)),
                    (_Cw(10, 1124, "Clear history on exit"),
                     _gen.get("ClearHistoryOnExit", True)),
                    (_Cw(10, 1123, "Expand items"),
                     _gen.get("ExpandHistoryItems", False))):
                v = tk.BooleanVar(value=bool(default))
                self._opt_vars[lab] = v  # keep ref: no GC-uncheck
                tk.Checkbutton(body, text=lab, variable=v,
                               bg=_COLORS["back"], fg=_COLORS["text"],
                               selectcolor=_COLORS["back"]).pack(anchor="w")

        def show_appearance():
            # mirrors DLG 175; all values live from the real
            # Options.json Appearance section (verified keys).
            for c in body.winfo_children():
                c.destroy()
            _ap = cfg.get("Appearance", {})
            self._opt_vars = getattr(self, "_opt_vars", {})
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
                    lambda e: self.apply_theme(th.get()))
            for lab, key in ((_Cw(14, 1158, "Enable auto size"), "PopupAutoSize"),
                             (_Cw(14, 1160, "Enable auto position"), "PopupAutoPos"),
                             (_Cw(14, 1159, "Always activate"), "PopupAutoFocus"),
                             (_Cw(14, 1161, "Pin when dragging"),
                              "PopupPinWhenDragging"),
                             (_Cw(14, 1123, "Enable window style"),
                              "EnableWindowStyle")):
                vv = tk.BooleanVar(value=bool(_ap.get(key, False)))
                self._opt_vars[key] = vv
                tk.Checkbutton(body, text=lab, variable=vv,
                               bg=_COLORS["back"], fg=_COLORS["text"],
                               selectcolor=_COLORS["back"]).pack(anchor="w")
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
                self._opt_vars[key] = ee
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
                self._opt_vars[f"PopupIcons_{bit}"] = vv

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
                self._opt_vars[key] = ee

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
            self._opt_vars = getattr(self, "_opt_vars", {})
            v = tk.BooleanVar(value=bool(hk.get("EnableHotKeys", True)))
            self._opt_vars["EnableHotKeys"] = v
            tk.Checkbutton(body, text=_Cw(16, 1118, "Enable hot keys"),
                           variable=v,
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
                    # state bits: Shift=0x1, CapsLock ignored,
                    # Control=0x4, Alt/Mod1=0x8|0x20000..., Win/Mod4
                    if e.state & 0x1:
                        mods |= 4
                    if e.state & 0x4:
                        mods |= 2
                    if e.state & 0x8:
                        mods |= 1
                    try:
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
            from qtranslate.services import dictionary as _D
            _names = dict(C2.SERVICE_DISPLAY)
            _dnames = dict(C2.DICT_DISPLAY)
            self._opt_vars = getattr(self, "_opt_vars", {})

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
                from qtranslate.services import google_translate as _G
                # SUPPORTED_LANGS[0] is -1 placeholder; native table
                # is indexed with it (1=auto, 17=en, 57=vi)
                _table = list(_G.SUPPORTED_LANGS)
            except Exception:
                _table = [-1, "auto", "en", "vi"]
            _names_l = [("auto (auto-detect)" if c == "auto" else c)
                        for c in _table]
            _gen = cfg.get("General", {})
            _dis_l = set(cfg.get("DisabledLanguages", []))
            _pairs = [list(p) for p in cfg.get("LanguagePairs",
                                               [[57, 17], [17, 57]])]
            self._opt_vars = getattr(self, "_opt_vars", {})

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
            for lab, key in (("Translate from:", "LanguageFrom"),
                             ("Translate to:", "LanguageTo"),
                             ("Dictionary:", "LanguageDictionary"),
                             ("Virtual keyboard:", "LanguageKeyboard")):
                _cb[key] = _idx_combo(body, lab,
                                      _gen.get(key, 17) or 0)
                _cb[key].bind("<<ComboboxSelected>>",
                              lambda e, k=key: (
                                  _gen.__setitem__(
                                      k, _names_l.index(_cb[k].get())),
                                  _save_l()))
            for lab, key in (("Always detect language",
                              "AlwaysDetectLanguage"),
                             ("Smart detection", "UseSmartDetection")):
                vv = tk.BooleanVar(value=bool(_gen.get(key, False)))
                self._opt_vars[key] = vv
                tk.Checkbutton(
                    body, text=lab, variable=vv, bg=_COLORS["back"],
                    fg=_COLORS["text"], selectcolor=_COLORS["back"],
                    command=lambda k=key: (
                        _gen.__setitem__(k, self._opt_vars[k].get()),
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
            self._opt_vars = getattr(self, "_opt_vars", {})

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
            self._opt_vars = getattr(self, "_opt_vars", {})
            self._opt_vars["UseSmartDetection_x"] = _sv

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
            self._opt_vars = getattr(self, "_opt_vars", {})

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
                self._opt_vars[key] = vv
                tk.Checkbutton(
                    body, text=lab, variable=vv, bg=_COLORS["back"],
                    fg=_COLORS["text"], selectcolor=_COLORS["back"],
                    command=lambda k=key: (
                        _ad2.__setitem__(k, self._opt_vars[k].get()),
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
            tk.Button(body, text=_Cw(18, 1190, "Check now"),
                      command=lambda: self.render(
                          "update server offline (checker 404s)")).pack(
                              anchor="w", pady=2)
            tk.Label(body, text="QTranslate 6.10.0 — update server is "
                                "offline (update checker 404s; nothing to "
                                "fetch).", bg=_COLORS["back"],
                     fg="gray", wraplength=380,
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

    # -- History window (DLG 164, 316x177: SysTreeView32 id83 +
    # Clear id1067 + Save as... id1160; NO Open button. Double-click
    # loads the item back into the main window.)
    def open_history_window(self):
        w = tk.Toplevel(self.root)
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
        tv.pack(fill="both", expand=True, padx=8, pady=8)

        def _paint():
            for i in tv.get_children():
                tv.delete(i)
            try:
                from qtranslate import config as _C
                _fav_only = bool(_C.load().get(
                    "Application", {}).get("HistoryFilterFavorites",
                                           False))
            except Exception:
                _fav_only = False
            for idx, (svc, src, *_) in enumerate(self.history):
                fav = len(self.history[idx]) > 3 \
                    and self.history[idx][3]
                if _fav_only and not fav:
                    continue
                tv.insert("", "end", iid=str(idx),
                          text=src[:70],
                          values=("★" if fav else "", svc))

        _paint()

        def load_sel(_e=None):
            try:
                sel = tv.selection()[0]
                idx = int(sel)
                _, src, res = self.history[idx][:3]
                self.src.delete("1.0", "end")
                self.src.insert("1.0", src)
                self.render(res)
            except Exception:
                pass

        tv.bind("<Double-1>", load_sel)

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
                  command=self.on_export_history).pack(side="left", padx=4)

    def clear_history(self):
        self.history.clear()

    def on_export_history(self):
        try:
            from qtranslate import config as _C
            _app = _C.load().get("Application", {})
            _init = _app.get("SaveHistoryPath", "") or None
        except Exception:
            _init, _app = None, {}
        path = filedialog.asksavefilename(title="Export history",
                                          defaultextension=".html",
                                          initialdir=_init,
                                          initialfile=_init)
        if not path:
            return
        try:
            import os as _o
            from qtranslate import config as _C2
            import json as _j
            full = _C2.load()
            full.setdefault("Application", {})["SaveHistoryPath"] = path
            with open(_C2.DEFAULT_PATH, "w",
                      encoding="utf-8") as f:
                _j.dump(full, f, ensure_ascii=False, indent=1)
        except Exception:
            pass
        try:
            from qtranslate import history as H
            data = H.html_export([(s, src, "auto", res, self.target)
                                  for (s, src, res, *_) in self.history])
            with open(path, "w", encoding="utf-8") as f:
                f.write(data if isinstance(data, str) else str(data))
            self.render(f"exported {len(self.history)} items -> {path}")
        except Exception as e:
            self.render(f"[export error] {e}")

    # -- Dictionary window (DLG 184: multi-service cards) --
    def open_dict_window(self):
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
        except Exception:
            _dcfg, _dorder = {}, [10, 19, 20, 14, 17, 18, 22, 24, 25,
                                  26, 29]
        try:
            _disp = _C.DICT_DISPLAY
        except Exception:
            _disp = {}
        _zoom = _dcfg.get("DictionaryZoom", -1)
        _font = max(6, 11 + (0 if _zoom in (-1, None) else int(_zoom)))
        w = tk.Toplevel(self.root)
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
        tk.Checkbutton(frm, text="Exact", variable=_exact_v,
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
            if _exact_v.get():
                word_q = word
            else:
                word_q = word
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
                            _frag = _X.lookup(word_q, _xp)
                            if _frag:
                                cards.append(("xdxf", _xp.split(
                                    "/")[-1].split("\\")[-1],
                                    _frag[:8000]))
                        except Exception:
                            pass
                except Exception:
                    pass
                for sid in sids:
                    key = {_v: _k for _k, _v in _disp.items()
                           }.get(_disp.get(sid, ""), "")
                    fn = DICTS.get(
                        _ID2FN.get(
                            _disp.get(sid, "").lower().split()[0], ""))
                    if fn is None:
                        continue
                    try:
                        frag = fn(word_q, "en", self.target)
                        if frag:
                            cards.append((str(sid), _disp.get(sid, str(
                                sid)), frag[:8000]))
                    except Exception:
                        pass
                page = DR.render_cards(cards)
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
                    self.tag_links(
                        out, summary,
                        lambda e: self._click_link_dict(out, e))

                self.root.after(0, _show)
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

    def on_ocr(self):
        # Default = ScreenCaptureWindow region select (native flow).
        self._ocr_region()

    def on_ocr_file(self):
        path = filedialog.askopenfilename(title="Image for OCR")
        if not path:
            return
        try:
            with open(path, "rb") as f:
                self._ocr_bytes(f.read())
        except Exception as e:
            self.render(f"[ocr error] {e}")

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
            _lang = {"en": "eng", "vi": "vie", "fr": "fre",
                     "de": "ger", "es": "spa", "ru": "rus",
                     "ja": "jpn", "ko": "kor",
                     "zh-CN": "chs"}.get(_code, "eng")
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
            self.src.delete("1.0", "end")
            self.src.insert("1.0", txt)
        except Exception as e:
            self.render(f"[ocr error] {e}")

    def _ocr_region(self):
        """Rubber-band screen region -> ImageGrab -> OCR (native
        ScreenCaptureWindow selection flow). Esc cancels."""
        try:
            from PIL import ImageGrab
        except ImportError:
            self.render("[ocr needs Pillow: pip install Pillow]")
            return
        ov = tk.Toplevel(self.root)
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
                _th.Thread(target=self._ocr_bytes,
                           args=(buf.getvalue(),),
                           daemon=True).start()
            except Exception as ex:
                self.render(f"[ocr error] {ex}")

        cv.bind("<Button-1>", _down)
        cv.bind("<B1-Motion>", _drag)
        cv.bind("<ButtonRelease-1>", _up)
        ov.bind("<Escape>", lambda e: ov.destroy())
        ov.focus_force()

    def open_keyboard(self):
        """Virtual keyboard window (DLG 162: 308x102).

        Clicking a key types it into the source pane (like the native
        on-screen keyboard feeding the edit control). Key labels follow
        General.LanguageKeyboard via the JCUKEN map (17=en default).
        """
        w = tk.Toplevel(self.root)
        w.title(_W(7, "Virtual keyboard"))
        w.configure(bg=_COLORS["back"])
        _place_aux(w, "WindowKeyboardPlacement", "308x102")
        w.attributes("-topmost", True)
        try:
            from qtranslate import config as _C
            _kb = _C.load().get("General", {}).get("LanguageKeyboard",
                                                   17)
        except Exception:
            _kb = 17
        try:
            from qtranslate.layout import EN2RU
            _ru = (_kb != 17)
        except Exception:
            EN2RU, _ru = {}, False
        rows = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
        for row in rows:
            frm = tk.Frame(w, bg=_COLORS["back"])
            frm.pack()
            for ch in row:
                label = EN2RU.get(ch, ch) if _ru else ch
                tk.Button(frm, text=label, width=3,
                          command=lambda c=label: self.src.insert(
                              "insert", c)).pack(
                    side="left", padx=1, pady=1)
        frm = tk.Frame(w, bg=_COLORS["back"])
        frm.pack(pady=2)
        tk.Button(frm, text="Space", width=20,
                  command=lambda: self.src.insert("insert", " ")).pack(
            side="left", padx=2)
        tk.Button(frm, text="⌫", width=5,
                  command=lambda: self.src.delete(
                      "insert-1c", "insert")).pack(side="left", padx=2)


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
    # native hotkey flow shows a separate popup (TaskShowPopupWindow),
    # not just the main window
    try:
        app.root.after(0, lambda: show_popup(text[:300], res, svc, tgt))
    except Exception:
        pass


_MOUSE_MON = {"active": None}


def _toggle_mouse_mode(app):
    """Closest port of HotKeySwitchMouseMode without a cursor hook.

    Cycles General.MouseMode 0=off -> 1=popup-monitor -> 2=main-monitor
    using the clipboard-sequence monitor (copy = the selection event).
    True cursor-side icon/hover needs a Win32 hook (documented limit).
    """
    try:
        from qtranslate import config as _C
        import json as _j
        full = _C.load()
        mode = (int(full.setdefault("General", {}).get("MouseMode", 0))
                + 1) % 3
        full["General"]["MouseMode"] = mode
        full["General"]["MouseModeOn"] = mode != 0
        with open(_C.DEFAULT_PATH, "w", encoding="utf-8") as f:
            _j.dump(full, f, ensure_ascii=False, indent=1)
    except Exception:
        return
    try:
        if _MOUSE_MON["active"] is not None:
            _MOUSE_MON["active"][0] = False
            _MOUSE_MON["active"] = None
        if mode != 0:
            _MOUSE_MON["active"] = start_clipboard_monitor(
                app, popup=(mode == 1))
        print(f"mouse mode: {['off', 'popup on copy', 'main on copy'][mode]}"
              " (cursor icon/hover needs Win32 hook)")
    except Exception as e:
        print(f"mouse mode failed: {e}")


def start_clipboard_monitor(app, interval_ms: int = 800,
                            popup: bool = False):
    """Port of TaskTranslateClipboard: poll GetClipboardSequenceNumber,
    translate new text clipped copies into main (or popup) window.

    Native mouse-mode variants (show icon/translation/translation+read)
    need the cursor hook; this covers the clipboard-monitor core:
    Ctrl+C anywhere -> auto-translate, with the exclusion gate.
    """
    if not _HAS_KEYS:
        return None
    try:
        from ctypes import windll
        _seq = windll.user32.GetClipboardSequenceNumber
    except Exception:
        return None
    try:
        last = [_seq()]
    except Exception:
        return None
    _active = [True]

    def _poll():
        if not _active[0]:
            return
        try:
            cur = _seq()
        except Exception:
            cur = last[0]
        if cur != last[0]:
            last[0] = cur
            try:
                from qtranslate.exclusions import foreground_excluded
                if foreground_excluded():
                    raise RuntimeError("excluded")
                import pyperclip as _pc
                text = _pc.paste().strip()
            except Exception:
                text = ""
            if text and len(text) < 5000:
                svc, _, tgt, _ = app.current()
                try:
                    res = do_translate(svc, text[:5000], tgt, "auto",
                                       app.opt_detect.get(),
                                       app.opt_backtr.get())
                    app.src.delete("1.0", "end")
                    app.src.insert("1.0", text[:2000])
                    app.render(res)
                    app.push_hist(svc, text[:120], res[:200])
                    if popup:
                        show_popup(text[:300], res, svc, tgt)
                except Exception:
                    pass
        try:
            app.root.after(interval_ms, _poll)
        except Exception:
            pass

    try:
        app.root.after(interval_ms, _poll)
    except Exception:
        return None
    return _active


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


def on_dict_hotkey(app):
    """Ctrl+Shift+Q => Show dictionary window (per help.txt)."""
    if not _HAS_KEYS:
        return
    try:
        text = pyperclip.paste().strip()
    except Exception:
        return
    if text:
        app.src.delete("1.0", "end")
        app.src.insert("1.0", text[:2000])
    app.open_dict_window()


def on_listen_hotkey(app):
    """Ctrl+E => Listen to selected text (per help.txt)."""
    if not _HAS_KEYS:
        return
    try:
        text = pyperclip.paste().strip()
    except Exception:
        return
    if not text:
        return
    _, _, tgt, _ = app.current()
    threading.Thread(target=speak, args=(text[:500], tgt),
                     daemon=True).start()


def _hotkey_to_combo(code: int) -> str:
    """Options.json hotkey dword -> `keyboard` combo string.

    FUN_00405A17 packs vk | (modifiers << 8): bit0=Alt, bit1=Ctrl,
    bit2=Shift, bit3=Win (matches format_hotkey in config.py).
    """
    if not code:
        return ""
    vk = code & 0xFF
    mods = (code >> 8) & 0xF
    parts = []
    if mods & 2:
        parts.append("ctrl")
    if mods & 4:
        parts.append("shift")
    if mods & 1:
        parts.append("alt")
    if mods & 8:
        parts.append("windows")
    if vk:
        if vk in (0x08, 0x09, 0x0D, 0x1B, 0x20, 0x2E):
            parts.append({0x08: "backspace", 0x09: "tab",
                          0x0D: "enter", 0x1B: "esc", 0x20: "space",
                          0x2E: "delete"}[vk])
        elif 0x20 <= vk < 0x7F:
            parts.append(chr(vk).lower())
        else:
            return ""
    return "+".join(parts)


def _register_native_hotkeys(app) -> list:
    """Register exactly the HotKeys bound in Options.json.

    Action routing mirrors help.txt global hotkeys: PopupWindow =>
    popup translate, MainWindow => show main, ReplaceSelection =>
    replace with translation, ListenText/ListenTranslation => speak,
    Dictionary/DictionaryClipboard => dictionary window, History =>
    history, Keyboard => virtual keyboard, ConvertTextLayout => fix
    layout, CopyTranslation => copy result, SpeechInput =>
    mic (not ported, noted), TextRecognition => OCR,
    SwitchMouseMode => toggle flag (noted),
    TranslateClipboard* => translate clipboard (main/popup/none).
    """
    try:
        from qtranslate import config as _C
        hk = _C.load().get("HotKeys", {})
        enabled = hk.get("EnableHotKeys", True)
    except Exception:
        return []
    if not enabled:
        print("  hotkeys disabled (EnableHotKeys=false)")
        return []

    def _show_main():
        try:
            app.root.after(0, lambda: (app.root.deiconify(),
                                       app.root.lift(),
                                       app.root.focus_force()))
        except Exception:
            pass

    def _replace():
        # Alt+W native: translate selection, retype into the app
        if not _HAS_KEYS:
            return
        try:
            import pyperclip as _pc
            text = _pc.paste().strip()
        except Exception:
            return
        if not text:
            return
        svc, _, tgt, _ = app.current()
        res = do_translate(svc, text[:5000], tgt, "auto",
                           app.opt_detect.get(), app.opt_backtr.get())
        try:
            import pyperclip as _pc2
            _pc2.copy(res)
            keyboard.write(res[:2000])
        except Exception:
            pass
        app.src.delete("1.0", "end")
        app.src.insert("1.0", text[:2000])
        app.render(res)

    def _copy_result():
        try:
            import pyperclip as _pc
            _pc.copy(app.out.get("1.0", "end").strip())
        except Exception:
            pass

    def _ocr():
        app.root.after(0, app.on_ocr)

    _monitors = {"main": None, "popup": None}

    def _mon_main():
        if _monitors["main"] is None:
            _monitors["main"] = start_clipboard_monitor(app,
                                                        popup=False)
            print("clipboard monitor -> main window: on")
        else:
            _monitors["main"][0] = False
            _monitors["main"] = None
            print("clipboard monitor -> main window: off")

    def _mon_popup():
        if _monitors["popup"] is None:
            _monitors["popup"] = start_clipboard_monitor(app,
                                                         popup=True)
            print("clipboard monitor -> popup: on")
        else:
            _monitors["popup"][0] = False
            _monitors["popup"] = None
            print("clipboard monitor -> popup: off")

    _actions = {
        "HotKeyPopupWindow": lambda: on_hotkey(app),
        "HotKeyMainWindow": _show_main,
        "HotKeyReplaceSelection": _replace,
        "HotKeyListenText": lambda: on_listen_hotkey(app),
        "HotKeyListenTranslation": lambda: app.root.after(
            0, app.on_listen),
        "HotKeyDictionary": lambda: on_dict_hotkey(app),
        "HotKeyDictionaryClipboard": lambda: on_dict_hotkey(app),
        "HotKeyHistory": lambda: app.root.after(
            0, app.open_history_window),
        "HotKeyKeyboard": lambda: app.root.after(
            0, app.open_keyboard),
        "HotKeyConvertTextLayout": on_layout_hotkey,
        "HotKeyCopyTranslation": _copy_result,
        "HotKeyTextRecognition": _ocr,
        "HotKeyTranslateClipboard": lambda: on_hotkey(app),
        "HotKeyTranslateClipboardInMainWindow": _mon_main,
        "HotKeyTranslateClipboardInPopupWindow": _mon_popup,
        "HotKeySpeechInput": lambda: app.root.after(0, app.on_mic),
        "HotKeySwitchMouseMode": lambda: _toggle_mouse_mode(app),
    }
    bound = []
    for name, fn in _actions.items():
        try:
            combo = _hotkey_to_combo(hk.get(name, 0) or 0)
        except Exception:
            combo = ""
        if not combo:
            continue
        try:
            keyboard.add_hotkey(combo, fn)
            bound.append(f"{name}={combo}")
        except Exception as e:
            print(f"  hotkey {name} ({combo}) failed: {e}")
    return bound


def _seed_service_options():
    """Seed the JS-runtime Options store (common.Options) from
    Options.json: Advanced.PreferredDomain + locale LanguageCode.

    Native UtilsDispatch runs addOption() per service at boot; without
    this the ports fall back to hardcoded defaults.
    """
    try:
        from qtranslate import common as _cm
        from qtranslate import config as _C
        cfg = _C.load()
        adv = cfg.get("Advanced", {})
        if adv.get("PreferredDomain"):
            _cm.add_option("PreferredDomain", adv["PreferredDomain"])
        loc = cfg.get("General", {}).get("LocaleFoderName", "")
        if loc:
            _cm.add_option("LanguageCode", loc[:2].lower())
    except Exception:
        pass


def _consume_crash_reports():
    """Port of FUN_00462C03: read Exceptions.json (minidump list from
    the previous run's exception filter), report type==2 entries once,
    then delete the file."""
    try:
        from qtranslate import config as _C
        import json as _j
        import os as _o
        _p = _o.path.join(_o.path.dirname(_C.DEFAULT_PATH),
                          "Exceptions.json")
        if not _o.path.exists(_p):
            return
        try:
            entries = _j.load(open(_p, encoding="utf-8"))
        except Exception:
            entries = []
        for e in (entries or []):
            try:
                if isinstance(e, dict) and e.get("type") == 2:
                    print(f"[previous crash] {e.get('path', e)}")
            except Exception:
                pass
        try:
            _o.remove(_p)
        except OSError:
            pass
    except Exception:
        pass


def _install_crash_hook():
    """Unhandled-exception filter: append a type==2 entry to
    Exceptions.json so the next launch reports it once (native
    minidump-writer equivalent; no dump, just the traceback)."""
    import sys as _sys
    import traceback as _tb

    def _hook(typ, val, tb):
        try:
            from qtranslate import config as _C
            import json as _j
            import os as _o
            _p = _o.path.join(_o.path.dirname(_C.DEFAULT_PATH),
                              "Exceptions.json")
            try:
                entries = _j.load(open(_p, encoding="utf-8"))
            except Exception:
                entries = []
            entries.append({"type": 2,
                            "path": "".join(
                                _tb.format_exception(typ, val,
                                                     tb))[-2000:]})
            open(_p, "w", encoding="utf-8").write(
                _j.dumps(entries, ensure_ascii=False))
        except Exception:
            pass
        _sys.__excepthook__(typ, val, tb)

    _sys.excepthook = _hook


def main():
    _seed_service_options()
    _consume_crash_reports()
    _install_crash_hook()
    root = tk.Tk()
    app = App(root)
    # MainWindowStartupAction (0=normal, 1=minimized, 2=tray) +
    # MainWindowShowOnLoad=false (start hidden, tray shows it).
    try:
        from qtranslate import config as _C
        _g = _C.load().get("General", {})
        _act = int(_g.get("MainWindowStartupAction", 0))
        if not _g.get("MainWindowShowOnLoad", True) or _act == 2:
            root.withdraw()
        elif _act == 1:
            try:
                root.iconify()
            except Exception:
                pass
    except Exception:
        pass
    print(f"qtranslate-re main window running "
          f"(services: {len(TRANSLATORS)} translate + {len(DICTS)} dict)")
    print("  Ctrl+Q: popup translate | Ctrl+Shift+Q: dictionary | "
          "Ctrl+E: listen | Ctrl+Alt+L: fix layout")
    if _HAS_KEYS:
        # Global hotkeys from Options.json HotKeys (native FUN_00405A17
        # registrar): only bound entries register. Double Ctrl => show
        # main window (native FUN_00417DCE double-press matcher).
        # In-window shortcuts (Ctrl+Enter/N/D/H/K/Tab/I/Space/F1/F11)
        # stay as Tk bindings in _build_main per help.txt.
        import time as _time
        _last_ctrl = [0.0]
        _last_c = [0.0]

        def _ctrl_tap():
            now = _time.time()
            if now - _last_ctrl[0] < 0.5:
                try:
                    root.lift()
                    root.focus_force()
                except Exception:
                    pass
            _last_ctrl[0] = now

        def _c_tap(e):
            # TaskCopySelection: Ctrl+C+C flow — double-tap C while
            # holding Ctrl: synthesize copy, translate clipboard.
            now = _time.time()
            if keyboard.is_pressed("ctrl") and now - _last_c[0] < 0.5:
                _last_c[0] = 0.0
                try:
                    keyboard.send("ctrl+c")
                except Exception:
                    pass
                root.after(300, lambda: on_hotkey(app))
            else:
                _last_c[0] = now

        keyboard.on_press_key("ctrl", lambda e: _ctrl_tap())
        keyboard.on_press_key("c", _c_tap)
        _bound = _register_native_hotkeys(app)
        print(f"  hotkeys bound from Options.json: "
              f"{', '.join(_bound) if _bound else '(none)'}")
    else:
        print("pip install keyboard pyperclip for global hotkeys")
    # System tray (native FUN_00418B69 states: off/partial/on).
    # Left-click toggles mouse mode, double-click shows main window.
    # Requires `pip install pystray Pillow`; silently skipped if absent.
    try:
        _tray = _make_tray(root, app)
        if _tray is not None:
            import threading as _th
            _th.Thread(target=_tray.run, daemon=True).start()
            print("  tray icon running (dbl-click = show main window)")
    except Exception as _e:
        print(f"  tray unavailable: {_e}")
    root.mainloop()


def _make_tray(root, app):
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
        # hotkey-state -> tray icon: any HotKey bound = on, else off
        # (partial = mouse-mode armed without hotkeys).
        try:
            from qtranslate import config as _C
            hk = _C.load().get("HotKeys", {})
            _any = any(hk.get(n, 0) for n in _C.HOTKEY_NAMES)
        except Exception:
            _any = False
        try:
            if _mouse_mode[0] and not _any:
                icon.icon = _imgs["partial"]
            elif _any or _mouse_mode[0]:
                icon.icon = _imgs["on"]
            else:
                icon.icon = _imgs["off"]
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
                if _A._MOUSE_MON["active"] is None:
                    _A._MOUSE_MON["active"] = \
                        _A.start_clipboard_monitor(app, popup=True)
            elif _A._MOUSE_MON["active"] is not None:
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

    menu = Menu(
        MenuItem("Show main window", _open(app.root.lift),
                 default=True),
        MenuItem("Dictionary", _open(app.open_dict_window)),
        MenuItem("History", _open(app.open_history_window)),
        MenuItem("Virtual keyboard", _open(app.open_keyboard)),
        MenuItem("Options...", _open(app.open_options)),
        Menu.SEPARATOR,
        MenuItem("Mouse mode: show icon", _toggle,
                 checked=lambda item: _mouse_mode[0]),
        Menu.SEPARATOR,
        MenuItem("Exit", _quit))
    icon = pystray.Icon("QTranslate", _img, "QTranslate",
                        menu)
    try:
        icon.on_activate = lambda i: _show()  # double-click
    except Exception:
        pass
    _sync_icon(icon)
    return icon


def show_popup(source, result, service="google", target="vi"):
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
        from qtranslate.theme import load_theme, window_colors
        from qtranslate import config as _C
        _tn = _C.load().get("Appearance", {}).get("ThemeName", "")
        _pc = window_colors(load_theme(_tn or "Flat Dark"))
    except Exception:
        _pc = _COLORS
    win.configure(bg=_pc.get("border", "#7a7a7a"))
    inner = tk.Frame(win, bg=_pc.get("back", "#f0f0f0"))
    inner.pack(fill="both", expand=True, padx=1, pady=1)
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

    def _to_main(_e=None):
        win.destroy()
        try:
            from qtranslate import app as _A
            _r = tk.Tk()
            _a = _A.App(_r)
            _a.src.delete("1.0", "end")
            _a.src.insert("1.0", source)
            _a.render(result)
            _r.mainloop()
        except Exception:
            pass

    txt.bind("<Double-1>", _to_main)
    win.bind("<Escape>", lambda e: win.destroy())


if __name__ == "__main__":
    main()
