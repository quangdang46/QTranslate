"""Settings model — reversed from %AppData%/QTranslate/Options.json (20 sections).

Hotkey codes pack (modifiers << 8) | vk, matching FUN_00405A17's parse:
id = low byte, modifiers = (word >> 8) & 0xF, vk = low byte.
Observed: HotKeyReplaceSelection=343 (0x157: vk=0x57 'W', mod=1),
HotKeyPopupWindow=593 (0x251: vk=0x51 'Q', mod=2).
"""
import json
import os

from qtranslate.platforms import app_data_dir

# The native keeps its settings in ``%APPDATA%\QTranslate\Options.json``.
# Off Windows ``%APPDATA%`` is empty, so the old join produced a RELATIVE
# path -- and on macOS, where the filesystem is case-insensitive, that
# resolved to ``qtranslate/Options.json`` INSIDE the package directory.
# `platforms.app_data_dir()` gives the same shape everywhere:
# ``~/.config/QTranslate`` off Windows.
DEFAULT_PATH = os.path.join(app_data_dir(), "Options.json")
# The path the app actually ships with. ``load()`` only auto-migrates the
# Kotlin DataStore when ``DEFAULT_PATH`` still points here -- tests and
# tools reassign ``DEFAULT_PATH`` to throwaway files, and without this
# guard every fresh temp config would get the user's REAL migrated
# settings (locale, hotkeys, ...) injected into it.
_BUILTIN_DEFAULT_PATH = DEFAULT_PATH


def ensure_dir(path: str = None) -> None:
    """Create the directory the settings file lives in.

    The app has ~38 places that persist a setting by opening
    ``DEFAULT_PATH`` directly, and every one of them sits inside a
    ``try`` that swallows the error. On a fresh install the directory
    did not exist, so each write raised ``FileNotFoundError`` and the
    setting was silently lost -- the app could not remember anything the
    user changed.

    The directory is created here, once, for the default path; `save()`
    creates it again for a path it is handed.
    """
    d = os.path.dirname(path or DEFAULT_PATH)
    if not d:
        return
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass


ensure_dir()

# SERVICE_ID order from Options.json ServicesOrder (default provider priority)
DEFAULT_SERVICES_ORDER = [1, 5, 12, 13, 11, 26, 28, 30, 31]

SERVICE_NAMES = {
    1: "google", 5: "microsoft", 11: "yandex", 12: "promt",
    13: "babylon", 18: "imtranslator", 26: "youdao", 28: "baidu",
    30: "naver", 31: "deepl",
}

# Display names scraped live from Services/*/Service.js serviceHeader()
# (2nd arg) — what the native Services options page + tray show.
SERVICE_DISPLAY = {
    1: "Google", 5: "Microsoft", 11: "Yandex", 12: "Promt",
    13: "Babylon", 18: "ImTranslator", 26: "youdao", 28: "Baidu",
    30: "Papago", 31: "DeepL",
}

# Providers with no native SERVICE_ID (the .tmp plugin ports and any
# built-in that joins TRANSLATORS without an id) still need a display
# name; keyed by the registry name, not a numeric id.
EXTRA_SERVICE_DISPLAY = {
    "mymemory": "MyMemory (Free)",
    "libretranslate": "LibreTranslate",
    "reverso": "Reverso",
    "mozhi": "Mozhi",
    "ai-translate": "AI Translate",
    "yandex-web": "Yandex Web (Unofficial)",
}

# Default dictionary order, measured from the native capture 2136: the
# list shows Google Search, WordReference, Babylon Dictionary,
# Wikipedia first.  The port had NO default, so a fresh config produced
# an EMPTY dictionary list on the Services page.
DEFAULT_DICTIONARIES_ORDER = [10, 19, 20, 14, 17, 18, 22, 24, 25, 26, 29]

