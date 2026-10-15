"""Router order follows ServicesOrder, not a hardcoded 5-name list.

Native D2 (FUN_0045CEDE): the service picker takes the head of the ordered
set, i.e. first in ServicesOrder. The port's ``_router`` used to pass
``order=["google", "microsoft", "bing", "deepl", "yandex"]``, which silently
dropped half of TRANSLATORS from the fallback chain (promt, babylon,
baidu, naver, youdao could never answer a fallback).

Now the order is built from ``config.services_order()`` (numeric ids)
mapped through ``SERVICE_NAMES``, with TRANSLATORS-only names appended.

Offline: no window, no network. Verifies the mapping logic and that the
built order covers every TRANSLATORS key.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


from qtranslate import config as C

# default ServicesOrder ids resolve to real TRANSLATORS names, in order
ids = list(C.DEFAULT_SERVICES_ORDER)
names = [C.SERVICE_NAMES[i] for i in ids if i in C.SERVICE_NAMES]
ck("default ids map to 9 names", len(names) == 9, str(names))
ck("google is head (id 1 first)", names[0] == "google", str(names))
ck("no duplicates in mapped order", len(set(names)) == len(names),
   str(names))

# the TRANSLATORS table keys. app.py holds them as an ALIAS of the
# registry table (Phase 2 slice 2026-10-15: ``from qtranslate.registry
# import TRANSLATORS, DICTS``), so read the keys from the registry source
# — parsing app.py's old literal no longer works by design.
src = io.open("qtranslate/registry.py", encoding="utf-8").read()
import re
m = re.search(r"TRANSLATORS = \{(.*?)\n\}", src, re.S)
keys = re.findall(r'"([a-z-]+)":', m.group(1))
ck("TRANSLATORS has 10 entries", len(keys) == 10, str(keys))
ck("app.TRANSLATORS is a registry alias, not a second literal",
   re.search(r"from qtranslate\.registry import TRANSLATORS, DICTS",
             io.open("qtranslate/app.py", encoding="utf-8").read()) is not None,
   "alias flip regressed: app.py defines its own table again")
# Slice 1 rule (b) 2026-10-15: router_order() dedupes by callable
# identity, so the alias "bing" (= microsoft) is NOT a chain entry, but
# every distinct callable stays reachable.
from qtranslate import registry as _RG
full = _RG.router_order()
ck("router_order covers all TRANSLATORS",
   set(full) == set(keys) - {"bing"}, str(full))
ck("router_order dedupes the bing/microsoft alias",
   "bing" not in full and "microsoft" in full, str(full))
ck("old hardcoded 5-list is gone",
   'order=["google", "microsoft", "bing"' not in src,
   "router must build order from services_order()")

# reliability-level: FallbackRouter honors a full order
from qtranslate import reliability as R
calls = {k: (lambda t, s, g, _k=k: _k.upper() + ":" + t) for k in keys}
pr = R.ProviderRouter(dict(calls), order=list(full),
                      policy=R.RetryPolicy(base_delay=0.0))
route = pr.router.route("hi", "en", "vi", "google")
ck("route walks the full order", route.ok, str(route.note))
ck("order length == distinct TRANSLATORS callables (bing deduped)",
   len(pr.router.order) == len(keys) - 1,
   "%d vs %d" % (len(pr.router.order), len(keys) - 1))

print("regress_router_order: %d checks, %d failed" % (n[0], len(fails)))
for f in fails:
    print("FAIL:", f)
sys.exit(1 if fails else 0)
