"""One-time bidirectional settings migration: Options.json <-> Kotlin DataStore.

The Python port keeps its settings in ``Options.json`` (20 native sections);
the Kotlin app in ``.tmp/QTranslate`` persists a single ``configuration_json``
string inside an AndroidX DataStore ``preferences_pb`` file
(``core/.../SettingsRepository.kt`` stores the whole ``Configuration`` as JSON
under the ``configuration_json`` key, plus ``disabled_plugin_ids``).

This module bridges the two once per install:

* whichever file is NEWER wins (mtime comparison);
* the winning side's shared settings are mapped into the other side's schema;
* the pre-migration file is copied to ``<file>.bak`` before being overwritten;
* marker files ``.migrated_from_kotlin`` / ``.migrated_to_kotlin`` in the
  Options.json directory record that the cross-app decision was made, so the
  migration never loops between the two apps.

Only sections with a real semantic counterpart are mapped:
``General.*``, ``Appearance.*``, ``HotKeys.*`` and ``AutoDetection.*``.
``Exceptions.*`` (window class/process blocklist), ``Contents.*``, ``Proxy.*``,
``Internet.*``, ``ServicesOrder``/``DisabledServices`` (native integer service
ids vs Kotlin ``pluginId:instanceId:serviceKey`` strings) and every other
section have no Kotlin equivalent and are left untouched. Kotlin-only fields
(service presets, comparison policy, plugin trust, window geometry, ...) are
likewise preserved verbatim inside ``configuration_json``.

The DataStore file is protobuf, but the schema is small and stable
(``androidx.datastore.preferences.proto.PreferenceMap``), so it is read and
rewritten here with a minimal hand-rolled codec -- every entry we do not touch
is copied through byte-for-byte, so unknown keys and value types survive.

Nothing here ever logs setting VALUES (they can contain user text such as
window titles in Exceptions rows); reports carry key names and counts only.

Hook: ``config.load()`` calls :func:`migrate_if_needed` once per process,
only when loading the real ``DEFAULT_PATH`` (explicit paths -- tests, tools --
never trigger it). Failure is swallowed: migration must never keep the app
from starting.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import uuid

# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

#: DataStore file name inside ``<userData>/datastore/`` -- AppConstants.DATASTORE_FILE.
DATASTORE_FILE_NAME = "app_settings.preferences_pb"

#: Preferences key holding the serialized Kotlin ``Configuration``.
CONFIG_JSON_KEY = "configuration_json"

MARKER_FROM_KOTLIN = ".migrated_from_kotlin"
MARKER_TO_KOTLIN = ".migrated_to_kotlin"


def _kotlin_datastore_path() -> str | None:
    """Where the Kotlin app's DataStore file lives on this OS.

    Mirrors ``AppDataLayout.installedUserDataRoot``: Windows ``%APPDATA%``,
    macOS ``~/Library/Application Support``, elsewhere ``$XDG_CONFIG_HOME`` or
    ``~/.config`` -- always under a ``QTranslate`` directory, with the store
    at ``datastore/app_settings.preferences_pb``. A ``-DappData`` override or
    a portable Kotlin install cannot be discovered from here; those layouts
    are out of scope unless overridden (see below).

    ``QTRANSLATE_KOTLIN_DATASTORE`` overrides the whole path -- used by the
    test-suite and by anyone whose Kotlin install uses ``-DappData`` or a
    portable layout.
    """
    override = os.environ.get("QTRANSLATE_KOTLIN_DATASTORE")
    if override:
        return override
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    elif sys.platform == "darwin":
        base = os.path.join(home, "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    return os.path.join(base, "QTranslate", "datastore", DATASTORE_FILE_NAME)


def _markers_dir(options_path: str) -> str:
    return os.path.dirname(os.path.abspath(options_path))


# ---------------------------------------------------------------------------
# Minimal protobuf codec for androidx.datastore.preferences.proto.PreferenceMap
#
#   PreferenceMap { map<string, Value> preferences = 1; }
#   Value oneof: boolean=1 float=2 integer=3 long=4 string=5
#                 string_set=6 double=7 bytes=8
#   StringSet { repeated string strings = 1; }
#
# Only field 5 (string) is ever *written* by us; every other entry is copied
# verbatim, so integer/float/double/string_set/bytes values and unknown fields
# all round-trip untouched.
# ---------------------------------------------------------------------------

def _varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7
        if shift > 70:
            raise ValueError("protobuf varint too long")


def _write_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _tag(field: int, wire: int) -> bytes:
    return _write_varint((field << 3) | wire)


def _len_field(field: int, payload: bytes) -> bytes:
    return _tag(field, 2) + _write_varint(len(payload)) + payload


def _iter_fields(buf: bytes):
    """Yield (field_number, wire_type, value_start, value_end, int_value)."""
    pos = 0
    n = len(buf)
    while pos < n:
        key, pos = _varint(buf, pos)
        field, wire = key >> 3, key & 7
        if wire == 0:
            val, pos = _varint(buf, pos)
            yield field, wire, val, pos, val
        elif wire == 1:
            yield field, wire, pos, pos + 8, int.from_bytes(buf[pos:pos + 8], "little")
            pos += 8
        elif wire == 2:
            length, pos = _varint(buf, pos)
            yield field, wire, pos, pos + length, buf[pos:pos + length]
            pos += length
        elif wire == 5:
            yield field, wire, pos, pos + 4, int.from_bytes(buf[pos:pos + 4], "little")
            pos += 4
        else:
            raise ValueError("unsupported protobuf wire type %d" % wire)


def _read_preferences(data: bytes):
    """Parse a PreferenceMap into [(key, entry_bytes, value_msg_bytes|None)].

    ``entry_bytes`` is the raw map-entry message (kept verbatim for
    untouched keys); ``value_msg_bytes`` is the decoded Value submessage.
    """
    entries = []
    for field, wire, s, e, raw in _iter_fields(data):
        if field != 1 or wire != 2:
            continue  # unknown top-level field: dropped on rewrite (none exist)
        entry = raw
        key = None
        value_msg = None
        for f2, w2, s2, e2, v2 in _iter_fields(entry):
            if f2 == 1 and w2 == 2:
                key = v2.decode("utf-8")
            elif f2 == 2 and w2 == 2:
                value_msg = v2
        if key is not None:
            entries.append((key, entry, value_msg))
    return entries


def _string_value_bytes(text: str) -> bytes:
    """Encode a Value message holding a single string (field 5)."""
    return _len_field(5, text.encode("utf-8"))


def _read_string_value(value_msg: bytes) -> str | None:
    """Extract the string out of a Value message, or None if not a string."""
    for f, w, s, e, v in _iter_fields(value_msg):
        if f == 5 and w == 2:
            return v.decode("utf-8")
    return None


def _entry_for(key: str, value_msg: bytes) -> bytes:
    return _len_field(1, key.encode("utf-8")) + _len_field(2, value_msg)


def _read_datastore(path: str):
    """Return (entries, configuration_json|None) for a preferences_pb file."""
    with open(path, "rb") as f:
        data = f.read()
    if not data:
        return [], None
    entries = _read_preferences(data)
    config_json = None
    for key, _entry, value_msg in entries:
        if key == CONFIG_JSON_KEY and value_msg is not None:
            config_json = _read_string_value(value_msg)
    return entries, config_json


def _write_datastore(path: str, entries, config_json: str) -> None:
    """Rewrite the preferences_pb, replacing/adding configuration_json."""
    out = bytearray()
    written = False
    for key, entry, value_msg in entries:
        if key == CONFIG_JSON_KEY:
            # Replace every occurrence (map semantics: there should be one).
            out += _len_field(1, _entry_for(key, _string_value_bytes(config_json)))
            written = True
        else:
            out += _len_field(1, entry)  # untouched entry: verbatim bytes
    if not written:
        out += _len_field(1, _entry_for(CONFIG_JSON_KEY, _string_value_bytes(config_json)))
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(bytes(out))
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Key mapping -- Python Options.json sections <-> Kotlin Configuration JSON
# ---------------------------------------------------------------------------

# HotKeys.HotKey* name -> Kotlin HotkeyAction. Only actions with a real
# semantic counterpart are listed; the remaining Python hotkeys
# (SpeechInput, DictionaryClipboard, SwitchMouseMode, the two extra
# clipboard-translate variants, ConvertTextLayout, Keyboard) and the
# Kotlin-only actions (SHOW_IMAGES, FOCUS_*, CLEAR_INPUT, SWAP_LANGUAGES,
# OPEN_SETTINGS, TRANSLATE_DOCUMENT, CYCLE_TARGET_LANGUAGE) are left as-is.
_PY_TO_KT_ACTION = {
    "HotKeyPopupWindow": "SHOW_QUICK_TRANSLATE",
    "HotKeyMainWindow": "SHOW_MAIN_WINDOW",
    "HotKeyDictionary": "SHOW_DICTIONARY",
    "HotKeyTranslateClipboard": "TRANSLATE",
    "HotKeyCopyTranslation": "COPY_TRANSLATION",
    "HotKeyReplaceSelection": "REPLACE_WITH_TRANSLATION",
    "HotKeyListenTranslation": "LISTEN_TO_TEXT",
    "HotKeyListenText": "LISTEN_TO_TEXT",
    "HotKeyTextRecognition": "OPEN_OCR",
    "HotKeyHistory": "SHOW_HISTORY",
}

# Reverse map; LISTEN_TO_TEXT feeds both Python names (they are duplicate
# native entries for the same gesture).
_KT_TO_PY_ACTIONS = {}
for _py_name, _kt_action in _PY_TO_KT_ACTION.items():
    _KT_TO_PY_ACTIONS.setdefault(_kt_action, []).append(_py_name)

# Kotlin HotkeyScope per action, mirroring HotkeyBinding.DEFAULTS -- used only
# when a migrated binding has to be appended to a config that lacks it.
_KT_ACTION_SCOPE = {
    "SHOW_MAIN_WINDOW": "GLOBAL",
    "SHOW_QUICK_TRANSLATE": "GLOBAL",
    "LISTEN_TO_TEXT": "GLOBAL",
    "OPEN_OCR": "GLOBAL",
    "REPLACE_WITH_TRANSLATION": "GLOBAL",
    "CYCLE_TARGET_LANGUAGE": "LOCAL",
    "SHOW_DICTIONARY": "GLOBAL",
    "SHOW_IMAGES": "GLOBAL",
    "TRANSLATE": "LOCAL",
    "FOCUS_INPUT": "LOCAL",
    "FOCUS_OUTPUT": "LOCAL",
    "FOCUS_EXTRA_OUTPUT": "LOCAL",
    "COPY_TRANSLATION": "LOCAL",
    "CLEAR_INPUT": "LOCAL",
    "SWAP_LANGUAGES": "LOCAL",
    "OPEN_SETTINGS": "LOCAL",
    "SHOW_HISTORY": "LOCAL",
    "TRANSLATE_DOCUMENT": "LOCAL",
}

# Options.json HotKey* dword packing (config.decode_hotkey):
#   bit15 = "Double" prefix, bits 8-11 modifiers (1=Alt 2=Ctrl 4=Shift
#   8=Win), low byte = virtual-key code. Windows VK numbers equal Java
#   KeyEvent VK numbers for every key either side can produce here.
_PY_MOD_TO_JAVA = {1: 512, 2: 128, 4: 64, 8: 256}   # ALT/CTRL/SHIFT/META _DOWN_MASK
# (mask, python bit) for decoding java.awt.InputEvent modifiers. The *_DOWN_MASK
# values (SHIFT=64 CTRL=128 META=256 ALT=512) are what HotkeyBinding.DEFAULTS
# uses; the legacy *_MASK values (SHIFT=1 CTRL=2 META=4 ALT=8) are accepted too.
_JAVA_MOD_BITS = (
    (512, 1), (8, 1),    # ALT
    (256, 8), (4, 8),    # META / Win
    (128, 2), (2, 2),    # CTRL
    (64, 4), (1, 4),     # SHIFT
)

# Java KeyEvent keyCode <-> Win32 VK. Nav keys, F1-F12, modifiers-as-masks,
# numpad and ASCII letters/digits coincide; the entries below are the ones
# that do NOT (Enter 10 vs 0x0D, Delete 127 vs 0x2E, Insert 155 vs 0x2D,
# OEM punctuation uses ASCII in Java vs VK_OEM_* in Win32, F13+ live in
# Java's private 0xF000 block).
_JAVA_TO_WIN32_VK = {
    10: 0x0D,      # VK_ENTER -> VK_RETURN
    127: 0x2E,     # VK_DELETE -> VK_DELETE (fwd)
    155: 0x2D,     # VK_INSERT -> VK_INSERT
    154: 0x2C,     # VK_PRINTSCREEN -> VK_SNAPSHOT
    44: 0xBC,      # VK_COMMA -> VK_OEM_COMMA (44 is VK_SNAPSHOT on Win32)
    45: 0xBD,      # VK_MINUS -> VK_OEM_MINUS
    46: 0xBE,      # VK_PERIOD -> VK_OEM_PERIOD
    47: 0xBF,      # VK_SLASH -> VK_OEM_2
    59: 0xBA,      # VK_SEMICOLON -> VK_OEM_1
    61: 0xBB,      # VK_EQUALS -> VK_OEM_PLUS
    91: 0xDB,      # VK_OPEN_BRACKET -> VK_OEM_4
    92: 0xDC,      # VK_BACK_SLASH -> VK_OEM_5
    93: 0xDD,      # VK_CLOSE_BRACKET -> VK_OEM_6
    222: 0xDE,     # VK_QUOTE -> VK_OEM_7
}
# F13..F24: Java 0xF000..0xF00B, Win32 0x7C..0x87.
for _i in range(13):
    _JAVA_TO_WIN32_VK[0xF000 + _i] = 0x7C + _i
_WIN32_TO_JAVA_VK = {v: k for k, v in _JAVA_TO_WIN32_VK.items()}
# Win32 VK_DELETE(0x2E) and VK_INSERT(0x2D) collide with nothing in Java;
# but Win32 0x2C (snapshot) is already covered. 0x2E/0x2D/0x2C need explicit
# reverse entries because the forward map is keyed by Java values:
_WIN32_TO_JAVA_VK.update({0x2E: 127, 0x2D: 155, 0x2C: 154})


def _java_keycode_to_vk(key_code: int) -> int:
    """Kotlin binding keyCode (java.awt.KeyEvent) -> Options.json VK."""
    return _JAVA_TO_WIN32_VK.get(key_code, key_code)


def _vk_to_java_keycode(vk: int) -> int:
    """Options.json VK -> Kotlin binding keyCode (java.awt.KeyEvent)."""
    return _WIN32_TO_JAVA_VK.get(vk, vk)

_MOUSE_MODE_TO_SELECTION = {0: "SHOW_ICON", 1: "TRANSLATE", 2: "TRANSLATE_AND_READ"}
_SELECTION_TO_MOUSE_MODE = {v: k for k, v in _MOUSE_MODE_TO_SELECTION.items()}

# Language index <-> code. Options.json AutoDetection stores 1-based indices
# into the native SupportedLanguages table (index 1 = auto); the port's
# qtranslate.languages.LANGS is the same table 0-based, so index N -> LANGS[N-1].
def _lang_index_to_code(index):
    try:
        from qtranslate import languages
        i = int(index)
        if 1 <= i <= len(languages.LANGS):
            return languages.LANGS[i - 1]
    except Exception:
        pass
    return None


def _lang_code_to_index(code):
    try:
        from qtranslate import languages
        if code == "auto":
            return 1
        i = languages.LANGS.index(code)
        return i + 1
    except Exception:
        return None


def _lang_tag_to_display(tag):
    """Kotlin language tag ("en") -> Options.json LocaleFoderName ("English")."""
    if not tag:
        return ""
    try:
        from qtranslate import languages
        return languages.LANG_DISPLAY.get(tag, tag)
    except Exception:
        return tag


def _display_to_lang_tag(name):
    """Options.json LocaleFoderName ("English") -> Kotlin tag ("en")."""
    if not name:
        return ""
    try:
        from qtranslate import languages
        return languages.LANG_CODES.get(name, name)
    except Exception:
        return name


# ---------------------------------------------------------------------------
# Kotlin Configuration JSON -> Options.json sections
# ---------------------------------------------------------------------------

def _kt_bool(d, key):
    v = d.get(key)
    return bool(v) if isinstance(v, bool) else None


def _apply_kotlin_to_options(kcfg: dict, options: dict) -> list:
    """Merge mapped Kotlin fields into an Options.json dict. Returns key paths."""
    applied = []

    general = options.setdefault("General", {})
    appearance = options.setdefault("Appearance", {})
    hotkeys_sec = options.setdefault("HotKeys", {})
    autodetect = options.setdefault("AutoDetection", {})

    # ---- General ----
    lang = kcfg.get("interfaceLanguage")
    if isinstance(lang, str):
        general["LocaleFoderName"] = _lang_tag_to_display(lang)
        applied.append("General.LocaleFoderName")
    for kt_key, py_key in (
        ("isHistoryEnabled", "EnableHistory"),
        ("clearHistoryOnExit", "ClearHistoryOnExit"),
        ("isInstantTranslationEnabled", "InstantTranslation"),
    ):
        v = _kt_bool(kcfg, kt_key)
        if v is not None:
            general[py_key] = v
            applied.append("General." + py_key)

    font = kcfg.get("uiFontConfig")
    if isinstance(font, dict):
        if isinstance(font.get("name"), str):
            general["FontName"] = font["name"]
            applied.append("General.FontName")
        if isinstance(font.get("size"), int):
            general["TextSize"] = font["size"]
            applied.append("General.TextSize")

    behavior = kcfg.get("closeButtonBehavior")
    if isinstance(behavior, str):
        general["MinimizeToTrayOnClose"] = behavior == "MINIMIZE_TO_TRAY"
        applied.append("General.MinimizeToTrayOnClose")
    min_behavior = kcfg.get("minimizeButtonBehavior")
    if isinstance(min_behavior, str):
        general["MinimizeToTrayOnMinimize"] = min_behavior == "HIDE_TO_TRAY"
        applied.append("General.MinimizeToTrayOnMinimize")

    # Mouse capture: Kotlin selectionBehavior <-> native General.MouseMode(+On).
    sel = kcfg.get("selectionBehavior")
    if isinstance(sel, str):
        general["MouseModeOn"] = sel != "OFF"
        mode = _SELECTION_TO_MOUSE_MODE.get(sel)
        if mode is not None:
            general["MouseMode"] = mode
        applied.append("General.MouseModeOn")
        if mode is not None:
            applied.append("General.MouseMode")

    toolbar = kcfg.get("toolbarVisibility")
    if isinstance(toolbar, dict) and isinstance(toolbar.get("isServicesPanelVisible"), bool):
        general["ShowServicesPane"] = toolbar["isServicesPanelVisible"]
        applied.append("General.ShowServicesPane")

    # ---- Appearance ----
    for kt_key, py_key in (
        ("isPopupAutoSizeEnabled", "PopupAutoSize"),
        ("isPopupAutoPositionEnabled", "PopupAutoPos"),
    ):
        v = _kt_bool(kcfg, kt_key)
        if v is not None:
            appearance[py_key] = v
            applied.append("Appearance." + py_key)

    pct = kcfg.get("popupTransparencyPercentage")
    if isinstance(pct, (int, float)):
        # Kotlin stores percent-transparent (5 -> 95% opaque);
        # native stores a 0-255 alpha (217 -> setWindowOpacity(217/255)).
        alpha = int(round(255.0 * (100.0 - float(pct)) / 100.0))
        appearance["Transparency"] = max(0, min(255, alpha))
        applied.append("Appearance.Transparency")

    timeout = kcfg.get("popupIdleTimeoutSeconds")
    if isinstance(timeout, int):
        appearance["PopupTimeout"] = timeout
        applied.append("Appearance.PopupTimeout")

    # ---- HotKeys ----
    v = _kt_bool(kcfg, "isGlobalHotkeysEnabled")
    if v is not None:
        hotkeys_sec["EnableHotKeys"] = v
        applied.append("HotKeys.EnableHotKeys")

    for binding in kcfg.get("hotkeys") or []:
        if not isinstance(binding, dict):
            continue
        action = binding.get("action")
        py_names = _KT_TO_PY_ACTIONS.get(action)
        if not py_names:
            continue
        key_code = binding.get("keyCode")
        mods = binding.get("modifiers")
        if not isinstance(mods, int):
            mods = 0
        enabled = binding.get("isEnabled", True)
        if not isinstance(key_code, int) or key_code == 0 or not enabled:
            dword = 0
        else:
            py_mods = 0
            for mask, bit in _JAVA_MOD_BITS:
                if mods & mask:
                    py_mods |= bit
            # Java keyCodes differ from Win32 VKs (Enter 10 vs 0x0D etc.)
            vk = _java_keycode_to_vk(key_code)
            dword = (vk & 0xFF) | (py_mods << 8)
        # SHOW_MAIN_WINDOW's double-Ctrl gesture is a separate mechanism in
        # both apps (native's "Double Ctrl" is not the HotKeyMainWindow dword),
        # so it is preserved as the dword's "Double" prefix bit. An omitted
        # flag means the Kotlin default (enabled), not disabled.
        if action == "SHOW_MAIN_WINDOW" and binding.get(
                "isDoubleCtrlEnabled", True):
            dword |= 0x8000
        for py_name in py_names:
            hotkeys_sec[py_name] = dword
        applied.append("HotKeys." + "/".join(py_names))

    # ---- AutoDetection ----
    src = kcfg.get("preferredSourceLanguage")
    if isinstance(src, str) and src:
        idx = _lang_code_to_index(src)
        if idx is not None:
            autodetect["LanguageFirst"] = idx
            applied.append("AutoDetection.LanguageFirst")
    tgt = kcfg.get("preferredTargetLanguage")
    if isinstance(tgt, str) and tgt:
        idx = _lang_code_to_index(tgt)
        if idx is not None:
            autodetect["LanguageSecond"] = idx
            applied.append("AutoDetection.LanguageSecond")

    return applied


# ---------------------------------------------------------------------------
# Options.json sections -> Kotlin Configuration JSON
# ---------------------------------------------------------------------------

def _java_mods(py_mods: int) -> int:
    out = 0
    for bit, mask in _PY_MOD_TO_JAVA.items():
        if py_mods & bit:
            out |= mask
    return out


def _hotkey_dword_to_binding(dword: int):
    """Options.json HotKey* dword -> (keyCode, modifiers, isDoubleCtrl)."""
    if not dword or not (dword & 0xFFF):
        return 0, 0, bool(dword & 0x8000)
    return dword & 0xFF, _java_mods((dword >> 8) & 0xF), bool(dword & 0x8000)


def _kt_default_hotkeys() -> list:
    """HotkeyBinding.DEFAULTS as JSON-ready dicts (fresh-config fallback)."""
    # (action, keyCode, modifiers, scope, isDoubleCtrlEnabled)
    table = [
        ("SHOW_MAIN_WINDOW", 0, 0, "GLOBAL", True),
        ("SHOW_QUICK_TRANSLATE", 81, 128, "GLOBAL", True),
        ("LISTEN_TO_TEXT", 69, 128, "GLOBAL", True),
        ("OPEN_OCR", 73, 128, "GLOBAL", True),
        ("REPLACE_WITH_TRANSLATION", 84, 192, "GLOBAL", True),
        ("CYCLE_TARGET_LANGUAGE", 76, 128, "LOCAL", True),
        ("SHOW_DICTIONARY", 68, 128, "GLOBAL", True),
        ("SHOW_IMAGES", 81, 192, "GLOBAL", True),
        ("TRANSLATE", 10, 128, "LOCAL", True),
        ("FOCUS_INPUT", 49, 512, "LOCAL", True),
        ("FOCUS_OUTPUT", 50, 512, "LOCAL", True),
        ("FOCUS_EXTRA_OUTPUT", 51, 512, "LOCAL", True),
        ("COPY_TRANSLATION", 67, 192, "LOCAL", True),
        ("CLEAR_INPUT", 88, 192, "LOCAL", True),
        ("SWAP_LANGUAGES", 83, 192, "LOCAL", True),
        ("OPEN_SETTINGS", 44, 128, "LOCAL", True),
        ("SHOW_HISTORY", 72, 192, "LOCAL", True),
        ("TRANSLATE_DOCUMENT", 68, 192, "LOCAL", True),
    ]
    return [
        {
            "action": action,
            "keyCode": key_code,
            "modifiers": modifiers,
            "isEnabled": True,
            "scope": scope,
            "isDoubleCtrlEnabled": dbl,
        }
        for action, key_code, modifiers, scope, dbl in table
    ]


def _fresh_kotlin_config() -> dict:
    """A minimal valid Configuration for a Kotlin install that never ran.

    Mirrors ``ServicePreset.createDefault()`` + ``Configuration.DEFAULT`` so
    the Kotlin app decodes a complete configuration rather than empty
    ``servicePresets`` (whose deserialization default is ``emptyList()``,
    NOT the companion's default preset). ``configVersion`` is stamped with
    the schema version this build writes (ConfigMigrator.CURRENT_VERSION = 7)
    so no migration runs on it.
    """
    preset_id = str(uuid.uuid4())
    return {
        "configVersion": 7,
        "servicePresets": [{
            "id": preset_id,
            "name": "__default__",
            "selectedServices": {
                "TRANSLATOR": "google-services:default:google-translator",
                "TTS": "google-services:default:google-tts",
                "SPELL_CHECKER": "system-services:default:system-spell-checker",
                "OCR": "system-services:default:system-ocr",
                "DICTIONARY": "wikimedia-reference:default:wikimedia-wiktionary",
            },
            "comparisonTranslatorIds": [],
        }],
        "activeServicePresetId": preset_id,
        "hotkeys": _kt_default_hotkeys(),
    }


def _apply_options_to_kotlin(options: dict, kcfg: dict) -> list:
    """Merge mapped Options.json fields into a Kotlin Configuration dict."""
    applied = []

    general = options.get("General") or {}
    appearance = options.get("Appearance") or {}
    hotkeys_sec = options.get("HotKeys") or {}
    autodetect = options.get("AutoDetection") or {}

    # ---- General ----
    if "LocaleFoderName" in general:
        kcfg["interfaceLanguage"] = _display_to_lang_tag(general.get("LocaleFoderName") or "")
        applied.append("General.LocaleFoderName")
    for py_key, kt_key in (
        ("EnableHistory", "isHistoryEnabled"),
        ("ClearHistoryOnExit", "clearHistoryOnExit"),
        ("InstantTranslation", "isInstantTranslationEnabled"),
    ):
        if py_key in general and isinstance(general.get(py_key), bool):
            kcfg[kt_key] = general[py_key]
            applied.append("General." + py_key)

    font_name = general.get("FontName")
    font_size = general.get("TextSize")
    if isinstance(font_name, str) or isinstance(font_size, int):
        font = dict(kcfg.get("uiFontConfig") or {})
        if isinstance(font_name, str):
            font["name"] = font_name
        if isinstance(font_size, int) and font_size > 0:
            font["size"] = font_size
        kcfg["uiFontConfig"] = font
        applied.append("General.FontName/TextSize")

    if "MinimizeToTrayOnClose" in general and isinstance(general.get("MinimizeToTrayOnClose"), bool):
        kcfg["closeButtonBehavior"] = (
            "MINIMIZE_TO_TRAY" if general["MinimizeToTrayOnClose"] else "ASK"
        )
        applied.append("General.MinimizeToTrayOnClose")
    if "MinimizeToTrayOnMinimize" in general and isinstance(general.get("MinimizeToTrayOnMinimize"), bool):
        kcfg["minimizeButtonBehavior"] = (
            "HIDE_TO_TRAY" if general["MinimizeToTrayOnMinimize"] else "MINIMIZE_TO_TASKBAR"
        )
        applied.append("General.MinimizeToTrayOnMinimize")

    # Mouse capture. MouseModeOn is a port-added key: absent means the file
    # predates it and the capture state is unknown, so leave Kotlin's
    # selectionBehavior alone rather than guessing OFF.
    if "MouseModeOn" in general:
        if general.get("MouseModeOn"):
            mode = general.get("MouseMode", 0)
            try:
                mode = int(mode)
            except Exception:
                mode = 0
            kcfg["selectionBehavior"] = _MOUSE_MODE_TO_SELECTION.get(mode, "SHOW_ICON")
        else:
            kcfg["selectionBehavior"] = "OFF"
        applied.append("General.MouseModeOn/MouseMode")

    if "ShowServicesPane" in general and isinstance(general.get("ShowServicesPane"), bool):
        toolbar = dict(kcfg.get("toolbarVisibility") or {})
        toolbar["isServicesPanelVisible"] = general["ShowServicesPane"]
        kcfg["toolbarVisibility"] = toolbar
        applied.append("General.ShowServicesPane")

    # ---- Appearance ----
    for py_key, kt_key in (
        ("PopupAutoSize", "isPopupAutoSizeEnabled"),
        ("PopupAutoPos", "isPopupAutoPositionEnabled"),
    ):
        if py_key in appearance and isinstance(appearance.get(py_key), bool):
            kcfg[kt_key] = appearance[py_key]
            applied.append("Appearance." + py_key)

    if "Transparency" in appearance:
        try:
            alpha = int(appearance["Transparency"])
        except Exception:
            alpha = None
        if alpha is not None:
            # Native alpha 0-255 -> Kotlin percent-transparent 0-100.
            pct = int(round(100.0 * (255 - alpha) / 255.0))
            kcfg["popupTransparencyPercentage"] = max(0, min(100, pct))
            applied.append("Appearance.Transparency")

    # PopupTimeout: native 0 means "never auto-hide"; Kotlin's idle timeout
    # has no disabled state, so only positive values are carried over.
    try:
        pop_timeout = int(appearance.get("PopupTimeout", 0) or 0)
    except Exception:
        pop_timeout = 0
    if pop_timeout > 0:
        kcfg["popupIdleTimeoutSeconds"] = pop_timeout
        applied.append("Appearance.PopupTimeout")

    # ---- HotKeys ----
    if "EnableHotKeys" in hotkeys_sec and isinstance(hotkeys_sec.get("EnableHotKeys"), bool):
        kcfg["isGlobalHotkeysEnabled"] = hotkeys_sec["EnableHotKeys"]
        applied.append("HotKeys.EnableHotKeys")

    # action -> (keyCode, modifiers, doubleCtrl). When two Python names map
    # to one action (LISTEN_TO_TEXT), a bound entry beats an unbound one.
    wanted = {}
    for py_name, action in _PY_TO_KT_ACTION.items():
        raw = hotkeys_sec.get(py_name)
        if not isinstance(raw, int):
            continue
        key_code, mods, dbl = _hotkey_dword_to_binding(raw)
        if action not in wanted or (wanted[action][0] == 0 and key_code != 0):
            wanted[action] = (key_code, mods, dbl)

    if wanted:
        bindings = list(kcfg.get("hotkeys") or [])
        seen = set()
        for binding in bindings:
            if not isinstance(binding, dict):
                continue
            action = binding.get("action")
            if action not in wanted:
                continue
            key_code, mods, dbl = wanted[action]
            key_code = _vk_to_java_keycode(key_code)
            if action == "SHOW_MAIN_WINDOW" and key_code == 0:
                # No explicit key binding: the dword cannot express "off"
                # for this action (native's double-Ctrl is separate), so only
                # the Double flag is carried and the rest is left alone.
                binding["isDoubleCtrlEnabled"] = dbl or binding.get("isDoubleCtrlEnabled", True)
            else:
                binding["keyCode"] = key_code
                binding["modifiers"] = mods
                binding["isEnabled"] = key_code != 0
                if action == "SHOW_MAIN_WINDOW":
                    binding["isDoubleCtrlEnabled"] = dbl
            seen.add(action)
        for action, (key_code, mods, dbl) in wanted.items():
            if action in seen:
                continue
            if action == "SHOW_MAIN_WINDOW" and key_code == 0:
                continue  # nothing explicit to add; Kotlin default stands
            bindings.append({
                "action": action,
                "keyCode": key_code,
                "modifiers": mods,
                "isEnabled": key_code != 0,
                "scope": _KT_ACTION_SCOPE.get(action, "GLOBAL"),
                "isDoubleCtrlEnabled": dbl if action == "SHOW_MAIN_WINDOW" else True,
            })
            seen.add(action)
        kcfg["hotkeys"] = bindings
        applied.append("HotKeys.*")

    # A Kotlin config that never wrote "hotkeys" decodes to an empty list
    # (the companion default is NOT applied on absent fields), leaving the
    # app with no bindings at all. Seed the documented defaults instead.
    if "hotkeys" not in kcfg:
        kcfg["hotkeys"] = _kt_default_hotkeys()
        applied.append("HotKeys.defaults")

    # ---- AutoDetection ----
    for py_key, kt_key in (
        ("LanguageFirst", "preferredSourceLanguage"),
        ("LanguageSecond", "preferredTargetLanguage"),
    ):
        if py_key in autodetect:
            code = _lang_index_to_code(autodetect.get(py_key))
            if code:
                kcfg[kt_key] = code
                applied.append("AutoDetection." + py_key)

    return applied


# ---------------------------------------------------------------------------
# Migration driver
# ---------------------------------------------------------------------------

_DONE = False


def _backup(path: str) -> str | None:
    """Copy ``path`` to ``path + '.bak'`` before it is overwritten."""
    try:
        if not os.path.isfile(path):
            return None
        bak = path + ".bak"
        shutil.copy2(path, bak)
        return bak
    except Exception:
        return None


def _touch(path: str) -> None:
    try:
        with open(path, "w"):
            pass
    except Exception:
        pass


def migrate_if_needed(options_path: str | None = None) -> dict:
    """Run the one-time Options.json <-> DataStore migration if unresolved.

    Returns a report dict (``{"from_kotlin": bool, "to_kotlin": bool,
    "applied": [...], "skipped": reason|None}``). Key names only -- never
    values. Safe to call repeatedly: a process-level guard plus the marker
    files make it run at most once per install.
    """
    global _DONE
    if _DONE:
        return {"skipped": "already-run-this-process"}
    _DONE = True

    report = {"from_kotlin": False, "to_kotlin": False, "applied": [], "skipped": None}
    try:
        return _migrate(options_path, report)
    except Exception as exc:  # never break config.load()
        report["skipped"] = "error: %s" % type(exc).__name__
        return report


def _migrate(options_path, report):
    from qtranslate import config as _cfg  # lazy: config imports this module

    opts_path = options_path or _cfg.DEFAULT_PATH
    cfg_dir = _markers_dir(opts_path)
    from_marker = os.path.join(cfg_dir, MARKER_FROM_KOTLIN)
    to_marker = os.path.join(cfg_dir, MARKER_TO_KOTLIN)

    if os.path.exists(from_marker) and os.path.exists(to_marker):
        report["skipped"] = "markers-present"
        return report

    pb_path = _kotlin_datastore_path()
    opts_exists = os.path.isfile(opts_path)
    pb_exists = bool(pb_path) and os.path.isfile(pb_path)

    if not opts_exists and not pb_exists:
        report["skipped"] = "no-settings-on-either-side"
        return report

    entries = None
    kcfg = None
    if pb_exists:
        try:
            entries, kconfig_json = _read_datastore(pb_path)
        except Exception:
            # An unreadable DataStore must not be overwritten blindly; the
            # Kotlin app itself recovers such files to defaults + backup.
            report["skipped"] = "datastore-unreadable"
            return report
        if kconfig_json:
            try:
                parsed = json.loads(kconfig_json)
                if isinstance(parsed, dict):
                    kcfg = parsed
            except ValueError:
                kcfg = None

    # A preferences_pb without a parseable configuration_json means the Kotlin
    # app never saved settings (it would read defaults anyway), so it counts
    # as "no Kotlin side" rather than as newer Kotlin data.
    kotlin_has_config = kcfg is not None

    # ---- decide direction: newer mtime wins; missing side loses ----
    kotlin_wins = kotlin_has_config and (
        not opts_exists
        or os.path.getmtime(pb_path) >= os.path.getmtime(opts_path)
    )

    if kotlin_wins:
        # Kotlin -> Python
        if opts_exists:
            try:
                options = _cfg.load(opts_path)
            except Exception:
                options = _cfg.default_config()
        else:
            options = _cfg.default_config()

        applied = _apply_kotlin_to_options(kcfg, options)
        _backup(opts_path)
        _cfg.save(options, opts_path)
        report["from_kotlin"] = True
        report["applied"] = applied
        # The Kotlin file already holds the superset (it was newer); pushing
        # the merged result back would only add rounding drift, so both
        # markers are written: the cross-app decision is resolved.
        _touch(from_marker)
        _touch(to_marker)
        return report

    # Python -> Kotlin (options newer, or the only side that exists)
    try:
        options = _cfg.load(opts_path)
    except Exception:
        options = _cfg.default_config()

    if kcfg is None:
        kcfg = _fresh_kotlin_config()

    applied = _apply_options_to_kotlin(options, kcfg)
    new_json = json.dumps(kcfg, ensure_ascii=False, separators=(",", ":"))
    if pb_exists:
        _backup(pb_path)
        _write_datastore(pb_path, entries, new_json)
    else:
        _write_datastore(pb_path, [], new_json)
    report["to_kotlin"] = True
    report["applied"] = applied
    _touch(from_marker)
    _touch(to_marker)
    return report
