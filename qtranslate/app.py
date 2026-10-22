"""Runnable clone of the QTranslate main window (Windows).

Faithful to DLG 129 in QTranslate.exe `.rsrc` (340x201, 17 controls):
  - service icon row (custom Dl control id108 — here as small buttons
    with service names; same function: click = switch + re-translate,
    cf. FUN_0045CDBA service switcher)
  - source RichEdit (id1000) / result RichEdit (id1017) with separator
    (native's third small pane, id1018, is built too -- it is the `aux`
    strip; the main window's own body lives in
    `qtranslate.windows.MainWindow` since Phase 7 (6/6))
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
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, ttk

sys.path.insert(0, ".")

# `keyboard` crashes at import on macOS Cocoa (a process-level abort,
# not a catchable Python exception), so it is only imported on Windows
# where the app actually uses global hotkeys. `pyperclip` is safe on any
# platform and is used for clipboard read/write regardless of hotkeys.
_HAS_KEYS = False
if sys.platform == "win32":
    try:
        import keyboard
        import pyperclip
        _HAS_KEYS = True
    except Exception:
        pass
else:
    try:
        import pyperclip
    except Exception:
        pass

# NOTE (Phase 2 slice 2026-10-15): provider modules moved to
# qtranslate/registry.py, which is tkinter-free. app.py must NOT import
# them directly any more — use ``from qtranslate import registry`` at the
# call site (lazy, to keep module import order stable). The one remaining
# direct use was ``_spell.google_suggest`` (now ``registry.google_suggest``)
# plus local ``SUPPORTED_LANGS`` imports (unchanged: they read a constant).

SERVICE = sys.argv[1] if len(sys.argv) > 1 else "google"
TARGET = sys.argv[2] if len(sys.argv) > 2 else "vi"
THEME = sys.argv[3] if len(sys.argv) > 3 else "Blue"
# Explicit CLI args win over the restored session (native behavior:
# an explicit launch overrides the remembered service/pair).
_CLI_SERVICE = len(sys.argv) > 1
_CLI_TARGET = len(sys.argv) > 2
# Same parse, factored for testing (qtranslate/cli.py, row A9). Values
# above are kept as module attributes because live code and ui_match read
# A.SERVICE / A.TARGET / A.THEME directly.
from qtranslate.cli import parse_args as _parse_args  # noqa: E402
assert _parse_args(sys.argv[1:])[:5] == (
    SERVICE, TARGET, THEME, _CLI_SERVICE, _CLI_TARGET)

def _default_colors():
    """Main-window colors from the real Options.json Appearance section.

    The native main window does NOT use Themes/*.json (those are for
    popups); it uses ColorBack/ColorText/ColorFrame from Appearance
    (verified: ColorBack=15790320=#F0F0F0, ColorText=0, ColorFrame=8023133
    on this machine). Falls back to the THEME arg when set.
    """
    if THEME != "Blue":
        try:
            from qtranslate.theme import load_theme, tk_colors, window_colors
            return tk_colors(window_colors(load_theme(THEME)))
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

# The port's OWN separator for a combined result string. This text is a port
# invention -- a UTF-16LE search of the recovered image finds no
# "back-translation" and no "--- back" literal
# (D10_SPOTCHECK_Contents_2026-10-10.md §4a), and native has no need for one:
# DLG129's third RichEdit (1018) IS the back-translation control, addressed by
# Contents.EditBackTranslation (+0x17c). `render()` splits on this only to
# keep a single-argument caller working.
BACKTR_MARKER = "--- back-translation ---"

# Size of a service-strip icon, in PIXELS. The native's icons are 16x16
# (recovered from the installer payload; see
# `qtranslate/assets/service_icons/manifest.json`), and the native draws them
# at that size in the main window's bottom strip.
#
# The unit matters: Tk reads a button's `width`/`height` as CHARACTERS for a
# text button and as PIXELS for an image button. The strip's buttons always
# carry an image, so these are pixels -- but the constant is named to keep
# that from being re-broken by a well-meaning change.
SVC_ICON_PX = 16

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


# Per-slot language defaults, as INDICES into the shared
# SupportedLanguages table: From = 1 (auto), To = 57 (vi),
# Dictionary = 17 (en), Keyboard = 17 (en).
#
# These were stated in the Options "Languages" page -- but native has
# NO such page (native's is DLG174, the language checklist), so the
# table moved to where its four consumers live: the main window's
# from/to pair, the dictionary window and the virtual keyboard.
LANG_DEFAULTS = {"LanguageFrom": 1, "LanguageTo": 57,
                 "LanguageDictionary": 17, "LanguageKeyboard": 17}

SRC_LANG_NAMES = [LANG_DISPLAY[c] for c in LANGS]
TO_LANG_NAMES = [LANG_DISPLAY[c] for c in TO_LANGS]


def _strip_html(h):
    """Dictionary-card summary text, via the verified native port.

    This used to be a second, simpler implementation. It diverged from
    ``common.strip_html`` (the measured port of Common.js ``stripHtml``)
    in ways that change displayed text:

      * ``<br>`` became a space instead of a line break, so a
        multi-paragraph dictionary card collapsed into one line;
      * every HTML entity was unescaped, including ``&amp;`` -- which
        native deliberately leaves alone (only ``&nbsp;`` and
        ``&#x27;`` have rules), so ``AT&amp;T`` displayed as ``AT&T``
        where native shows the escape.

    One call site (the dictionary result summary), so the delegation is
    a straight substitution.
    """
    from qtranslate.common import strip_html
    return strip_html(h)


# ------------------------------------------------------- service registry
# --- provider adapters: owned by qtranslate/registry.py -----------------------
# The nine ``_t_*`` adapters lived here until 2026-10-15; they now live in
# ``registry`` (moved verbatim, same bodies, same comments) so Core and
# headless callers get dispatch without importing tkinter. The names below
# are re-exported for the call sites in this file that still reference them
# directly (``_router``'s google closure, ``do_translate``'s fallbacks);
# everything else goes through TRANSLATORS/DICTS.
from qtranslate.registry import (
    _t_google, _t_deepl, _t_yandex, _t_baidu, _t_naver, _t_youdao,
    _t_bing, _t_babylon, _t_promt,
)


# Single source of truth: qtranslate/registry.py USES_AUTO_DETECT
# (Phase 2 slice). Kept as a module attribute because live UI code and
# regress_source_language read ``A._USES_AUTO_DETECT``.
from qtranslate.registry import USES_AUTO_DETECT as _USES_AUTO_DETECT

# --- the reliability layer, wired 2026-10-10 ---------------------------------
# Built once over the TRANSLATORS table above: ProviderRouter's `callables`
# maps a service id to fn(text, src, tgt), which is exactly the signature the
# _t_* adapters already have. `order` is the ServicesOrder fallback chain.
#   docs/review/RELIABILITY_UNWIRED_2026-10-10.md
_ROUTER = None


def _router(sink=None):
    """Forwarder to ``registry.build_router`` (Phase 2 slice).

    The singleton construction, ServicesOrder order build, and per-call
    clone used to live here (~60 lines); they now live in
    ``qtranslate/registry.py`` so Core/headless callers get the same router
    without importing tkinter. This forwarder is kept because live UI code
    and tests call ``app._router(...)``; it will go away when the callers
    move. Returns None only if the reliability layer cannot be imported,
    preserving the old degrade-to-bare-provider contract.
    """
    try:
        from qtranslate import registry as _RG
        return _RG.build_router(sink)
    except Exception:
        return None


def _cfg_safe():
    """Options.json as a dict, or {} if it cannot be read.

    ProviderRouter reads only Advanced.RemoveLineBreaks from it; do_translate
    also applied that transform above, so this is belt-and-braces rather than
    the only guard.
    """
    try:
        from qtranslate import config as _C
        return _C.load() or {}
    except Exception:
        return {}


# Single source of truth: registry.call_with_sink / registry.apply_phonetics
# (Phase 2 slice). Aliases kept because do_translate calls them 4 times.
from qtranslate.registry import call_with_sink as _t_call
from qtranslate.registry import apply_phonetics as _apply_phonetics

# Single source of truth: owned by qtranslate/registry.py (Phase 2 slice).
# These are aliases, not copies — ``A.TRANSLATORS is R.TRANSLATORS`` holds.
# Kept as module attributes because ui_match and live UI code read
# ``A.TRANSLATORS`` / ``A.DICTS``.
from qtranslate.registry import TRANSLATORS, DICTS


# Single source of truth: registry.SERVICE_LINKS (Phase 2 slice).
# Alias kept because UI code reads ``_SERVICE_LINKS`` in help text paths.
from qtranslate.registry import SERVICE_LINKS as _SERVICE_LINKS


# Single source of truth: qtranslate/placement.py (Phase 2 slice, moved
# verbatim 2026-10-15 — stdlib + config only, no tkinter). Aliases kept
# because ui_match reads A.TEMPLATE_GEOMETRY / A._decode_placement and the
# UI calls the place/save helpers unqualified.
from qtranslate.placement import (
    decode_placement as _decode_placement,
    encode_placement as _encode_placement,
    TEMPLATE_GEOMETRY,
    place_main as _place_main,
    place_aux as _place_aux,
    save_placement as _save_placement,
)


def _pane_font(size_delta: int = 0):
    """Main-pane font from General.FontName/TextSize (native dialog
    font; empty FontName = MS Shell Dlg ~ Tahoma)."""
    try:
        from qtranslate import config as _C
        from qtranslate.fonts import resolve_font as _rf
        name, size = _rf(_C.load().get("General", {}),
                         size_delta=size_delta)
        return (name, size)
    except Exception:
        return ("Tahoma", 9 + size_delta)


_PACK = {}
_PACK_NAME = [None]


def _pack():
    """Load the UI language pack per General.LocaleFoderName
    (native FUN_0045B716 path).

    **English is a pack like any other.** It used to be skipped -- the
    comment claimed "English = built-in strings" -- and that was wrong in
    a way that showed on screen: the hardcoded fallbacks are the
    *design-time* strings from the DIALOG TEMPLATE, while the pack holds
    the *runtime* strings the native actually draws. The two differ:
    DLG175 control 1159 is "Always activate" in the template and
    "Activate when opened" in the English pack; 1145 is
    "Transparency (0-90):" in the template and "Transparency (0 - 90):"
    in the pack; 1137 is "Icons:" in the pack but the port's fallback
    said "Popup icons:". Skipping the pack therefore made EVERY label in
    the English UI the template's text, and the mismatch was invisible
    in the source because the fallbacks looked plausible.
    """
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
    """Control label by Windows Id + control id.

    A COMBOBOX's "label" is its ITEM LIST, and the pack stores it that
    way (`[1162, [[0, 'Enabled for these programs:'],
    [1, 'Disabled for these programs:']]]`). Stringifying that put a
    raw Python list in the Exceptions page's mode combo, so the raw
    value is returned for a list/tuple and only a plain string is
    stringified. No caller uses `_Cw` on a combo control as a caption.
    """
    try:
        pack = _pack()
        for w in pack.get("Windows", []):
            if isinstance(w, dict) and w.get("Id") == wid:
                for c in w.get("Controls", []):
                    if isinstance(c, (list, tuple)) and len(c) >= 2 \
                            and c[0] == cid:
                        if isinstance(c[1], (list, tuple)):
                            return c[1]
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


# Single source of truth: registry.service_link (Phase 2 slice).
from qtranslate.registry import service_link as _dict_service_link


# Single source of truth: registry.detect_language (Phase 2 slice).
# Alias kept because live UI code calls ``detect_language(...)`` unqualified.
from qtranslate.registry import detect_language


def speak(text, lang):
    """Online mp3 -> BASS; on failure fall back to offline SAPI.

    Thin forwarder to ``player.play_text`` (Phase 2 slice): the TTS
    orchestration (slow flag, online-first, SAPI fallback) lives there,
    not here. The old body duplicated ``play_text``'s fallback chain with
    its own nested try/except — two places to fix the same policy.
    Honors Advanced.EnableSlowerListening (clearer/slower TTS).
    """
    try:
        from qtranslate import config as _C
        slow = bool(_C.load().get("Advanced", {}).get(
            "EnableSlowerListening", False))
    except Exception:
        slow = False
    from qtranslate.player import play_text
    play_text(text, lang, slow=slow)


def do_translate(service, text, target, src="auto", auto_detect=False,
                 back_translate=False):
    """Forwarder to ``engine.translate`` (Slice 2, approved 2026-10-15).

    The orchestration (pick → detect → execute → fallbacks →
    back-translation → phonetics) lives in ``qtranslate/engine.py``;
    the signature is unchanged so every existing caller is untouched.
    """
    from qtranslate import engine as _ENG
    return _ENG.translate(service, text, target, src=src,
                          auto_detect=auto_detect,
                          back_translate=back_translate)


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
                _lt = _ga.get("LanguageTo", LANG_DEFAULTS["LanguageTo"])
                TARGET_EFF = _table[_lt] if 0 <= _lt < len(_table) \
                    else TARGET
            _lf = _ga.get("LanguageFrom", LANG_DEFAULTS["LanguageFrom"])
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
        # Restores General.WindowMainPlacement when saved, else the
        # DLG129 template size (TEMPLATE_GEOMETRY).
        _place_main(root)
        # Phase 7 (6/6): the main window's body lives in
        # ``qtranslate.windows.MainWindow``. It is handed the live App, so
        # every widget and every piece of state stays where it was.
        from qtranslate.windows import MainWindow
        self._main = MainWindow(self)
        self._init_opt_flags()
        self._main._build_main()

    # -- main window body: mirrors the real QTranslate main window --
    # nav row (back/forward + service link + overflow menu),
    # source pane (default text = version line + help.txt),
    # toolbar (paste, Auto-Detect, swap, target combo, Translate,
    # mic/headphone), result pane, service icon strip at the bottom.
    def _build_main(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main._build_main()
    def toggle_backtr(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.toggle_backtr()
    def dict_with_service(self, n):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.dict_with_service(n)
    def toggle_fullscreen(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.toggle_fullscreen()
    def reset_pair(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.reset_pair()
    def slot_service(self, n):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.slot_service(n)
    def slot_pair(self, n):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.slot_pair(n)
    def cycle_service(self, direction=1):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.cycle_service(direction)
    def toggle_pane(self, key, pane):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.toggle_pane(key, pane)
    def open_service_page_n(self, name):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.open_service_page_n(name)
    def _ui_icon(self, name):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main._ui_icon(name)
    def _load_svc_icon(self, name, button):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main._load_svc_icon(name, button)

    # -- option flags live in the nav kebab menu (show_nav_menu); the
    # native main window has NO menubar (tray + context menus only),
    # so there is deliberately no _build_menu here. --
    def _init_opt_flags(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main._init_opt_flags()
    def show_result_menu(self, event=None):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.show_result_menu(event)

    # -- main-window helpers (mirror native behavior) --
    def ordered_services(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.ordered_services()
    def default_source_text(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.default_source_text()
    def hist_back(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.hist_back()
    def hist_forward(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.hist_forward()
    def copy_to_source(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.copy_to_source()
    def open_service_page(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.open_service_page()
    def show_nav_menu(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.show_nav_menu()
    def on_new(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.on_new()
    def on_paste(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.on_paste()
    def on_mic(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.on_mic()

    # -- actions --
    def _mark_service(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main._mark_service()
    def switch_service(self, name):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.switch_service(name)
    def apply_theme(self, name):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.apply_theme(name)
    def current(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.current()

    def tag_links(self, widget, text, on_click):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.

        The WIDGET is forwarded: the main window tags its own result
        pane, the dictionary window its own aux pane, and the tagger
        works on whichever it is handed. This was a `@staticmethod` whose
        body used `self` -- so every call raised `NameError: name
        'self' is not defined` and `render()` could not fill the result
        pane at all.
        """
        return self._main.tag_links(widget, text, on_click)
    def render(self, text, back=""):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.render(text, back)
    def _apply_backtr_split(self, text):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main._apply_backtr_split(text)
    def _click_link_dict(self, widget, event=None):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main._click_link_dict(widget, event)
    def _click_link(self, event=None):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main._click_link(event)

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
                    # The three Contents keys map 1:1 onto DLG129's three
                    # RichEdits (1000/1017/1018 -- D10_SPOTCHECK_Contents_
                    # 2026-10-10.md §2), so each is read from its own pane
                    # and no separator is involved. The old code split the
                    # result pane on "--- back-translation ---", a separator
                    # that is not in the image (§4a) and that only existed
                    # because the aux pane was missing.
                    full.setdefault("Contents", {})["EditSource"] = \
                        self.src.get("1.0", "end").strip()[:5000]
                    full["Contents"]["EditTranslation"] = \
                        self.out.get("1.0", "end").strip()[:5000]
                    full["Contents"]["EditBackTranslation"] = \
                        (self.aux.get("1.0", "end").strip()[:5000]
                         if getattr(self, "aux", None) is not None else "")
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
        # General.EnableHistory: when off, native does not record new
        # history entries at all (was previously unconditional).
        try:
            from qtranslate import config as _CEH
            if not bool(_CEH.load().get("General", {}).get(
                    "EnableHistory", True)):
                return
        except Exception:
            pass
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
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.on_swap()
    def toggle_multi_service(self, name):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.toggle_multi_service(name)
    def on_go(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.on_go()
    def on_clear(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.on_clear()
    def on_listen(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.on_listen()
    def on_copy(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.on_copy()
    def on_layout(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.on_layout()
    def on_type(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.on_type()
    def accept_suggestion(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.accept_suggestion()
    def show_hotkeys(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.show_hotkeys()
    def show_about(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.show_about()
    def show_override_conflicts(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.show_override_conflicts()

    # -- Options dialog (DLG 154 + pages; Basics page mirrors screenshot) --
    def open_options(self):
        """The Options window (Phase 7 `OptionsDialog`).

        Body lives in ``qtranslate/windows.py``; this is the delegator.
        """
        from qtranslate.windows import OptionsDialog
        return OptionsDialog(self.root, self).open()


    # -- History window (DLG 164, 316x177: SysTreeView32 id83 +
    # Clear id1067 + Save as... id1160; NO Open button. Double-click
    # loads the item back into the main window.)
    def open_history_window(self):
        """The History window (Phase 7 `HistoryView`).

        Body lives in ``qtranslate/windows.py``: Phase 7 splits ``App``
        into window classes, and this is the delegator. The signature and
        the reachable behavior are unchanged -- the SAME ``self.history``
        list object is passed by reference, so delete/favourite/clear in
        the window are visible to the main window exactly as before.
        """
        from qtranslate.windows import HistoryView
        return HistoryView(self.root, self, self.history).open()

    def clear_history(self):
        self.history.clear()

    def on_export_history(self):
        try:
            from qtranslate import config as _C
            _app = _C.load().get("Application", {})
            _init = _app.get("SaveHistoryPath", "") or None
        except Exception:
            _init, _app = None, {}
        # Native (FUN_0042856e) feeds the Save dialog a per-plugin filter
        # built as "%s (%s)" = historyFileDescription(historyFileExtension)
        # -- description, then the extension in parens, one entry per
        # registered HistoryScript. The port had no filetypes at all, so
        # build the same shape from EXT_DESCRIPTIONS/EXPORT_ORDER.
        try:
            from qtranslate import history as _H0
            _fmask = [("%s (*.%s)" % (_H0.describe_extension(e), e),
                       "*.%s" % e) for e in _H0.EXPORT_ORDER]
        except Exception:
            _fmask = None
        _ask = {"title": "Export history", "defaultextension": ".html",
                "initialdir": _init, "initialfile": _init}
        if _fmask:
            _ask["filetypes"] = _fmask + [("All files", "*.*")]
        path = filedialog.asksavefilename(**_ask)
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
            # Native (FUN_00428483) picks the history writer from the
            # file's own extension via each HistoryScript plugin's
            # historyFileExtension -- it does NOT hardwire HTML. The port
            # used to always write HTML regardless of the chosen filename;
            # use the same extension dispatch through H.exporter_for.
            from qtranslate import history as H
            _fn = H.exporter_for(path)
            if _fn is None:
                self.render("[export error] no history writer for %s "
                            "(known: %s)" % (path, ", ".join(H.EXPORT_ORDER)))
                return
            data = _fn([(s, src, "auto", res, self.target)
                        for (s, src, res, *_) in self.history])
            with open(path, "w", encoding="utf-8") as f:
                f.write(data if isinstance(data, str) else str(data))
            self.render(f"exported {len(self.history)} items -> {path}")
        except Exception as e:
            self.render(f"[export error] {e}")

    # -- Dictionary window (DLG 184: multi-service cards) --
    def open_dict_window(self):
        """The Dictionary window (Phase 7 `DictionaryView`).

        Body lives in ``qtranslate/windows.py``; this is the delegator.
        The signature and reachable behavior are unchanged.
        """
        from qtranslate.windows import DictionaryView
        return DictionaryView(self.root, self).open()
    def on_ocr(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.on_ocr()
    def on_ocr_file(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.on_ocr_file()
    def _ocr_bytes(self, data: bytes):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main._ocr_bytes(data)
    def _ocr_region(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main._ocr_region()
    def open_keyboard(self):
        """The main window (Phase 7 `MainWindow`).

        Body lives in ``qtranslate/windows.py``; this is the
        delegator. The signature and the reachable behavior are
        unchanged.
        """
        return self._main.open_keyboard()


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
    svc, _, tgt, src = app.current()
    print(f"translating {len(text)} chars via {svc}...")
    res = do_translate(svc, text[:5000], tgt, src,
                       app.opt_detect.get(), app.opt_backtr.get())
    app.src.delete("1.0", "end")
    app.src.insert("1.0", text[:2000])
    app.render(res.text)
    app.push_hist(svc, text[:120], res.text[:200])
    # native hotkey flow shows a separate popup (TaskShowPopupWindow),
    # not just the main window
    try:
        app.root.after(0, lambda: show_popup(
            text[:300], res.text, svc, tgt,
            res.source_language_code or src))
    except Exception:
        pass


_MOUSE_MON = {"active": None}
_MOUSE_HOOK = {"on": False}


def _mouse_mode_select(app, x, y):
    """Native click-to-capture callback (FUN_004183bd): a selection click
    arrived at (x,y). Mode 2 reads the text under the cursor via OLEACC
    (FUN_00404901) and translates that directly; modes 0/1 synthesize Ctrl+C to
    copy the selection, then run the normal translate->popup path. Runs on a
    worker thread (the LL hook proc must return fast)."""
    try:
        from qtranslate import mouse_capture as _MC
        if not _MC.available():
            return
        from qtranslate import config as _CG
        _adv = _CG.load().get("Advanced", {})
        # Advanced.EnableGuiTranslation (checkbox 0x482) gates native mode-2
        # OLEACC text-capture (FUN_00404901, DAT_005494e4); mirror it here
        # as the gate for mouse-selection capture.
        if not bool(_adv.get("EnableGuiTranslation", True)):
            return
        # Advanced.EnableMouseModeOnCtrl: require Ctrl held at click time.
        if bool(_adv.get("EnableMouseModeOnCtrl", False)):
            try:
                import keyboard as _kb2
                if not _kb2.is_pressed("ctrl"):
                    return
            except Exception:
                pass
        from qtranslate import exclusions as _ex
        if _ex.foreground_excluded():
            return
    except Exception:
        pass

    def _work():
        try:
            # General.MouseMode 2 = native "popup + read aloud": FUN_004183bd
            # dispatches mode 2 through the OLEACC cursor-text path instead of
            # the clipboard copy. Prefer that text when it is non-empty.
            mode = 0
            try:
                from qtranslate import config as _C2
                mode = int(_C2.load().get("General", {}).get("MouseMode", 0))
            except Exception:
                pass
            if mode == 2:
                text = ""
                try:
                    text = (_MC.cursor_text(x, y) or "").strip()
                except Exception:
                    text = ""
                if text:
                    _translate_text(app, text)
                    return
            if _HAS_KEYS:
                from qtranslate import sendkeys as _SK
                _SK.send("ctrl+c")
                try:
                    import time as _t
                    _t.sleep(0.15)
                except Exception:
                    pass
            on_hotkey(app)
        except Exception:
            pass

    import threading as _th
    _th.Thread(target=_work, daemon=True).start()


def _translate_text(app, text):
    """Translate already-captured text (no clipboard involved).

    Shared by the mode-2 OLEACC path so cursor-captured text goes through the
    same selection/detect/back-translation/history/popup flow as on_hotkey,
    differing only in where the text came from."""
    try:
        svc, _, tgt, src = app.current()
    except Exception:
        return
    print(f"translating {len(text)} chars via {svc} (mouse mode 2)...")
    res = do_translate(svc, text[:5000], tgt, src,
                       app.opt_detect.get(), app.opt_backtr.get())
    try:
        app.src.delete("1.0", "end")
        app.src.insert("1.0", text[:2000])
        app.render(res.text)
        app.push_hist(svc, text[:120], res.text[:200])
    except Exception:
        pass
    # native mode 2 = popup + read aloud; the read-aloud half needs a provider
    # TTS sink we do not have, so only the popup is emitted here.
    try:
        app.root.after(0, lambda: show_popup(text[:300], res.text, svc, tgt,
                                             res.source_language_code or src))
    except Exception:
        pass


def _set_mouse_hook(app, on):
    """Enable/disable the Win32 low-level mouse hook for mouse modes."""
    try:
        from qtranslate import mouse_capture as _MC
        if on and not _MOUSE_HOOK["on"]:
            _MOUSE_HOOK["on"] = _MC.start(
                lambda x, y: _mouse_mode_select(app, x, y))
        elif not on and _MOUSE_HOOK["on"]:
            _MC.stop()
            _MOUSE_HOOK["on"] = False
    except Exception:
        _MOUSE_HOOK["on"] = False


def _toggle_mouse_mode(app):
    """Port of HotKeySwitchMouseMode.

    Cycles General.MouseMode 0=off -> 1=popup -> 2=popup+read (native
    FUN_004183bd semantics). Uses the Win32 low-level mouse hook
    (mouse_capture) to trigger on a real selection click when available,
    and the clipboard-sequence monitor as the copy-event fallback.
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
        _set_mouse_hook(app, mode != 0)
        if mode != 0:
            _MOUSE_MON["active"] = start_clipboard_monitor(
                app, popup=(mode == 1))
        _label = ["off", "popup on select", "popup+read on select"][mode]
        print(f"mouse mode: {_label}")
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
                    app.render(res.text)
                    app.push_hist(svc, text[:120], res.text[:200])
                    if popup:
                        show_popup(text[:300], res.text, svc, tgt,
                                   res.source_language_code or "auto")
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

    The conversion itself is in the core (``config.hotkey_combo``), so
    the tkinter front end and the PySide6 one cannot disagree about
    which key a binding is: a hotkey that fires in one app and not the
    other is a bug in one of them, and there is only one answer.
    """
    from qtranslate import config as _C
    return _C.hotkey_combo(code)


def _register_native_hotkeys(app) -> list:
    """Register exactly the HotKeys bound in Options.json.

    Action routing mirrors help.txt global hotkeys: PopupWindow =>
    popup translate, MainWindow => show main, ReplaceSelection =>
    replace with translation, ListenText/ListenTranslation => speak,
    Dictionary/DictionaryClipboard => dictionary window, History =>
    history, Keyboard => virtual keyboard, ConvertTextLayout => fix
    layout, CopyTranslation => copy result, SpeechInput =>
    offline SAPI mic (native Google full-duplex URL builder lives in
    speech_input.py; live path is dead:native-unavailable),
    TextRecognition => OCR, SwitchMouseMode => cycle MouseMode flag
    (cursor-side icon/hover needs a Win32 mouse hook — see B),
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
        from qtranslate import clipboard as _CB
        text = _CB.read_text().strip()
        if not text:
            return
        svc, _, tgt, _ = app.current()
        res = do_translate(svc, text[:5000], tgt, "auto",
                           app.opt_detect.get(), app.opt_backtr.get())
        # Advanced.CopyAction: 0 = copy to clipboard only, 1 = copy AND
        # retype in place (write-back). Default 0 if unset.
        try:
            from qtranslate import config as _CRA
            _copy_action = int(_CRA.load().get(
                "Advanced", {}).get("CopyAction", 0))
        except Exception:
            _copy_action = 0
        _CB.write_text(res.text)
        if _copy_action == 1:
            from qtranslate import sendkeys as _SK2
            _SK2.write_text(res.text[:2000])
        app.src.delete("1.0", "end")
        app.src.insert("1.0", text[:2000])
        app.render(res.text)

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


def _write_default_options_if_missing():
    """Write the default Options.json on a fresh install.

    Native's first run shows a setup wizard and writes the file
    (``FUN_00419DA6``). The port has no wizard, so it writes the same
    20-section shape straight away -- otherwise the file only ever
    appears as a side effect of the user changing a setting, and the
    settings the app has already read are nowhere to be found.

    An existing file is left exactly as it is: this is a first-run
    seed, not a migration.
    """
    try:
        from qtranslate import config as _C
        if os.path.exists(_C.DEFAULT_PATH):
            return
        _C.save(_C.default_config())
    except Exception:
        pass


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


def startup_entry(winreg_mod=None, executable=None):
    """Read/write the HKCU Run entry for start-with-Windows (row G).

    Returns ``(present, set_present)``: ``present`` is whether the
    ``QTranslate`` value exists under ``...\\CurrentVersion\\Run``;
    ``set_present(True/False)`` writes or deletes it. ``winreg_mod`` is
    injectable so the logic is testable headless; on non-Windows (or a
    missing winreg) it reports ``(False, no-op)`` honestly instead of
    pretending.
    """
    try:
        import winreg as _wr
    except Exception:
        _wr = None
    if winreg_mod is not None:
        _wr = winreg_mod
    if _wr is None:
        return False, (lambda on: None)

    def _read():
        try:
            _rk = _wr.OpenKey(
                _wr.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run")
            _wr.QueryValueEx(_rk, "QTranslate")
            return True
        except Exception:
            return False

    def _write(on):
        try:
            _rk2 = _wr.OpenKey(
                _wr.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, _wr.KEY_SET_VALUE)
            if on:
                _wr.SetValueEx(_rk2, "QTranslate", 0,
                               _wr.REG_SZ, executable or sys.executable)
            else:
                try:
                    _wr.DeleteValue(_rk2, "QTranslate")
                except Exception:
                    pass
        except Exception:
            pass

    return _read(), _write


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


def _frozen_selftest():
    """``--selftest``: prove the frozen import graph, open no window.

    Used to verify a *bundled* build (tools/build_bundle.py). The failure
    it exists to catch is a module PyInstaller's Analysis never followed --
    the app would start, hit a lazy ``import``, and die in front of the
    user. So this touches the same lazily-imported surface the real startup
    and its first actions use, rather than just ``import qtranslate``.

    Returns the process exit code; raises nothing. Prints one machine
    marker line (``SELFTEST ...``) so a tool can parse it, and a human
    readable summary otherwise.
    """
    import json as _json

    checks = []

    def _ck(name, fn):
        try:
            fn()
            checks.append((name, True, ""))
        except Exception as exc:            # noqa: BLE001 -- report, don't die
            checks.append((name, False, "%s: %s"
                           % (type(exc).__name__, exc)))

    # The import the UI lives behind. `screens`/`win32app` are standalone
    # entry points and are included in the bundle deliberately.
    _ck("qtranslate.app", lambda: __import__("qtranslate.app"))

    # The provider table must resolve by NAME (registry imports every
    # service module at module scope, so a missing one fails here).
    def _registry():
        from qtranslate import registry as _RG
        names = sorted(_RG.TRANSLATORS)
        if len(names) < 9:
            raise AssertionError("only %d providers: %r" % (len(names), names))
    _ck("registry.TRANSLATORS", _registry)

    # The lazily-imported modules the main paths reach. Each of these was
    # once invisible to a static import walk.
    for _mod, _why in (
            ("qtranslate.registry", "dispatch table"),
            ("qtranslate.engine", "orchestration"),
            ("qtranslate.theme", "themes"),
            ("qtranslate.history", "history window"),
            ("qtranslate.dict_render", "dictionary cards"),
            ("qtranslate.locale", "locale packs"),
            ("qtranslate.placement", "window placement"),
            ("qtranslate.sdk", "published SDK surface"),
            ("qtranslate.providers", "Provider contract"),
            ("qtranslate.ui_slots", "UI extension slots"),
            ("qtranslate.tray_state", "tray icon states"),
            ("qtranslate.screens", "reference screens"),
    ):
        _ck("import %s (%s)" % (_mod, _why),
            lambda m=_mod: __import__(m, fromlist=["*"]))

    # The runtime deps that must be INSIDE the bundle. Without them the
    # app starts but has no hotkeys and no icons -- a silent degradation
    # that looks like a feature, so it is checked. `keyboard` is Windows-only
    # (it aborts the process on macOS Cocoa), so the check is skipped there.
    for _dep in ("pyperclip", "PIL"):
        _ck("bundled dep %s" % _dep,
            lambda d=_dep: __import__(d, fromlist=["*"]))
    if sys.platform == "win32":
        _ck("bundled dep keyboard",
            lambda: __import__("keyboard", fromlist=["*"]))

    # A theme must load when its data file is present. NOTE the honest
    # caveat this check cannot hide: `theme.THEMES_DIR` points at the
    # INSTALLED native copy ("C:/Program Files (x86)/QTranslate/Themes"),
    # so a bundle on a machine without that install has no themes. That is
    # a real packaging gap (Phase 8 should ship Themes/ inside the bundle),
    # not something to assert around -- so the check reports which case it
    # saw rather than passing either way.
    def _theme():
        import os as _os
        from qtranslate import theme as _T
        have = _os.path.exists(_T.THEMES_DIR)
        t = _T.load_theme("Blue") if have else {}
        if not have:
            return "skipped: no Themes dir at %s" % _T.THEMES_DIR
        if not t:
            raise AssertionError("load_theme('Blue') returned nothing")
        return "ok"
    _ck("theme loads from its data file", _theme)

    bad = [(n, d) for n, ok, d in checks if not ok]
    print("SELFTEST %s %d/%d" % ("PASS" if not bad else "FAIL",
                                 len(checks) - len(bad), len(checks)))
    for name, ok, detail in checks:
        if not ok:
            print("  MISSING %s -- %s" % (name, detail))
    return 0 if not bad else 1


def main():
    # A headless startup probe, used by the packaging tool
    # (tools/build_bundle.py) to prove a FROZEN build's imports resolve
    # without opening a window. It is deliberately first, before any
    # config/crash/single-instance work, so it exercises the same import
    # graph the real startup uses and nothing else.
    if "--selftest" in sys.argv[1:]:
        return _frozen_selftest()
    _write_default_options_if_missing()
    _seed_service_options()
    # User extensions (D16): load from the per-user folder, fail-open, and
    # commit the winners into the live dispatch table so a provider/override
    # is actually used. A missing folder or a bad extension never blocks
    # startup (EXTENSION_SDK.md §7).
    try:
        from qtranslate.extensions import load_user_extensions
        _ext = load_user_extensions()
        if _ext:
            _loaded = sum(1 for r in _ext if r["status"] == "loaded")
            _disabled = sum(1 for r in _ext if r["status"] == "disabled")
            print(f"extensions: {_loaded} loaded, {_disabled} disabled")
    except Exception:
        pass
    _consume_crash_reports()
    _install_crash_hook()
    # FUN_0040345B's fail-fast: an out-of-memory condition terminates
    # without unwinding, so it must NOT fall through to the crash-report
    # excepthook installed just above (native's Q-row records exactly that
    # separation). qtranslate/crash.py holds the code mapping.
    def _oom_hook(typ, val, tb):
        if typ is MemoryError:
            from qtranslate import crash as _crash
            _crash.fail_fast(-0x7FF8FFF2)   # -> 0xC0000017, never returns
        return _prev_hook(typ, val, tb)

    try:
        _prev_hook = sys.excepthook
        sys.excepthook = _oom_hook
    except Exception:
        pass
    # Single-instance guard (FUN_00435175): an existing
    # QTranslate_ApplicationWindow is activated and this launch exits,
    # unless the command line carries allow-multiple-instances.
    try:
        from qtranslate import single_instance as _SI
        if _SI.ensure_single(sys.argv[1:]):
            print("another QTranslate instance is already running "
                  "(activated it)")
            return
    except SystemExit:
        raise
    except Exception:
        pass
    root = tk.Tk()
    app = App(root)
    global _MAIN_APP
    _MAIN_APP = app
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
        try:
            from ctypes import windll as _wd
            _dbl_s = _wd.user32.GetDoubleClickTime() / 1000.0
        except Exception:
            _dbl_s = 0.5
        _last_ctrl = [0.0]
        _last_c = [0.0]

        def _ctrl_tap():
            now = _time.time()
            if now - _last_ctrl[0] < _dbl_s:
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
            if keyboard.is_pressed("ctrl") and now - _last_c[0] < _dbl_s:
                _last_c[0] = 0.0
                from qtranslate import sendkeys as _SK3
                _SK3.send("ctrl+c")
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
    """The tray icon (Phase 7 `TrayController.build`).

    Body lives in ``qtranslate/windows.py``; this forwarder keeps the
    original ``(root, app)`` signature so the call site and any test that
    invokes it are unchanged.
    """
    from qtranslate.windows import TrayController
    return TrayController(root, app).build()



_MAIN_APP = None  # set by main(); lets the popup reuse the existing window


def _safe_destroy(widget):
    try:
        widget.destroy()
    except Exception:
        pass


def show_popup(source, result, service="google", target="vi",
              src_lang="auto"):
    """The borderless popup window (Phase 7 `PopupHost.open`).

    Body lives in ``qtranslate/windows.py``; this forwarder keeps the
    exact original signature so the three call sites in this module are
    unchanged.
    """
    from qtranslate.windows import PopupHost
    return PopupHost.open(source, result, service, target, src_lang)



if __name__ == "__main__":
    main()
