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

# LanguagePairs [[57,17],[17,57]] — index into the shared SupportedLanguages
# table (57=vi, 17=en in the Google ordering used as canonical).
LANG_INDEX = {57: "vi", 17: "en"}


def decode_hotkey(code: int) -> dict:
    """Split a HotKey* dword the way FUN_00405A17 does."""
    if not code:
        return {"id": 0, "modifiers": 0, "vk": 0, "enabled": False}
    vk = code & 0xFF
    mods = (code >> 8) & 0xF
    return {"id": code & 0xFFF, "modifiers": mods, "vk": vk, "enabled": True}


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
