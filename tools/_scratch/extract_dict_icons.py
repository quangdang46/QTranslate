"""Fix the mis-assigned youdao icon and bundle the dictionary-service icons.

Two findings, both by matching the installer payload's icons against
native's own strips (tools/_scratch/match_dict_icons.py):

1. **youdao was wrong.** The manifest assigned `youdao` to icon_033, the
   ORANGE "ud" -- which is URBAN DICTIONARY's logo. Native's main-window
   strip shows the red "y" in the youdao cell, and icon_041 is that red
   "y"; the block-average match puts icon_041 on native's youdao cell
   (score 742) and nothing else there. So the port's service strip was
   drawing Urban Dictionary's icon in the youdao slot.

2. **The dictionary services' icons are in the payload too.** Matched
   against native's dictionary strip (capture 2132, eleven cells):

       cell 1  Google Search      icon_015  (the multicoloured G)
       cell 2  WordReference      icon_037  (the "wR")
       cell 3  Babylon Dictionary icon_008  (the green/blue "b")
       cell 5  Multitran          icon_023  (the cyan "M")      score 227
       cell 6  ImTranslator       icon_019  (the figure)
       cell 7  Reverso            icon_031  (the red/blue swirl) score 297
       cell 8  Urban Dictionary   icon_033  (the orange "ud")
       cell 9  ABBYY Lingvo Live  icon_006  (the red square)    score 0.0
       cell 10 youdao             icon_041  (the red "y")
       cell 11 Oxford Learner     icon_027  (the olive circles)

   Cell 4 (Wikipedia) has NO icon in the payload: the only unused icon
   left is icon_035, a striped placeholder that matches nothing well.

Writes into a new, empty directory.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "g9", ROOT / "tools" / "g9_screenshot_diff.py")
g9 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g9)

ICONS = ROOT / "docs" / "review" / "rea" / "service_icons"
SVC_OUT = ROOT / "qtranslate" / "assets" / "service_icons"
DICT_OUT = ROOT / "qtranslate" / "assets" / "dict_icons"

# the dictionary service id -> (file stem, chunk)
DICT = {
    "Google Search": ("google-search", "icon_015.png"),
    "WordReference": ("wordreference", "icon_037.png"),
    "Babylon Dictionary": ("babylon", "icon_008.png"),
    "Multitran": ("multitran", "icon_023.png"),
    "ImTranslator": ("imtranslator", "icon_019.png"),
    "Reverso": ("reverso", "icon_031.png"),
    "Urban Dictionary": ("urban", "icon_033.png"),
    "ABBYY Lingvo Live": ("lingvo", "icon_006.png"),
    "youdao": ("youdao", "icon_041.png"),
    "Oxford Learner Dictionary": ("oxford", "icon_027.png"),
}


def main() -> int:
    DICT_OUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "note": "Dictionary-service icons recovered from the QTranslate "
                "6.10.0 installer payload, matched by pixels against "
                "native's own dictionary strip (docs/review/native_screens/"
                "2132.png). 16x16, the size native draws them at.",
        "provenance": {
            "payload": "docs/review/artifacts/nsis_payload_unpacked.bin",
            "extracted_by": "tools/_scratch/extract_dict_icons.py",
            "matched_against": "docs/review/native_screens/2132.png",
            "matcher": "tools/_scratch/match_dict_icons.py",
        },
        "size": [16, 16],
        "icons": {},
    }
    for name, (stem, chunk) in DICT.items():
        src = ICONS / chunk
        w, h, rgb = g9.png_decode(src)
        (DICT_OUT / (stem + ".png")).write_bytes(
            g9.png_encode(w, h, rgb))
        manifest["icons"][stem] = {
            "file": stem + ".png",
            "recovered_from": chunk,
            "service": name,
        }
        print("  %-14s <- %s" % (name, chunk))

    # Wikipedia is the eleventh cell and has NO .ico: the payload carries
    # 18 for 19 services, and the EXE's 24 RT_ICON groups do not hold it
    # either. Native draws a 16x16 white tile with a black serif W, so the
    # tile is re-drawn from native's own capture by the generator below.
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "wiki", ROOT / "tools" / "_scratch" / "make_wikipedia_tile.py")
    _wiki = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_wiki)
    _wiki.main()
    manifest["icons"]["wikipedia"] = {
        "file": "wikipedia.png",
        "service": "Wikipedia",
        "recovered_from": "not in the payload",
        "note": (
            "Wikipedia has NO .ico in the installer payload (19 services, "
            "18 icons) and none in the EXE's RT_ICON resources either. "
            "Native draws a 16x16 white tile with a black serif W -- read "
            "off its own capture (2132.png, cell 4, x=134..148, "
            "y=309..324) and re-drawn from those measurements by "
            "tools/_scratch/make_wikipedia_tile.py."),
    }
    (DICT_OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")

    # --- 1. the youdao fix in the SERVICE strip --------------------------
    w, h, rgb = g9.png_decode(ICONS / "icon_041.png")
    (SVC_OUT / "youdao.png").write_bytes(g9.png_encode(w, h, rgb))
    sm = json.loads((SVC_OUT / "manifest.json").read_text(encoding="utf-8"))
    sm["icons"]["youdao"]["recovered_from"] = "icon_041.png"
    sm["icons"]["youdao"]["corrected_2026-10-21"] = (
        "was icon_033.png -- the ORANGE 'ud', which is URBAN "
        "DICTIONARY's logo. Native's main-window strip shows the red "
        "'y' in the youdao cell, and the block-average match puts "
        "icon_041 there. The port's strip was drawing Urban "
        "Dictionary's icon in the youdao slot.")
    (SVC_OUT / "manifest.json").write_text(
        json.dumps(sm, indent=1, ensure_ascii=False), encoding="utf-8")
    print("fixed service_icons/youdao.png -> icon_041.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
