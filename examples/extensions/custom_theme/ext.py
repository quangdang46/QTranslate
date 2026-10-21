"""The example theme extension.

A theme is a record of COLOUR SLOTS, the same shape
``qtranslate.theme.load_theme_at`` returns: a ``{"Common": ...,
"Window": ...}`` dict. A theme may set only the slots it cares about --
``theme.slot()`` reports the rest as unset, so the rest is inherited --
and enabling it is the user's decision (D18), never the extension's.

Copy this folder into the per-user extensions directory and restart
QTranslate; the theme appears in the Options page's Appearance list.
"""

# A small, legible palette: the window's caption and border in a warm
# grey, the client background in a soft paper tone.
_THEME = {
    "Common": {
        "ClientBackColor": "f4f1ea",
        "GroupBoxColor": "d8d3c8",
    },
    "Window": {
        "Normal": {
            "Back": "f4f1ea",
            "Text": "2b2a28",
            "Border": "8a8378",
            "Caption": "8a8378",
        },
    },
}


def register(api):
    """Called once at startup with the SDK's API object."""
    api.register_theme("paper", _THEME)
