"""Slice 3 pin: ExtensionManager — registered vs enabled, two order
contracts kept separate, override conflict reported (not auto-resolved),
fail-open on a broken registration.

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


from qtranslate import registry as RG
from qtranslate.extensions import ExtensionManager, OverrideConflict

m = ExtensionManager()

# --- registered vs enabled --------------------------------------------
ck("registered includes retired-host providers (babylon)",
   "babylon" in m.providers(), str(sorted(m.providers())))
ck("enabled dedupes the bing/microsoft alias",
   "bing" not in m.enabled() and "microsoft" in m.enabled(),
   str(m.enabled()))
ck("enabled is a subset of registered",
   set(m.enabled()) <= set(m.providers()), str(m.enabled()))

# --- two order contracts are distinct ---------------------------------
strip = m.strip()
ck("strip has no extras beyond the native set",
   set(strip) <= set(m.enabled()), str(strip))
ck("router_order and strip are computed by different rules",
   m.enabled() == RG.router_order() or set(m.enabled()) == set(RG.router_order()),
   "%r vs %r" % (m.enabled(), RG.router_order()))

# --- override conflict reported, not auto-resolved --------------------
m2 = ExtensionManager()


def _fake(t, s, g):
    return "custom"


m2.register("ext.custom_a", _fake, replaces="google")
_conflict = None
try:
    m2.register("ext.custom_b", _fake, replaces="google")
except OverrideConflict as e:
    _conflict = str(e)
ck("second override of the same id raises OverrideConflict",
   _conflict is not None and "pick the winner" in _conflict, repr(_conflict))
ck("conflict recorded for the user to review",
   m2.conflicts().get("google") == "ext.custom_a", str(m2.conflicts()))
ck("active() serves the declared override",
   m2.active("google") is _fake, repr(m2.active("google")))

# --- rule (b): bing resolves to microsoft ------------------------------
ck("active('bing') is active('microsoft')",
   m.active("bing") is m.active("microsoft"))

# --- fail-open on a broken registration --------------------------------
_broken = None
try:
    m.register("ext.broken", "not-callable")
except TypeError as e:
    _broken = str(e)
ck("non-callable registration is rejected (fail-open at call site)",
   _broken is not None, repr(_broken))
ck("built-in google still active after a rejected registration",
   m.active("google") is not None)

# --- tkinter-free ------------------------------------------------------
_src = io.open("qtranslate/extensions.py", encoding="utf-8").read()
ck("extensions module imports no tkinter",
   re.search(r"^\s*(import|from)\s+tkinter", _src, re.M) is None)

print("regress_extensions: %d checks, %d failed" % (n[0], len(fails)))
for f in fails:
    try:
        print("FAIL:", f)
    except UnicodeEncodeError:
        print("FAIL:", f.encode("ascii", "replace").decode("ascii"))
sys.exit(1 if fails else 0)