# Native's Options -> Languages page (DLG174) is a checklist of the
# languages the app can translate, in native's own order, laid out in
# four columns. The list was transcribed from the native capture 2137
# and lived in `screens.py`; it lives HERE because the live Options
# window needs it, and `screens.py` is a standalone reference module
# that no production module is supposed to depend on.
LANGUAGE_COLUMNS = [
    "Afrikaans Albanian Arabic Armenian Azerbaijani Basque Belarusian "
    "Bengali Bulgarian Catalan Chinese_(Simplified) "
    "Chinese_(Traditional) Croatian Czech Danish Dutch English Esperanto",
    "Estonian Filipino Finnish French Galician Georgian German Greek "
    "Haitian_Creole Hebrew Hindi Hmong Hungarian Icelandic Indonesian "
    "Irish Italian Japanese",
    "Kannada Kazakh Khmer Korean Lao Latin Latvian Lithuanian Macedonian "
    "Malay Maltese Marathi Mongolian Norwegian Persian Polish Portuguese "
    "Romanian",
    "Russian Serbian Sinhala Slovak Slovenian Spanish Swahili Swedish "
    "Tajik Tamil Tatar Telugu Thai Turkish Ukrainian Urdu Uzbek "
    "Vietnamese",
]

DICT_DISPLAY = {
    10: "Google Search", 14: "Wikipedia", 17: "Multitran",
    18: "ImTranslator", 19: "WordReference", 20: "Babylon Dictionary",
    22: "Reverso", 24: "Urban Dictionary", 25: "ABBYY Lingvo Live",
    26: "youdao", 29: "Oxford Learner Dictionary",
}

# LanguagePairs [[57,17],[17,57]] — index into the shared SupportedLanguages
# table (57=vi, 17=en in the Google ordering used as canonical).
LANG_INDEX = {57: "vi", 17: "en"}

# The four language slots' defaults, native's own: From = 1 (auto),
# To = 57 (vi), Dictionary = 17 (en), Keyboard = 17 (en). A single
# default of 17 for all four was the old bug (a 2026-10-15 fix, pinned):
# an unset From would show "en" on first run instead of auto.
LANG_DEFAULTS = {"LanguageFrom": 1, "LanguageTo": 57,
                 "LanguageDictionary": 17, "LanguageKeyboard": 17}

# Defaults scraped from a real Options.json (Contents/Appearance/Advanced).
DEFAULT_HOTKEY_DOC = (
    "Double Ctrl => Show main window; Ctrl+Q => popup translate; "
    "Ctrl+Shift+Q => dictionary; Ctrl+E => listen; "
    "Ctrl+Enter => translate; Ctrl+N => clear")

# HotKey* names: 17 real entries in Options.json HotKeys section
# (EnableHotKeys + these 17; verified, no duplicates). Value 0 = unbound.
HOTKEY_NAMES = [
    "HotKeySpeechInput", "HotKeyDictionaryClipboard",
    "HotKeyTextRecognition", "HotKeySwitchMouseMode",
    "HotKeyTranslateClipboardInMainWindow", "HotKeyTranslateClipboard",
    "HotKeyTranslateClipboardInPopupWindow", "HotKeyCopyTranslation",
    "HotKeyReplaceSelection", "HotKeyListenTranslation",
    "HotKeyConvertTextLayout", "HotKeyKeyboard", "HotKeyListenText",
    "HotKeyDictionary", "HotKeyHistory",
    "HotKeyPopupWindow", "HotKeyMainWindow",
]

# Hotkey presets -- ported from .tmp's core/settings/data/HotkeyPresets.kt
# and ui-swing HotkeyDraftOperations.replacePreset/clearForCustom.
# LEGACY is HotkeyBinding.DEFAULTS (the classic QTranslate chords);
# MODERN moves the GLOBAL actions to Ctrl+Shift+<key>; CUSTOM is every
# binding cleared -- upstream's "start from scratch" choice, and the
# state HotkeyPresets.identify reports for any hand-edited set.
#
# Only .tmp GLOBAL actions with a native HotKey* name appear here: the
# LOCAL-scope .tmp actions already live as fixed QShortcuts in
# qt/main_window.py, and binding them system-wide a second time would
# fire both. HotKeyListenTranslation (the port's second listen gesture,
# no .tmp action) stays unbound so the two never share a chord. Values
# use the Options.json packing (mods << 8) | vk -- mods 1=Alt 2=Ctrl
# 4=Shift 8=Win; bit15 is the "Double" prefix carried by HotKeyMainWindow.
HOTKEY_PRESETS = {
    "LEGACY": {
        "HotKeyMainWindow": 0x8000,       # Double Ctrl, no chord
        "HotKeyPopupWindow": 0x251,       # Ctrl+Q
        "HotKeyListenText": 0x245,        # Ctrl+E
        "HotKeyTextRecognition": 0x249,   # Ctrl+I
        "HotKeyReplaceSelection": 0x654,  # Ctrl+Shift+T
        "HotKeyDictionary": 0x244,        # Ctrl+D
    },
    "MODERN": {
        "HotKeyMainWindow": 0x8000,
        "HotKeyPopupWindow": 0x651,       # Ctrl+Shift+Q
        "HotKeyListenText": 0x64C,        # Ctrl+Shift+L
        "HotKeyTextRecognition": 0x64F,   # Ctrl+Shift+O
        "HotKeyReplaceSelection": 0x652,  # Ctrl+Shift+R
        "HotKeyDictionary": 0x644,        # Ctrl+Shift+D
    },
    # CUSTOM clears every binding, HotKeyMainWindow's Double prefix
    # included (upstream clearForCustom drops isDoubleCtrlEnabled too).
    "CUSTOM": {},
}
HOTKEY_PRESET_ORDER = ("LEGACY", "MODERN", "CUSTOM")


