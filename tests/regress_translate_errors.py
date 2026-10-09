"""Regression: provider failures surface as the native error string, not as
translation text.

Native behavior (FUN_00404A12 orchestrator): a failed provider request yields
the app-level "no data" error string (string id 190), never a fabricated
payload. The port's Promt adapter previously caught exceptions and returned
``f"[error] {e}"`` as if it were the translation, bypassing that path.

Offline only: no network. Providers are monkey-patched to raise.
"""
import sys

sys.path.insert(0, "C:/Users/ADMIN/qtranslate-re")

import qtranslate.app as app  # noqa: E402
from qtranslate.services import promt as _promt  # noqa: E402

failures = []


def check(name, cond, detail=""):
    if not cond:
        failures.append("%s%s" % (name, (" -- " + detail) if detail else ""))


# 1. _t_promt must propagate, not fabricate "[error] ..." text.
_orig_session = _promt.session


def _boom(*a, **k):
    raise RuntimeError("simulated provider failure")


_promt.session = _boom
try:
    raised = False
    try:
        app._t_promt("hello", "en", "vi")
    except Exception:
        raised = True
    check("_t_promt propagates provider failure (no pseudo-translation)", raised)
finally:
    _promt.session = _orig_session

# 2. do_translate must return the native error string when a provider raises.
_promt.session = _boom
try:
    out = app.do_translate("promt", "hello", "vi", src="en")
finally:
    _promt.session = _orig_session
check("do_translate returns native 'no data' string on provider failure",
      out.startswith("No data returned"), repr(out))
check("do_translate never returns an '[error]' pseudo-translation",
      "[error]" not in out, repr(out))

# 3. No translator adapter anywhere fabricates an "[error] ..." result.
import inspect  # noqa: E402

src = inspect.getsource(app)
check("no '[error] {e}' fabricated return in adapters",
      'return f"[error] {e}"' not in src)

if failures:
    raise SystemExit("FAIL:\n  " + "\n  ".join(failures))
print("OK: provider failures route to the native error string")
