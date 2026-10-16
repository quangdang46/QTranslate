"""Regression: the port's HOTKEY_NAMES are exactly the native option keys.

`config.HOTKEY_NAMES` names the Options keys whose values are hotkey
bindings. A missing key means a task the user cannot bind; an extra key
means a name native never reads, which is silently dead configuration.

Both directions are checked against the recovered image, which stores them
as one run of wide strings around offset `1185518`:

    HotKeySpeechInput, HotKeyDictionaryClipboard, HotKeyTextRecognition,
    HotKeySwitchMouseMode, HotKeyTranslateClipboardInMainWindow,
    HotKeyTranslateClipboard, HotKeyTranslateClipboardInPopupWindow,
    HotKeyCopyTranslation, HotKeyReplaceSelection, HotKeyListenTranslation,
    HotKeyConvertTextLayout, HotKeyKeyboard, HotKeyListenText,
    HotKeyDictionary, HotKeyHistory, HotKeyPopupWindow, HotKeyMainWindow

Extraction detail that matters: a naive scan for `HotKey` followed by
`.split("\x00")` stops each string at the first NUL, which lands
mid-character for every one of them -- the names come out truncated by
one or two characters (`HotKeyConvertTextLayou`). This suite instead walks
the bytes two at a time to the wide terminator, which yields each name
complete. It still compares by PREFIX, so that a later refactor to the
naive scan cannot manufacture a mismatch, and it pins the exact list so an
extraction that drops one key fails loudly instead of silently.

Headless: the image is READ, never executed.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.config import HOTKEY_NAMES  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(REPO, "docs", "review", "artifacts",
                   "QTranslate.6.10.0.exe")

if not os.path.exists(EXE):
    print("SKIP: recovered image not present (%s)" % EXE)
    raise SystemExit(0)

RAW = io.open(EXE, "rb").read()

# --- the native run, read as wide strings terminated by a NUL pair -----
NEEDLE = b"H\x00o\x00t\x00K\x00e\x00y\x00"
native_raw = set()
pos = 0
while True:
    i = RAW.find(NEEDLE, pos)
    if i < 0:
        break
    pos = i + 1
    end = i
    # walk two bytes at a time until the wide terminator (a NUL pair)
    while end + 1 < len(RAW) and not (RAW[end] == 0 and RAW[end + 1] == 0):
        end += 2
    native_raw.add(RAW[i:end].decode("utf-16-le", "replace"))

# The scan above walks two bytes at a time to the wide terminator, so each
# name comes out complete -- no truncation, no dedupe needed. Keep the raw
# set and match by prefix only, so that a future extraction that DOES
# truncate cannot manufacture a mismatch.
native_names = sorted(native_raw)
ck("the scan finds a non-trivial hotkey key run",
   len(native_names) >= 15, str(len(native_names)))

# Two of the hits are not hotkey bindings and are excluded on purpose:
# `HotKeyControl...` is the Options SECTION title in the UI string table
# and `HotKeys` the toggle name. They are not bindings.
NOT_BINDINGS = {"HotKeyControl", "HotKeys"}
native_bindings = sorted(s for s in native_names if s not in NOT_BINDINGS)
ck("the run contains the section/toggle names as well",
   set(native_names) - set(native_bindings) == NOT_BINDINGS,
   str(sorted(set(native_names) - set(native_bindings))))


def native_has(key):
    """Is ``key`` (or a truncation of it) in the native run?"""
    return any(sv.startswith(key) or key.startswith(sv)
               for sv in native_bindings)


def native_only(keys):
    """Native binding names with no port counterpart."""
    return [sv for sv in native_bindings
            if not any(k.startswith(sv) or sv.startswith(k) for k in keys)]


# --- 1. no port key is a name native does not have --------------------
extra = [k for k in HOTKEY_NAMES if not native_has(k)]
ck("every port key is a native Options key", not extra, str(extra))

# --- 2. no native key is missing from the port -----------------------
missing = native_only(HOTKEY_NAMES)
ck("every native key is in the port", not missing, str(missing))

# --- 3. the count, and the exact list (so a drop is not silent) ------
ck("the port declares 17 hotkey keys", len(HOTKEY_NAMES) == 17,
   str(len(HOTKEY_NAMES)))
ck("the keys are unique", len(set(HOTKEY_NAMES)) == len(HOTKEY_NAMES))
EXPECTED = [
    "HotKeySpeechInput", "HotKeyDictionaryClipboard",
    "HotKeyTextRecognition", "HotKeySwitchMouseMode",
    "HotKeyTranslateClipboardInMainWindow", "HotKeyTranslateClipboard",
    "HotKeyTranslateClipboardInPopupWindow", "HotKeyCopyTranslation",
    "HotKeyReplaceSelection", "HotKeyListenTranslation",
    "HotKeyConvertTextLayout", "HotKeyKeyboard", "HotKeyListenText",
    "HotKeyDictionary", "HotKeyHistory",
    "HotKeyPopupWindow", "HotKeyMainWindow",
]
ck("the exact list is pinned", sorted(HOTKEY_NAMES) == sorted(EXPECTED),
   "port=%r" % (HOTKEY_NAMES,))

# --- 4. every bound key has a handler in app.py ----------------------
APP = io.open(os.path.join(REPO, "qtranslate", "app.py"),
              encoding="utf-8", errors="replace").read()
unbound = [k for k in HOTKEY_NAMES
           if ('"%s"' % k) not in APP and ("'%s'" % k) not in APP]
ck("every hotkey key is referenced by app.py (so it can be bound)",
   not unbound, str(unbound))
bound = [k for k in HOTKEY_NAMES if '"%s":' % k in APP]
ck("at least a dozen are actually mapped to handlers",
   len(bound) >= 12, str(len(bound)))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_hotkey_option_keys: all checks ok (%d assertions)" % n[0])
