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
# Full defaults verified vs real Options.json (missing keys fall back
# via .get at use sites; these document the true native defaults).
DEFAULT_APPEARANCE = {
    "EnableWindowStyle": False, "PopupAutoSize": True,
    "ColorFrame": 8023133, "PopupPinWhenDragging": True,
    "PopupWindowFrameThickness": 2, "Transparency": 217,
    "PopupIcons": 30, "ColorText": 0, "PopupAutoFocus": False,
    "ThemeName": "", "PopupAutoPos": True, "PopupTimeout": 0,
    "ColorBack": 15790320,
}
DEFAULT_ADVANCED = {
    "EnableSlowerListening": True, "OcrApiKey": "",
    "LayoutIndicator": 0, "EnableGuiTranslation": False,
    "CopyAction": 0, "SwitchMouseModeOnTrayClick": True,
    "DefaultBrowserId": "", "EnableMouseModeOnCtrl": False,
    "RemoveLineBreaks": False, "PreferredDomain": "com",
    "GoogleDomain": "com",
}
DEFAULT_INTERNET = {"Timeout": 10000}
DEFAULT_PROXY = {"ProxyType": 0, "Scheme": 0, "Host": "", "Port": 0,
                 "Username": "", "Password": ""}


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
             0x2D: "Insert", 0x6F: "Divide", 0x90: "Num Lock"}


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
                   0x1B: "esc", 0x20: "space", 0x2E: "delete"}
        if vk in special:
            parts.append(special[vk])
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
            "Disabled": [], "Enabled": [], "DisabledMode": True,
        },
        "Contents": {
            "EditSource": "", "EditTranslation": "", "EditBackTranslation": "",
        },
        "Advanced": dict(DEFAULT_ADVANCED),
        "Appearance": dict(DEFAULT_APPEARANCE),
        "Internet": dict(DEFAULT_INTERNET),
        "HotKeys": {
            "EnableHotKeys": True,
            # The native's own file carries ALL SEVENTEEN hotkey keys
            # (EnableHotKeys plus these), and an unbound one is 0. The
            # two the RE recovered with their codes are the replace-
            # selection (Alt + W) and the popup (Ctrl + Q); the rest are
            # unbound in the native's saved file, so they stay 0 rather
            # than being invented here.
            "HotKeySpeechInput": 0,
            "HotKeyDictionaryClipboard": 0,
            "HotKeyTextRecognition": 0,
            "HotKeySwitchMouseMode": 0,
            "HotKeyTranslateClipboardInMainWindow": 0,
            "HotKeyTranslateClipboard": 0,
            "HotKeyTranslateClipboardInPopupWindow": 0,
            "HotKeyCopyTranslation": 0,
            "HotKeyReplaceSelection": 343,
            "HotKeyListenTranslation": 0,
            "HotKeyConvertTextLayout": 0,
            "HotKeyKeyboard": 0,
            "HotKeyListenText": 0,
            "HotKeyDictionary": 0,
            "HotKeyHistory": 0,
            "HotKeyPopupWindow": 593,
            "HotKeyMainWindow": 0,
        },
        "OfflineDictionaries": [],
        "Ocr": {
            "OcrApiKey": "", "OcrLanguage": 0,
        },
        "Update": {
            "CheckForUpdates": False,
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
    if path is None:
        path = DEFAULT_PATH
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
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


def save(cfg: dict, path: str | None = None) -> None:
    """Write the settings dict back to Options.json (D18 persistence).

    UTF-8 without BOM; a trailing newline keeps the file friendly to
    editors. The caller owns the dict — this never mutates it. As with
    `load`, the path is resolved at call time.
    """
    if path is None:
        path = DEFAULT_PATH
    ensure_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")


def services_order(cfg: dict | None = None) -> list:
    if cfg is None:
        try:
            cfg = load()
        except OSError:
            return list(DEFAULT_SERVICES_ORDER)
    return cfg.get("ServicesOrder", list(DEFAULT_SERVICES_ORDER))


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
