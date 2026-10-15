"""Pin the clipboard primitives (rows: Replace-selection write-back,
SendInput copy-capture sequence poll).

Native `FUN_0043BE56` writes CF_UNICODETEXT (0xD); `FUN_0043BF30` polls
`GetClipboardSequenceNumber`. The port wraps pyperclip + ctypes and must
report honestly (False / -1) when a backend is missing rather than raise.

Offline: pyperclip is faked; the sequence call is only checked for a
sane int shape (it does not open a window).
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


from qtranslate import clipboard as CB

ck("CF_UNICODETEXT is 0xD", CB.CF_UNICODETEXT == 0xD)

# --- write_text with a fake pyperclip -----------------------------------
written = {}


class _FakePyperclip:
    @staticmethod
    def copy(s):
        written["v"] = s

    @staticmethod
    def paste():
        return "pasted"


_orig = sys.modules.get("pyperclip")
sys.modules["pyperclip"] = _FakePyperclip
try:
    ck("write_text returns True on success", CB.write_text("hello") is True)
    ck("write_text passes the text through", written.get("v") == "hello",
       repr(written.get("v")))
    ck("write_text(None) writes empty string, not 'None'",
       CB.write_text(None) is True and written.get("v") == "",
       repr(written.get("v")))
    ck("read_text returns the clipboard text", CB.read_text() == "pasted")
finally:
    if _orig is not None:
        sys.modules["pyperclip"] = _orig
    else:
        sys.modules.pop("pyperclip", None)

# --- missing backend: honest failure, no raise --------------------------
class _Boom:
    @staticmethod
    def copy(s):
        raise RuntimeError("no clipboard")

    @staticmethod
    def paste():
        raise RuntimeError("no clipboard")


sys.modules["pyperclip"] = _Boom
try:
    ck("write_text reports False when the backend fails",
       CB.write_text("x") is False)
    ck("read_text returns '' when the backend fails", CB.read_text() == "")
finally:
    sys.modules.pop("pyperclip", None)

# --- sequence is an int (>=0 on Windows, -1 otherwise) ------------------
seq = CB.sequence()
ck("sequence returns an int", isinstance(seq, int), repr(seq))
ck("sequence is >= -1", seq >= -1, repr(seq))

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_clipboard: all checks ok (%d assertions)" % n[0])
