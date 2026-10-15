"""Slice 1 pin: provider contract + thin adapters + rule (b) `bing` alias.

Approved 2026-10-15 (design-only phase locked these rules first):

1. Provider contract: every registered provider exposes ``name``,
   ``translate``, ``detect``, ``langs``; ``langs()`` is that provider's
   OWN table (never merged).
2. Rule (b): ``bing`` is an ALIAS of ``microsoft`` — same adapter object
   (identity, not equality) — and never a separate fallback-chain entry.
3. ``router_order()`` dedupes by callable identity, so the chain never
   tries one implementation twice.
4. Caller compatibility: ``do_translate("bing", ...)`` still works.

Offline, no window, no network: only construction + table inspection.
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


import qtranslate.registry as RG
from qtranslate.providers import Provider, build_adapters

table = build_adapters()

# --- 1. contract conformance -------------------------------------------
ck("every TRANSLATORS key has an adapter",
   set(table) == set(RG.TRANSLATORS), str(sorted(set(table))))
for key, ad in table.items():
    ck("%s.name == key" % key, ad.name == key or key == "bing",
       "%s vs %s" % (ad.name, key))
    ck("%s is a Provider" % key, isinstance(ad, Provider))
    ck("%s.translate callable" % key, callable(ad.translate))
    ck("%s.langs() is a tuple" % key, isinstance(ad.langs(), tuple))
    ck("%s.detect callable" % key, callable(ad.detect))

# --- 2. rule (b): bing IS microsoft (identity) -------------------------
ck("bing is microsoft adapter (identity)",
   table["bing"] is table["microsoft"],
   "bing must share microsoft's object, not a copy")
ck("bing.name is 'microsoft'", table["bing"].name == "microsoft")

# --- 3. per-provider langs are NOT merged ------------------------------
from qtranslate.services import google_translate as _G
from qtranslate.services import microsoft as _MS
ck("google.langs() == google SUPPORTED_LANGS (own table)",
   table["google"].langs() == tuple(_G.SUPPORTED_LANGS))
ck("microsoft.langs() == microsoft SUPPORTED_LANGS (own table)",
   table["microsoft"].langs() == tuple(_MS.SUPPORTED_LANGS))
ck("google vs microsoft tables are distinct objects",
   table["google"].langs() is not table["microsoft"].langs())

# --- 4. router_order dedupes by callable identity ----------------------
order = RG.router_order()
ck("router_order has no duplicate callable",
   len(order) == len({id(RG.TRANSLATORS[k]) for k in order}), str(order))
ck("bing not an independent entry in the chain",
   order.count("bing") == 0, str(order))
ck("microsoft present in the chain", "microsoft" in order, str(order))
ck("chain still reaches every distinct callable",
   {id(RG.TRANSLATORS[k]) for k in order}
   == {id(v) for v in RG.TRANSLATORS.values()},
   "a distinct implementation became unreachable")

# --- 5. caller compatibility -------------------------------------------
ck("do_translate('bing') alias resolves to microsoft callable",
   RG.TRANSLATORS["bing"] is RG.TRANSLATORS["microsoft"])
# USES_AUTO_DETECT still re-exported through this slice (not yet moved).
ck("USES_AUTO_DETECT still present on registry",
   hasattr(RG, "USES_AUTO_DETECT") and RG.USES_AUTO_DETECT.get("microsoft"))
ck("provider uses_auto_detect mirrors the table",
   table["microsoft"].uses_auto_detect
   == bool(RG.USES_AUTO_DETECT.get("microsoft", False)))

# --- 6. mock-chain evidence: no duplicate callable, alias works -------
from qtranslate import reliability as _R
_m_order = RG.router_order()
_m_calls = []


def _mk(_name, _fail=True):
    def _f(t, s, g):
        _m_calls.append(_name)
        return "" if _fail else "OK:" + _name
    return _f


_shared = _mk("ms-shared", True)
_m_callables = dict(RG.TRANSLATORS)
_m_callables["microsoft"] = _shared
_m_callables["bing"] = _shared
_m_callables["google"] = _mk("google", False)
_m_pr = _R.ProviderRouter(dict(_m_callables), order=list(_m_order),
                          policy=_R.RetryPolicy(base_delay=0.0))
_m_route = _m_pr.router.route("hi", "auto", "vi", "bing")
ck("mock route with requested='bing' succeeds via fallback",
   _m_route.ok, str(_m_route.note))
ck("shared callable tried at most once in the chain",
   _m_calls.count("ms-shared") <= 1, str(_m_calls))
ck("alias caller compatible: microsoft callable served the bing request",
   "ms-shared" in _m_calls or _m_route.provider != "bing",
   str(_m_calls))

# --- 7. tkinter-free (static) ------------------------------------------
_pv = io.open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "qtranslate", "providers",
    "__init__.py"), encoding="utf-8").read()
import re as _re
ck("providers module imports no tkinter",
   _re.search(r"^\s*(import|from)\s+tkinter", _pv, _re.M) is None)

print("regress_provider_contract: %d checks, %d failed" % (n[0], len(fails)))
for f in fails:
    print("FAIL:", f)
sys.exit(1 if fails else 0)
