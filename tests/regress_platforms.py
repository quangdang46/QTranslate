"""Slice 4 pin: platform interfaces — Core talks through the interface,
adapters report capabilities honestly, unavailable adapter is honest.

Offline, no window, no network.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate import platforms as P

# --- interfaces exist --------------------------------------------------
for iface in ("Clipboard", "Hotkey", "Capture", "Audio", "Window",
              "Paths", "SpeechInput"):
    ck("interface %s defined" % iface, hasattr(P, iface))

# --- windows adapter reports honestly ----------------------------------
wa = P.WindowsAdapter()
ck("windows clipboard available", wa.capability("clipboard") == "available")
ck("windows speech needs permission (not claimed available)",
   wa.capability("speech") == "needs-permission")
ck("unknown capability reported unavailable",
   wa.capability("nope") == "unavailable")

# --- unavailable adapter is honest -------------------------------------
ua = P.UnavailableAdapter()
ck("unavailable adapter reports unavailable",
   ua.capability("clipboard") == "unavailable")
_threw = False
try:
    ua.read_text()
except NotImplementedError:
    _threw = True
ck("unavailable adapter raises on use (no silent fake)", _threw)

# --- current() picks per platform --------------------------------------
cur = P.current()
ck("current() returns an adapter with capability()",
   callable(getattr(cur, "capability", None)))

# --- the macOS branch resolves the per-user folder -----------------------
# The extension loader resolves its folder through the Paths adapter, so
# on macOS it has to be a real path -- not the UnavailableAdapter's
# NotImplementedError, which made the loader return [] silently.
_mac = P.MacOSAdapter()
ck("the macOS adapter resolves the app-data dir",
   _mac.app_data() == P.app_data_dir(), _mac.app_data())
ck("the macOS adapter resolves the extensions dir",
   _mac.extensions_dir() == os.path.join(P.app_data_dir(), "extensions"),
   _mac.extensions_dir())
ck("the macOS extensions dir is absolute",
   os.path.isabs(_mac.extensions_dir()), _mac.extensions_dir())
ck("the macOS adapter reports the clipboard available",
   _mac.capability("clipboard") == P.Capability.AVAILABLE)
ck("the macOS adapter reports the Win32-only pieces unavailable",
   _mac.capability("hotkey") == P.Capability.UNAVAILABLE
   and _mac.capability("capture") == P.Capability.UNAVAILABLE)
_threw = False
try:
    _mac.sequence()  # noqa: SLF001 -- probing the interface contract
except (NotImplementedError, AttributeError):
    _threw = True
ck("the macOS adapter does not fake the Win32 clipboard counter",
   _threw)
_src_cur = io.open("qtranslate/platforms.py", encoding="utf-8").read()
ck("current() picks the macOS adapter on darwin",
   re.search(r'sys\.platform\s*==\s*"darwin"', _src_cur) is not None)

# --- tkinter-free ------------------------------------------------------
_src = io.open("qtranslate/platforms.py", encoding="utf-8").read()
ck("platforms module imports no tkinter",
   re.search(r"^\s*(import|from)\s+tkinter", _src, re.M) is None)
ck("platforms module does not import win32 at module level",
   re.search(r"^\s*import\s+win32", _src, re.M) is None)

# --- the settings path is absolute and outside the package ----------------
# `config.DEFAULT_PATH` used to be `os.path.join(os.environ.get("APPDATA",
# ""), "QTranslate", "Options.json")`. Off Windows `APPDATA` is empty, so
# that was a RELATIVE path -- and on macOS, where the filesystem is
# case-insensitive, `QTranslate/Options.json` resolved to
# `qtranslate/Options.json` INSIDE the package directory.
from qtranslate import config as C  # noqa: E402

ck("the settings path is absolute",
   os.path.isabs(C.DEFAULT_PATH), C.DEFAULT_PATH)
ck("the settings path is not inside the package",
   os.path.abspath(C.DEFAULT_PATH) != os.path.abspath(
       os.path.join(os.path.dirname(os.path.dirname(
           os.path.abspath(__file__))), "qtranslate", "Options.json")),
   C.DEFAULT_PATH)
ck("the settings path keeps the native's shape",
   os.path.basename(os.path.dirname(C.DEFAULT_PATH)) == "QTranslate",
   C.DEFAULT_PATH)
ck("the app-data dir is the platform's",
   P.app_data_dir() == os.path.dirname(C.DEFAULT_PATH),
   "%r vs %r" % (P.app_data_dir(), os.path.dirname(C.DEFAULT_PATH)))

# --- load()/save() resolve the path at CALL time --------------------------
# A default argument freezes its value when the function is defined, so a
# caller that points DEFAULT_PATH somewhere else still read and wrote the
# ORIGINAL file.
import tempfile  # noqa: E402
import json  # noqa: E402

_tmp = tempfile.mkdtemp(prefix="qtranslate-cfg-")
_saved = C.DEFAULT_PATH
try:
    C.DEFAULT_PATH = os.path.join(_tmp, "Options.json")
    C.save({"General": {"probe": 1}})
    ck("save() honours a redirected DEFAULT_PATH",
       os.path.isfile(os.path.join(_tmp, "Options.json")),
       sorted(os.listdir(_tmp)))
    ck("load() reads back what save() wrote",
       C.load().get("General", {}).get("probe") == 1,
       repr(C.load()))
finally:
    C.DEFAULT_PATH = _saved
    try:
        os.remove(os.path.join(_tmp, "Options.json"))
        os.rmdir(_tmp)
    except Exception:
        pass

# --- the settings directory exists -----------------------------------------
# The app persists a setting from ~38 places, each of them opening
# DEFAULT_PATH directly inside a `try` that swallows the error. On a
# fresh install the directory did not exist, so every one of those writes
# raised FileNotFoundError and the setting was silently lost.
ck("the settings directory exists",
   os.path.isdir(os.path.dirname(C.DEFAULT_PATH)),
   os.path.dirname(C.DEFAULT_PATH))
_deep = tempfile.mkdtemp(prefix="qtranslate-cfg-")
try:
    _missing = os.path.join(_deep, "a", "b", "Options.json")
    C.ensure_dir(_missing)
    ck("ensure_dir creates a missing directory",
       os.path.isdir(os.path.dirname(_missing)), _missing)
    C.DEFAULT_PATH = _missing
    C.save({"General": {"probe": 2}})
    ck("save() works into a directory that did not exist",
       C.load().get("General", {}).get("probe") == 2, _missing)
finally:
    C.DEFAULT_PATH = _saved
    import shutil
    shutil.rmtree(_deep, ignore_errors=True)

print("regress_platforms: %d checks, %d failed" % (n[0], len(fails)))
for f in fails:
    print("FAIL:", f)
sys.exit(1 if fails else 0)
