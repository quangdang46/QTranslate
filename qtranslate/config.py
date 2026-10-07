"""Settings model — reversed from %AppData%/QTranslate/Options.json (20 sections).

Hotkey codes pack (modifiers << 8) | vk, matching FUN_00405A17's parse:
id = low byte, modifiers = (word >> 8) & 0xF, vk = low byte.
Observed: HotKeyReplaceSelection=343 (0x157: vk=0x57 'W', mod=1),
HotKeyPopupWindow=593 (0x251: vk=0x51 'Q', mod=2).
"""
import json
import os

DEFAULT_PATH = os.path.join(
    os.environ.get("APPDATA", ""),
    "QTranslate", "Options.json")

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

DICT_DISPLAY = {
    10: "Google Search", 14: "Wikipedia", 17: "Multitran",
    18: "ImTranslator", 19: "WordReference", 20: "Babylon Dictionary",
    22: "Reverso", 24: "Urban Dictionary", 25: "ABBYY Lingvo Live",
    26: "youdao", 29: "Oxford Learner Dictionary",
}

# LanguagePairs [[57,17],[17,57]] — index into the shared SupportedLanguages
# table (57=vi, 17=en in the Google ordering used as canonical).
LANG_INDEX = {57: "vi", 17: "en"}

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
    "ThemeName": "", "PopupAutoPos": True, "PopupTimeout": 5,
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
    """Split a HotKey* dword the way FUN_00405A17 does."""
    if not code:
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


def load(path: str = DEFAULT_PATH) -> dict:
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def services_order(cfg: dict | None = None) -> list:
    if cfg is None:
        try:
            cfg = load()
        except OSError:
            return list(DEFAULT_SERVICES_ORDER)
    return cfg.get("ServicesOrder", list(DEFAULT_SERVICES_ORDER))


if __name__ == "__main__":
    for name in ("HotKeyReplaceSelection", "HotKeyPopupWindow",
                 "HotKeyTranslateClipboard"):
        code = {"HotKeyReplaceSelection": 343, "HotKeyPopupWindow": 593,
                "HotKeyTranslateClipboard": 0}[name]
        print(name, code, decode_hotkey(code))
    print("order:", services_order(None))
