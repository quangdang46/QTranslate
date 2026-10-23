"""The language index: an extension turns a provider's language INDEX
into a code, and a code into a display name.

The host keeps this table in ``qtranslate.languages``. The SDK carries a
copy for the same reason it carries ``Result``: it must not import the
desktop app. ``tests/regress_sdk_package.py`` compares the two tables.
"""
from __future__ import annotations

# The provider's SupportedLanguages order (Google Translate's Service.js,
# 75 entries with index 0 unused). Only the codes are needed here: the
# index IS the position, and the display names are the host's business.
LANG_CODES_BY_INDEX = (
    "", "auto", "af", "az", "sq", "ar", "hy", "eu", "be", "bg", "ca",
    "zh-CN", "zh-TW", "hr", "cs", "da", "nl", "en", "et", "fi", "tl",
    "fr", "gl", "de", "el", "ht", "iw", "hi", "hu", "is", "id", "it",
    "ga", "ja", "ka", "ko", "lv", "lt", "mk", "ms", "mt", "no", "fa",
    "pl", "pt", "ro", "ru", "sr", "sk", "sl", "es", "sw", "sv", "th",
    "tr", "uk", "ur", "vi", "cy", "yi", "eo", "hmn", "la", "lo", "kk",
    "uz", "si", "tg", "te", "km", "mn", "kn", "ta", "mr", "bn", "tt",
)


def lang_code_at(index: int) -> str:
    """The code at a provider language index, or "" when out of range."""
    try:
        i = int(index)
    except (TypeError, ValueError):
        return ""
    if 0 <= i < len(LANG_CODES_BY_INDEX):
        return LANG_CODES_BY_INDEX[i]
    return ""
