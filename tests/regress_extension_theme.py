"""Regression: theme extension slot (Slice 9a).

The extension manifest may declare the ``theme`` capability, but before
Slice 9a the loader did nothing with themes -- a theme-declaring
extension loaded with no effect. Now:

  * ``ExtensionAPI.register_theme(name, record, replaces=None)``
    registers a theme-colour record (same shape ``theme.load_theme_at``
    returns); a non-dict raises TypeError (fail-open at the call site);
  * a second claimant on the same built-in theme id raises
    ``OverrideConflict`` (D18 -- the user picks the winner), and the
    failed registration is dropped so the first claim stands;
  * ``ExtensionManager.active_theme(name)`` resolves with native
    semantics: extension name wins, then a declared override, then the
    built-in ``theme.active_theme`` (which itself falls back to
    ``default_theme``, never None -- FUN_0044b44f);
  * partial records inherit: slot-by-slot resolution happens in the
    existing ``theme.slot()`` / ``state_colors()`` readers, so an
    extension record with two sections does not need the other three.

Headless: no Tk import anywhere in this file.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import theme as TH  # noqa: E402
from qtranslate.extensions import (  # noqa: E402
    ExtensionAPI, ExtensionManager, OverrideConflict,
)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


m = ExtensionManager()
api = ExtensionAPI(m)

ck("register_theme returns the name",
   api.register_theme("acme-dark", {"Common": {"ButtonRadius": 4}})
   == "acme-dark")
ck("themes() lists it", list(m.themes()) == ["acme-dark"])
ck("no theme conflicts yet", m.theme_conflicts() == {})

try:
    api.register_theme("bad", "not-a-dict")
    ck("non-dict record raises TypeError", False)
except TypeError:
    ck("non-dict record raises TypeError", True)
ck("failed registration is dropped", "bad" not in m.themes())

api.register_theme("t-one", {"Window": {"Back": "#111111"}},
                   replaces="Default")
ck("override declared", m.theme_conflicts() == {"Default": "t-one"})
try:
    api.register_theme("t-two", {"Window": {"Back": "#222222"}},
                       replaces="Default")
    ck("second claimant raises OverrideConflict", False)
except OverrideConflict:
    ck("second claimant raises OverrideConflict", True)
ck("failed override keeps the first claim",
   m.theme_conflicts() == {"Default": "t-one"})

# resolution order: extension name > declared override > built-in
ck("direct extension name wins",
   m.active_theme("acme-dark") == {"Common": {"ButtonRadius": 4}})
mlater = ExtensionManager()
later_api = ExtensionAPI(mlater)
later_api.register_theme("replacement",
                         {"Window": {"Back": "#333333"}},
                         replaces="DoesNotExistBuiltIn")
ck("declared override resolves",
   mlater.active_theme("DoesNotExistBuiltIn")
   == {"Window": {"Back": "#333333"}})

# built-in fallback: unknown names fall through to the native-shaped
# default, never None
fallback = ExtensionManager().active_theme("NoSuchTheme")
ck("unknown theme falls back to built-in, never None",
   isinstance(fallback, dict) and fallback)
ck("fallback is the native default object",
   fallback == TH.default_theme())

# partial records inherit slot-by-slot through the existing readers:
# an extension theme that only knows Window/Back must still yield a
# valid colour for a known section and UNSET for the rest.
partial = m.active_theme("acme-dark")
ck("known overridden slot reads back",
   partial.get("Common", {}).get("ButtonRadius") == 4)
ck("missing section is simply absent (slot() will report UNSET)",
   "Window" not in partial)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_extension_theme: all checks ok (%d assertions)" % n[0])
