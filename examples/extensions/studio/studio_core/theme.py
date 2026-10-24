"""Studio's themes: two PARTIAL records.

A theme may claim only the slots it cares about -- unset slots inherit
slot-by-slot, exactly like a partial native theme file. Enabling one is
the USER's decision (Options → Appearance), never the extension's.
"""

DARK = {
    "Common": {"ClientBackColor": "14181f", "GroupBoxColor": "222833"},
    "Window": {"Normal": {"Back": "14181f", "Text": "d7e3f4",
                          "Border": "2c3440", "Caption": "2c3440"}},
}

HIGH_CONTRAST = {
    "Common": {"ClientBackColor": "000000"},
    "Window": {"Normal": {"Back": "000000", "Text": "ffffff",
                          "Border": "ffffff", "Caption": "000000"}},
}
