"""The language table: code -> display name, and back.

This is Core data, not view data: the tkinter view's two language
combos and the PySide6 view's both read it, and the SDK and the CLI
need the same names. It used to live in ``qtranslate/app.py`` (the
tkinter front end), which meant the Qt front end had to import the
tkinter module for two constants -- a dependency that would have kept
tkinter alive after its removal.

The table is transcribed from the native's Services/Google
Translate/Service.js ``SupportedLanguages`` (75 codes; index 1 = auto,
index 57 = vi). The display names are ISO English names: the native's
combo shows localized names from its own ``.mui`` resources, and the
English mapping is equivalent for selection.

Toolkit-free, like every other Core module.
"""
from __future__ import annotations

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


def _supported_codes():
    """The codes the Google provider supports, in the provider's order."""
    try:
        from qtranslate.services.google_translate import SUPPORTED_LANGS
        return [c for c in SUPPORTED_LANGS if c != -1]
    except Exception:
        return list(_ISO_NAMES)


LANGS = _supported_codes()
TO_LANGS = [c for c in LANGS if c != "auto"]
LANG_DISPLAY = {c: _ISO_NAMES.get(c, c) for c in LANGS}
LANG_CODES = {v: k for k, v in LANG_DISPLAY.items()}


def display(code: str) -> str:
    """The display name of a language code."""
    return LANG_DISPLAY.get(code, code)


def code(name: str) -> str:
    """The code of a display name."""
    return LANG_CODES.get(name, "auto")