def hotkey_preset_values(kind: str) -> dict:
    """Every HotKey* name -> the preset's dword (0 = unbound)."""
    preset = HOTKEY_PRESETS.get(kind) or {}
    return {name: preset.get(name, 0) for name in HOTKEY_NAMES}


def hotkey_preset_kind(hotkeys: dict) -> str:
    """Which preset a HotKeys section's bindings match (.tmp
    HotkeyPresets.identify): LEGACY or MODERN on an exact match over all
    seventeen bindings, CUSTOM for anything else -- a hand-edited set
    included."""
    hk = hotkeys or {}
    for kind in ("LEGACY", "MODERN"):
        want = hotkey_preset_values(kind)
        if all(int(hk.get(name, 0) or 0) == want[name]
               for name in HOTKEY_NAMES):
            return kind
    return "CUSTOM"


def apply_hotkey_preset(hotkeys: dict, kind: str) -> dict:
    """A HotKeys section with the preset's bindings written over it
    (.tmp HotkeyDraftOperations.replacePreset). CUSTOM clears every
    binding. EnableHotKeys and any non-binding keys are preserved."""
    out = dict(hotkeys or {})
    out.update(hotkey_preset_values(kind))
    return out


# Full defaults verified vs real Options.json (missing keys fall back
# via .get at use sites; these document the true native defaults).
DEFAULT_APPEARANCE = {
    "EnableWindowStyle": False, "PopupAutoSize": True,
    "ColorFrame": 8023133, "PopupPinWhenDragging": True,
    "PopupWindowFrameThickness": 2, "Transparency": 217,
    "PopupIcons": 30, "ColorText": 0, "PopupAutoFocus": False,
    "ThemeName": "", "PopupAutoPos": True, "PopupTimeout": 0,
    "ColorBack": 15790320,
    # Menu-181 "ClosePopupsOnClickOutside" (.tmp PopupsPanel, default
    # on) and the .tmp AppearancePanel uiScale (75-300, step 25).
    "ClosePopupsOnClickOutside": True, "UiScale": 100,
}
DEFAULT_ADVANCED = {
    "EnableSlowerListening": True, "OcrApiKey": "",
    "LayoutIndicator": 0, "EnableGuiTranslation": False,
    "CopyAction": 0, "SwitchMouseModeOnTrayClick": True,
    "DefaultBrowserId": "", "EnableMouseModeOnCtrl": False,
    "RemoveLineBreaks": False, "PreferredDomain": "com",
    "GoogleDomain": "com",
}
# .tmp NetworkConfig defaults: retry on, 2 retries, 1s initial delay,
# per-host timeout overrides keyed by hostname (seconds).
DEFAULT_INTERNET = {"Timeout": 10000, "RetryEnabled": True,
                    "MaxRetries": 2, "RetryDelayMs": 1000,
                    "HostTimeouts": {}}
# Proxy.Password is deliberately ABSENT: upstream keeps the proxy
# password in a SecretStore, never in persisted config
# (.tmp NetworkConfigMappingTest "the proxy password comes from the
# secret store, not the config file"). The port's store is
# qtranslate/secrets.py; config.load() migrates a legacy plaintext
# value out of existing Options.json files.
DEFAULT_PROXY = {"ProxyType": 0, "Scheme": 0, "Host": "", "Port": 0,
                 "Username": ""}


