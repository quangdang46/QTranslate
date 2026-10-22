"""Pin key synthesis (row: SendInput synth FUN_0043BD5C).

Native: Ctrl-down → key-down → Sleep(0x20) → key-up → Ctrl-up via a
zeroed tagINPUT + SendInput(1, &input, 0x1C). The port routes through
the `keyboard` package; sendkeys.send/write_text wrap it and must
report honestly (False on a missing/failing backend) rather than raise.
The three app.py call sites (mouse-mode copy, _replace write-back,
Ctrl+C+C flow) now go through this module.

Offline: backend is faked; no keys are synthesized.
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


from qtranslate import sendkeys as SK


class _FakeKB:
    def __init__(self):
        self.sent = []
        self.written = []

    def send(self, combo):
        self.sent.append(combo)

    def write(self, text):
        self.written.append(text)


kb = _FakeKB()
ck("send delivers and reports True",
   SK.send("ctrl+c", backend=kb) is True and kb.sent == ["ctrl+c"],
   str(kb.sent))
ck("write_text delivers, capped at the limit",
   SK.write_text("x" * 3000, backend=kb) is True
   and kb.written == ["x" * 2000], str(len(kb.written[0])))
ck("write_text honors a custom limit",
   SK.write_text("abcdef", backend=kb, limit=3) is True
   and kb.written[-1] == "abc")
ck("write_text(None) writes empty",
   SK.write_text(None, backend=kb) is True and kb.written[-1] == "")


class _Boom:
    def send(self, _c):
        raise RuntimeError("no backend")

    def write(self, _t):
        raise RuntimeError("no backend")


ck("send reports False on backend failure",
   SK.send("ctrl+c", backend=_Boom()) is False)
ck("write_text reports False on backend failure",
   SK.write_text("x", backend=_Boom()) is False)

# --- the call sites go through the module -------------------------------
# The tkinter view is gone (2026-10-22); the call sites that used to read
# app.py are the Qt view (`qtranslate/qt/`) and the Win32 helper. The pins
# are "no direct synthesis bypasses the module's honest reporting".
import io
import re
from tests._view_src import view_source
_app = view_source() + io.open("qtranslate/win32app.py", encoding="utf-8").read()
ck("no direct keyboard.send left in the views",
   re.search(r"^\s*keyboard\.send\(", _app, re.M) is None)
ck("no direct keyboard.write left in the views",
   re.search(r"^\s*keyboard\.write\(", _app, re.M) is None)
ck("sendkeys.send used", "_SK.send(" in _app or "_SK2" in _app
   or "_SK3.send(" in _app or 'sendkeys.send("ctrl+c")' in _app)

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_sendkeys: all checks ok (%d assertions)" % n[0])
