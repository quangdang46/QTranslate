"""Regression: UI extension slots — names from native, wiring from Core.

Phase 7's remaining port-side deliverable is "publish UI extension slots;
migrate theme/panel/menu/popup extension points". This suite pins both
halves:

* **The names are not invented.** The menu ids are the ``Menus[].Id``
  values a locale pack declares (read out of `Locales/English/lang.json`),
  and the panel names are the three ``Show*Pane`` toggles native's Options
  page reads. A slot name that native does not have would be an extension
  point nobody can reach.
* **The wiring reaches an extension.** ``ExtensionManager.register_ui``
  lazily builds the registry, ``ExtensionAPI.register_ui`` forwards to it,
  and the slot's winner resolves with the same declared-``replaces`` policy
  the provider and theme slots use — so an outcome never depends on
  discovery order.

Headless: no Tk, no network. The locale pack is read from the installed copy
and the suite SKIPS (exit 0) without it.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import ui_slots  # noqa: E402
from qtranslate.extensions import ExtensionAPI, ExtensionManager  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


INSTALLED = os.environ.get(
    "QTRANSLATE_DIR", r"C:\Program Files (x86)\QTranslate")
EN_PACK = os.path.join(INSTALLED, "Locales", "English", "lang.json")

# --- 1. the names come from native ------------------------------------
ck("three UI kinds are published",
   ui_slots.UI_KINDS == ("menu", "panel", "popup"), str(ui_slots.UI_KINDS))
ck("panel slots are the three native pane toggles",
   ui_slots.PANES == ("top", "middle", "services"), str(ui_slots.PANES))

menu_ids = ui_slots.MENU_SLOT_IDS
ck("menu slots are named after native's menu ids",
   len(menu_ids) >= 8, str(sorted(menu_ids)))
ck("every menu slot id is a real int", all(isinstance(v, int)
                                           for v in menu_ids.values()))
ck("the tray menu (id 5) is a published slot",
   menu_ids.get("tray") == 5, str(menu_ids.get("tray")))

if os.path.exists(EN_PACK):
    # use the PORT's reader: the packs are not strict JSON (7 of 35 carry
    # trailing commas), so json.loads alone would reject the very file whose
    # menu ids are the contract.
    from qtranslate import locale as _L
    pack = _L.load_pack("English")
    native_ids = {m.get("Id") for m in pack.get("Menus", ())
                  if isinstance(m, dict)}
    published = set(menu_ids.values())
    ck("the pack has menus to compare against", len(native_ids) >= 10,
       str(sorted(native_ids)))
    ck("every published menu id exists in the shipped pack",
       published <= native_ids,
       "published but absent: %r" % sorted(published - native_ids))
    # id 8 exists in the pack (the dict card's 'Remove dictionary' menu) and
    # is deliberately not published -- so nobody has to guess whether its
    # absence is an oversight.
    ck("the one deliberately-closed menu (id 8) is named as such",
       8 in native_ids and "dict_card" not in menu_ids,
       "id 8 handling changed")
else:
    print("SKIP: English pack not present (%s) -- slot-id cross-check skipped"
          % EN_PACK)

# --- 2. the slots enumerate ------------------------------------------
slots = ui_slots.all_slots()
ck("all_slots covers all three kinds",
   {s.kind for s in slots} == set(ui_slots.UI_KINDS))
ck("menu slots come first, in native-id order",
   [s.native_id for s in ui_slots.menu_slots()]
   == sorted(menu_ids.values()),
   str([s.native_id for s in ui_slots.menu_slots()]))
ck("every menu slot documents its native id",
   all(s.native_id and "Menus[].Id" in s.doc for s in ui_slots.menu_slots()))
ck("popup has icons and body",
   [s.name for s in ui_slots.popup_slots()] == ["icons", "body"])

# --- 3. registration, validation, and the winner ---------------------
reg = ui_slots.UISlotRegistry()
ck("an empty slot reports empty", reg.is_empty("panel", "top"))
reg.add("panel", "top", lambda: "builtin")
ck("a contribution is retrievable in order",
   [c() for c in reg.contributions("panel", "top")] == ["builtin"])
ck("...and the winner is the only one", reg.winner("panel", "top")
   ["contribution"]() == "builtin")

for bad in (("bogus", "top", None), ("panel", "bogus", None),
            ("menu", "bogus", None), ("popup", "bogus", None)):
    try:
        reg.add(*bad)
        ck("rejects %r" % (bad[:2],), False)
    except ValueError:
        ck("rejects %r" % (bad[:2],), True)

# last-wins, and declared replaces binds a conflict to a name
reg2 = ui_slots.UISlotRegistry()
reg2.add("menu", "tray", lambda: "a")
reg2.add("menu", "tray", lambda: "b")
ck("two undeclared contributions: last wins",
   reg2.winner("menu", "tray")["contribution"]() == "b")
ck("...and both are still composable",
   [c() for c in reg2.contributions("menu", "tray")] == ["a", "b"])

# --- 4. the manager and API forward to it ----------------------------
m = ExtensionManager()
ck("no UI registry until something registers",
   m.ui_slots is None)
m.register_ui("panel", "top", lambda: "from manager")
ck("register_ui creates it lazily", m.ui_slots is not None)
ck("...and the contribution lands",
   m.ui_slots.winner("panel", "top")["contribution"]() == "from manager")

api = ExtensionAPI(m)
api.register_ui("menu", "tray", lambda: "from api")
ck("ExtensionAPI.register_ui reaches the same registry",
   m.ui_slots.winner("menu", "tray")["contribution"]() == "from api",
   repr(m.ui_slots.winner("menu", "tray")["contribution"]()))
ck("...and the earlier manager-level slot is untouched",
   m.ui_slots.winner("panel", "top")["contribution"]() == "from manager")

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_ui_slots: all checks ok (%d assertions)" % n[0])