def decode_hotkey(code: int) -> dict:
    """Split a HotKey* dword the way FUN_00405A17 does.

    Native (decompiled 2026-10-15): skips registration when ``word == 0``
    **or** ``(word & 0xFFF) == 0``; the enabled flag mirrors that branch.
    """
    if not code or not (code & 0xFFF):
        return {"id": 0, "modifiers": 0, "vk": 0, "enabled": False}
    vk = code & 0xFF
    mods = (code >> 8) & 0xF
    return {"id": code & 0xFFF, "modifiers": mods, "vk": vk, "enabled": True}


# GetKeyNameTextW special cases from FUN_00403D3C (verified decompile):
# nav block 0x21-0x28 + 0x2C/0x2D/0x2E, Divide 0x6F, NumLock 0x90
# (0x100-extended via scan code), Alt-flag pseudo-key 0x13.
_VK_NAMES = {0x08: "Backspace", 0x09: "Tab", 0x0D: "Enter", 0x1B: "Esc",
             0x20: "Space", 0x2E: "Delete", 0x21: "PgUp", 0x22: "PgDn",
             0x23: "End", 0x24: "Home", 0x25: "Left", 0x26: "Up",
             0x27: "Right", 0x28: "Down", 0x2C: "Print Screen",
             0x2D: "Insert", 0x6F: "Divide", 0x90: "Num Lock",
             0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".",
             0xBF: "/", 0xC0: "`", 0xDB: "[", 0xDC: "\\", 0xDD: "]",
             0xDE: "'"}


