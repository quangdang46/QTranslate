"""Common fields: flat, non-per-state, measured from FUN_00464c2f and its own
getter functions.

FUN_00464c2f reads Common through four different getters, none of the colour
record getters:

  - FUN_00440942  ->  ButtonRadius, WindowBorderRadius    (hex string -> int)
  - FUN_00464724  ->  ClientBackColor, GroupBoxColor, GroupBoxHighlightColor   (hex -> 0xffffffff on fail)
  - FUN_00440921  ->  PaintClassicFocus                       (int, 0 when absent)

And its semantics are not the same as the colour sections:

  * WindowBorderRadius is only written when the key is present AND < 4.
    So an absent key does NOT mean unset; it keeps the default. This is the
    opposite of the colour slots, where absent == 0xffffffff.
  * ClientBackColor / GroupBoxColor / GroupBoxHighlightColor are hex values
    (not BGR); 0xffffffff => GetSysColor(COLOR_BTNFACE).
  * PaintClassicFocus is an int/bool (0 when absent); not a colour.

Because they are flat and non-per-state, they have no section key in
SECTION_SLOTS. They are handled separately by the loader.
"""
import json, re

PAYLOAD = "docs/review/artifacts/nsis_payload_unpacked.bin"
OFF = [0x97b30,0x98285,0x98cf5,0x99359,0x99d63,0x9a7b4,0x9af7e]


def load_themes():
    data = open(PAYLOAD, "rb").read()
    out = []
    for o in OFF:
        ln = int.from_bytes(data[o:o+4], "little")
        out.append(json.loads(re.sub(r"//[^\n]*", "", data[o+4:o+4+ln].decode("utf-8"))))
    return out


if __name__ == "__main__":
    tl = load_themes()
    for d in tl:
        c = d.get("Common", {})
        print(sorted(c.keys()), c)
