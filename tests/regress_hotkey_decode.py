"""Pin hotkey decode/format against the FUN_00405A17 decompile.

Native (read 2026-10-15): skip when ``word == 0`` or ``(word & 0xFFF) ==
0``; else ``RegisterHotKey(hwnd, id=word, mod=(word>>8)&0xF, vk=word&0xFF)``.
The port's ``decode_hotkey`` mirrors exactly this split (plus an
``enabled`` flag the native register-or-skip branch implies).

Offline: pure integer splitting, no window registration.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate.config import decode_hotkey, format_hotkey

# --- observed real values (config.py docstring) -------------------------
# HotKeyReplaceSelection = 343 (0x157: vk=0x57 'W', mod=1)
d = decode_hotkey(343)
ck("343 -> vk 0x57", d["vk"] == 0x57, str(d))
ck("343 -> modifiers 1", d["modifiers"] == 1, str(d))
ck("343 is enabled", d["enabled"] is True, str(d))
# HotKeyPopupWindow = 593 (0x251: vk=0x51 'Q', mod=2)
d2 = decode_hotkey(593)
ck("593 -> vk 0x51", d2["vk"] == 0x51, str(d2))
ck("593 -> modifiers 2", d2["modifiers"] == 2, str(d2))

# --- the native skip branch --------------------------------------------
ck("0 is disabled", decode_hotkey(0)["enabled"] is False)
ck("a word with low 12 bits clear is disabled (native skip)",
   decode_hotkey(0x1000)["enabled"] is False, str(decode_hotkey(0x1000)))

# --- display strings ----------------------------------------------------
ck("593 formats with Ctrl", "Ctrl" in format_hotkey(593),
   format_hotkey(593))
ck("593 formats with Q", "Q" in format_hotkey(593), format_hotkey(593))
ck("empty code formats to empty string", format_hotkey(0) == "")

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_hotkey_decode: all checks ok (%d assertions)" % n[0])