def hotkey_combo(code: int) -> str:
    """Options.json hotkey dword -> the `keyboard` library's combo string.

    FUN_00405A17 packs the binding as ``vk | (modifiers << 8)``:
    bit0 = Alt, bit1 = Ctrl, bit2 = Shift, bit3 = Win. The same packing
    as :func:`format_hotkey` reads, but the output is the machine form
    ("ctrl+shift+q") the `keyboard` library registers, not the display
    form ("Ctrl + Shift + Q").

    This lives in the core because it is not a UI concern: the tkinter
    front end registers the hotkeys with it and so does the PySide6 one,
    and a hotkey that the two disagree about is a hotkey that fires in
    one app and not the other.
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
        special = {0x08: "backspace", 0x09: "tab", 0x0D: "enter",
                   0x1B: "esc", 0x20: "space", 0x2E: "delete",
                   0x21: "pageup", 0x22: "pagedown", 0x23: "end",
                   0x24: "home", 0x25: "left", 0x26: "up",
                   0x27: "right", 0x28: "down", 0x2C: "printscreen",
                   0x2D: "insert",
                   0xBA: "oem_1", 0xBB: "oem_plus", 0xBC: "oem_comma",
                   0xBD: "oem_minus", 0xBE: "oem_period", 0xBF: "oem_2",
                   0xC0: "oem_3", 0xDB: "oem_4", 0xDC: "oem_5",
                   0xDD: "oem_6", 0xDE: "oem_7"}
        if vk in special:
            parts.append(special[vk])
        elif 0x70 <= vk <= 0x87:      # VK_F1..VK_F24
            parts.append("f%d" % (vk - 0x6F))
        elif 0x20 <= vk < 0x7F:
            parts.append(chr(vk).lower())
        else:
            return ""
    return "+".join(parts)


def format_hotkey(code: int) -> str:
    """Port of FUN_00403B48: hotkey word -> 'Double Ctrl + Q' display string.

    Verified decompile 2026-10-08: 'Double ' prefix if bit15 (short<0);
    modifier names in fixed order Ctrl(0x11)/Shift(0x10)/Alt(0x12)/Win
    via FUN_00403D3C string resources, joined with ' + ' (0x2B0020);
    vk name via GetKeyNameText-style lookup FUN_00403D3C(vk).
    Special-cased nav keys here (same visible output).
    """
    if not code or not (code & 0xFFF):
        return ""
    parts = []
    if code & 0x8000:
        parts.append("Double")
    mods = (code >> 8) & 0xF
    vk = code & 0xFF
    if mods & 2:
        parts.append("Ctrl")
    if mods & 4:
        parts.append("Shift")
    if mods & 1:
        parts.append("Alt")
    if mods & 8:
        parts.append("Win")
    if vk:
        name = _VK_NAMES.get(vk)
        if name is None:
            # Native falls back to GetKeyNameTextW (system key names);
            # printable-ASCII approximation is equivalent for hotkey display.
            try:
                name = chr(vk).upper() if 0x20 <= vk < 0x7F else f"VK_{vk:02X}"
            except ValueError:
                name = f"VK_{vk:02X}"
        parts.append(name)
    return " + ".join(parts)


def default_config() -> dict:
    """The settings a fresh install starts from.

    Native's own file has 20 sections (NATIVE_ARCH.md, "File layout (from
    a real install, 20 sections)"), and the first-run wizard
    (``FUN_00419DA6``) writes exactly that shape. The port has no wizard,
    so this is the file a fresh install gets instead -- the same sections
    with the same defaults, so every ``cfg.get("Section", {})`` in the app
    finds the section it expects.

    The values are the module's own ``DEFAULT_*`` constants, so there is
    one source of truth for each default.
    """
    return {
        "Application": {
            "OptionsPageIndex": 0,
        },
        "Exceptions": {
            # Native's real first-run file ships these 8 blocklist rows
            # (empty side = match anything); an explicitly emptied list
            # must stay empty, so seed the defaults rather than [].
            "Disabled": [
                ["", "SysListView32"], ["", "SysTreeView32"],
                ["", "ListBox"], ["", "ScrollBar"], ["", "ComboBox"],
                ["", "msctls_hotkey32"], ["", "ConsoleWindowClass"],
                ["mstsc.exe", ""],
            ],
            "Enabled": [], "DisabledMode": True,
        },
        "Contents": {
            "EditSource": "", "EditTranslation": "", "EditBackTranslation": "",
        },
        "Advanced": dict(DEFAULT_ADVANCED),
        "Appearance": dict(DEFAULT_APPEARANCE),
        # .tmp imageSearch* fields (qt/image_search.py reads them via
        # setdefault; declared here so a fresh Options.json is complete).
        "ImageSearch": {"AutoPosition": True, "Transparency": 5,
                        "LastKnownPosition": "", "LastKnownSize": ""},
        "Internet": dict(DEFAULT_INTERNET),
        "HotKeys": {
            "EnableHotKeys": True,
            # The native's own file carries ALL SEVENTEEN hotkey keys
            # (EnableHotKeys plus these), and an unbound one is 0. A
            # fresh install starts on the LEGACY preset -- .tmp's own
            # default (HotkeyBinding.DEFAULTS) -- so the Hotkeys page's
            # preset combo identifies it as Legacy, not Custom.
            **hotkey_preset_values("LEGACY"),
        },
        "OfflineDictionaries": [],
        "Ocr": {
            # Google-language INDEX, default 17 = English (the parity
            # note in docs/review/SERVICES_PAGE_PARITY: the earlier 0
            # pointed at the table's first entry, not English).
            "OcrApiKey": "", "OcrLanguage": 17,
        },
        "Update": {
            "CheckForUpdates": False,
            # Epoch seconds of the last update check (qt-v74 auto-check
            # throttle); 0 = never checked.
            "LastCheckAt": 0,
        },
        "DisabledServices": [],
        "Proxy": dict(DEFAULT_PROXY),
        "DictionariesOrder": list(DEFAULT_DICTIONARIES_ORDER),
        "DisabledLanguages": [],
        "DisabledDictionaries": [],
        "Dictionary": {
            "LanguageDictionary": 17,
            "DictionaryExactSearch": False,
            "DictionaryZoom": 100,
        },
        "LanguagePairs": [[57, 17], [17, 57]],
        "General": {
            "LocaleFoderName": "English",
            "EnableHistory": True,
            "ClearHistoryOnExit": True,
            # The native's saved file has this FALSE: the history list
            # does not expand its items by itself.
            "ExpandHistoryItems": False,
            "MainWindowShowOnLoad": True,
            "MainWindowStartupAction": 0,
            "MinimizeToTrayOnClose": False,
            "MinimizeToTrayOnMinimize": False,
            "ShowTopPane": True,
            "ShowMiddlePane": True,
            "ShowServicesPane": True,
            # .tmp toolbarVisibility.isHistoryBarVisible/
            # isLanguageBarVisible/isStatusBarVisible (the back/forward
            # pair, the language tool row and the bottom status strip;
            # ShowServicesPane above is .tmp's isServicesPanelVisible
            # under its native name) and Configuration.
            # serviceSelectorAppearance -- the provider strip's
            # icon/text mix, .tmp's own enum names.
            "ShowHistoryBar": True,
            "ShowLanguageBar": True,
            "ShowStatusBar": True,
            "ServiceSelectorAppearance": "ICONS_AND_TEXT",
            # Menu-181 toggles (native ids 0x8063/0x8077/0x8075) and
            # the startup-action group (85-88) plus its quit-time
            # persistence key; editor-font split (.tmp
            # editorFontConfig). See RE_COVERAGE_CHECKLIST legacy-menu
            # pass for semantics.
            "ClearInputOnDragDrop": True,
            "AutoCleanupTranslation": False,
            "SaveContentsOnExit": True,
            # .tmp Configuration.dictionaryAutoSource /
            # isDictionaryAutoPopupEnabled (AutoLookupCoordinator gates
            # the whole auto-lookup -- inline gloss AND the visible
            # dictionary panel refresh -- on the popup flag).
            "DictionaryAutoSource": "TRANSLATED",
            # .tmp StandardOptions.SUMMARY_LENGTH / REWRITE_STYLE --
            # the extra-output pane's AI modes read these verbatim.
            "SummaryLength": "MEDIUM",
            "RewriteStyle": "FORMAL",
            "DictionaryAutoPopup": True,
            "LastWindowVisible": False,
            "EditorFontName": "",
            "EditorTextSize": 0,
            # Menu-1 toggle consumed by main_window's instant-translate
            # debounce (.tmp observeInstantTranslation, 350 ms).
            "InstantTranslation": False,
            "FontName": "",
            "TextSize": 9,
        },
        "ServicesOrder": list(DEFAULT_SERVICES_ORDER),
        "AutoDetection": {
            # The three keys FUN_0045869F reads, at +0x188/+0x18C/+0x190
            # (RE_COVERAGE_CHECKLIST.md, row M21). The values are indices
            # into the shared SupportedLanguages table: 57 = vi, 17 = en.
            "LanguageFirst": 57,
            "LanguageSecond": 17,
            "LanguageSpeechRecognition": 57,
        },
    }


def load(path: str | None = None) -> dict:
    """Read the settings file.

    ``path`` defaults to ``DEFAULT_PATH`` **at call time**, not at import
    time: a default argument freezes its value when the function is
    defined, so a caller that points ``DEFAULT_PATH`` somewhere else --
    the tests do, and so does the pane toggle -- would still read the
    original file.

    **A missing file is not an error.** It is the state of a fresh
    install, and native reaches it on every first run. The port used to
    raise ``FileNotFoundError`` here, and that broke the app in a way
    nothing else showed: the app persists a setting from ~38 places, and
    each one reads the file first and writes it back, so on a machine
    with no ``Options.json`` yet EVERY write raised on the read and the
    setting was discarded -- the app could not remember anything, and
    the failure was invisible because each write sat inside a ``try``
    that swallowed it. So a missing file now yields the defaults, and a
    corrupt one is moved aside and also yields the defaults (the caller
    is then free to write a good file over it).
    """
    is_default = path is None
    if path is None:
        path = DEFAULT_PATH
        # One-time bidirectional migration with the Kotlin .tmp app's
        # DataStore settings (qtranslate/migrate.py). Runs only for the real
        # settings path -- explicit paths (tests, tools) never trigger it,
        # and neither does a reassigned ``DEFAULT_PATH`` (tests point it at
        # temp files; migrating there would import the user's real
        # settings into every throwaway config). Guarded to once per
        # process, and swallows all errors so a migration problem can
        # never stop the app from loading settings.
        if DEFAULT_PATH == _BUILTIN_DEFAULT_PATH:
            try:
                from qtranslate import migrate as _migrate
                _migrate.migrate_if_needed()
            except Exception:
                pass
    try:
        with open(path, encoding="utf-8-sig") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        return default_config()
    except (OSError, ValueError):
        # A corrupt file must not take the app down, and must not be
        # silently overwritten either: it is moved aside first, so the
        # user's old settings are still there to look at.
        try:
            os.replace(path, path + ".corrupt")
        except Exception:
            pass
        return default_config()
    # One-time secrets migration, default path only (explicit paths --
    # tests, tools -- never touch the real secrets store): a legacy
    # Options.json may still carry Proxy.Password in plaintext; move it
    # to secrets.json and rewrite the file without it. Runs only while
    # the key is present, so the steady state costs nothing.
    if is_default:
        try:
            from qtranslate import secrets as _secrets
            if _secrets.migrate_options(
                    cfg, path=_secrets.path_for(path)):
                save(cfg)
        except Exception:
            pass
    return cfg


def save(cfg: dict, path: str | None = None) -> None:
    """Write the settings dict back to Options.json (D18 persistence).

    UTF-8 without BOM; a trailing newline keeps the file friendly to
    editors. The caller owns the dict — this never mutates it. As with
    `load`, the path is resolved at call time.
    """
    if path is None:
        path = DEFAULT_PATH
    ensure_dir(path)
    # Write-then-rename: a crash mid-write must not leave a truncated
    # Options.json (which load() would quarantine as .corrupt, losing
    # every setting). os.replace is atomic on the same filesystem.
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def services_order(cfg: dict | None = None) -> list:
    if cfg is None:
        try:
            cfg = load()
        except OSError:
            return list(DEFAULT_SERVICES_ORDER)
    return cfg.get("ServicesOrder", list(DEFAULT_SERVICES_ORDER))


# ------------------------------------------------------- read helpers
# ``load`` returns the raw file: a partial/legacy Options.json lacks
# keys added later, so consumers that need a guaranteed value should go
# through these merged reads instead of ``cfg.get(section, {}).get(k)``.


def general_setting(key: str, default=None):
    """One ``General`` key, default-document merged under the file.

    The ``General`` section carries the pane/tray/history flags the
    Qt front end reads at scattered points (``ShowTopPane``,
    ``MinimizeToTrayOnClose``, ``ClearHistoryOnExit``, ...); a file
    written before a key existed must still see the default.
    """
    merged = dict(default_config().get("General", {}))
    try:
        merged.update((load() or {}).get("General", {}) or {})
    except Exception:
        pass
    return merged.get(key, default)


def auto_detection() -> dict:
    """The ``AutoDetection`` section with defaults merged.

    Native reads three keys here (``LanguageFirst`` +0x188,
    ``LanguageSecond`` +0x18C, ``LanguageSpeechRecognition`` +0x190 --
    RE_COVERAGE_CHECKLIST.md row M21). The values are indices into the
    shared ``SupportedLanguages`` table: 57 = vi, 17 = en, and index 0
    is the ``-1`` sentinel, NOT a language.
    """
    merged = dict(default_config().get("AutoDetection", {}))
    try:
        merged.update((load() or {}).get("AutoDetection", {}) or {})
    except Exception:
        pass
    return merged


def expand_history_items() -> bool:
    """``General.ExpandHistoryItems`` -- the history window grows each
    entry to show its detail rows when set (default False, the native
    file's own value). Consumer: ``qt/history_window.py`` ``_fill``."""
    return bool(general_setting("ExpandHistoryItems", False))


def service_selector_appearance(default: str = "ICONS_AND_TEXT") -> str:
    """``General.ServiceSelectorAppearance`` -- .tmp's
    ``ServiceSelectorAppearance`` (ICONS_ONLY / ICONS_AND_TEXT /
    TEXT_ONLY): the provider strip's icon/text mix. Absent or unknown
    values fall back to .tmp's own default, ICONS_AND_TEXT."""
    v = str(general_setting("ServiceSelectorAppearance", default) or "")
    return v if v in ("ICONS_ONLY", "ICONS_AND_TEXT", "TEXT_ONLY") \
        else default


def write_default_options_if_missing() -> None:
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
        if os.path.exists(DEFAULT_PATH):
            return
        save(default_config())
    except Exception:
        pass


def seed_service_options() -> None:
    """Seed the JS-runtime Options store (common.Options) from
    Options.json: Advanced.PreferredDomain + locale LanguageCode.

    Native UtilsDispatch runs addOption() per service at boot; without
    this the ports fall back to hardcoded defaults.
    """
    try:
        from qtranslate import common as _cm
        cfg = load()
        adv = cfg.get("Advanced", {})
        if adv.get("PreferredDomain"):
            _cm.add_option("PreferredDomain", adv["PreferredDomain"])
        loc = cfg.get("General", {}).get("LocaleFoderName", "")
        if loc:
            _cm.add_option("LanguageCode", loc[:2].lower())
    except Exception:
        pass


if __name__ == "__main__":
    for name in ("HotKeyReplaceSelection", "HotKeyPopupWindow",
                 "HotKeyTranslateClipboard"):
        code = {"HotKeyReplaceSelection": 343, "HotKeyPopupWindow": 593,
                "HotKeyTranslateClipboard": 0}[name]
        print(name, code, decode_hotkey(code))
    print("order:", services_order(None))
