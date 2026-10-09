"""Regression: Google tkk seed markers + hourly cache (E21/F12).

Native evidence, from Ghidra 12.1.4 decompile of the real binary
(docs/review/artifacts/QTranslate.6.10.0.exe, sha256 f35a3bc8…):

  FUN_0040FB54  builds marker strings from the .rdata wide-string table:
                DAT_0051d57c = "_ctkk='"   (primary start)
                DAT_0051d5c4 = "TKK='"      (alternate start)
                DAT_0051d58c = "';"         (end, shared by both)
                then calls FUN_0040fec9(&out, &path, &start, &end) and, when
                the result is empty (the `*(int *)(DAT_00549774 + -0xc) == 0`
                guard), retries once with the TKK=' start marker.
  FUN_0040fec9  GETs https://translate.google.<domain> + "/translate_a/element.js"
                (codepage 0xfde9), then slices between the two markers via two
                ATL CStringT::wchar_t::Find calls.

The earlier port used a single regex over "_ctkk='..." and had no alternate
marker, so a page served with only `TKK=` fell back to tkk "0.0" while native
still recovered the seed. This test pins the two-marker behaviour.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qtranslate.services.google_translate import (  # noqa: E402
    _tkk_slice, refresh_tkk, _TKK_START, _TKK_START_ALT, _TKK_END, _TKK_URL)

fail = []
_N = [0]


def ck(n, c, d=""):
    _N[0] += 1
    if not c:
        fail.append(n + (" -- " + d if d else ""))


# --- the markers themselves must match the native .rdata literals ---
ck("primary start marker", _TKK_START == "_ctkk='", _TKK_START)
ck("alternate start marker", _TKK_START_ALT == "TKK='", _TKK_START_ALT)
ck("shared end marker", _TKK_END == "';", _TKK_END)
ck("element.js path", _TKK_URL == "/translate_a/element.js", _TKK_URL)

# --- slice semantics: CString::Find(start, 0) then Find(end, past start) ---
ck("native primary form",
   _tkk_slice("var _ctkk='409484.2968434358';") == "409484.2968434358")
ck("comment before marker", _tkk_slice("/*c*/_ctkk='1.2';") == "1.2")
ck("substring (native Find has no anchor)",
   _tkk_slice("a_ctkk='9.9';b") == "9.9")

# --- alternate marker only (the case the old regex missed) ---
ck("alternate marker recovers", _tkk_slice("var TKK='77.1';") == "77.1")
ck("primary wins when both present",
   _tkk_slice("TKK='0.0' _ctkk='5.5';") == "5.5")

# --- empties fall through to the alternate, then to "0.0" ---
ck("empty primary falls to alternate",
   _tkk_slice("_ctkk=''; TKK='3.3';") == "3.3")
ck("both empty -> empty string", _tkk_slice("_ctkk=''; TKK='';") == "")
ck("no marker -> empty string", _tkk_slice("garbage") == "")
ck("start with no end -> empty string", _tkk_slice("_ctkk='1234") == "")

# --- hourly cache (native keys on the calendar hour) ---
import qtranslate.services.google_translate as G  # noqa: E402


class _Resp:
    def __init__(self, body):
        self._b = body.encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _with_fetch(body, fn):
    class _Ctx:
        def http_open(self, req):
            return _Resp(body)
    old, G.common.http_open = G.common.http_open, _Ctx().http_open
    try:
        return fn()
    finally:
        G.common.http_open = old


# a fresh (empty) cache must populate from the page
G._TKK_CACHE = ("", 0.0)
with_fetch = lambda body, f: _with_fetch(body, f)
got = _with_fetch("var _ctkk='11.22';", lambda: G.refresh_tkk())
ck("refresh_tkk seeds from page", got == "11.22", got)
ck("refresh_tkk writes Options.GoogleTkk",
   G.Options.get("GoogleTkk") == "11.22", str(G.Options.get("GoogleTkk")))

# within the hour the page must NOT be re-fetched
calls = []


def _counting(req):
    calls.append(1)
    return _Resp("var _ctkk='99.99';")


class _Ctx2:
    def http_open(self, req):
        return _counting(req)


old = G.common.http_open
G.common.http_open = _Ctx2().http_open
try:
    got2 = G.refresh_tkk()
finally:
    G.common.http_open = old
ck("cache hit avoids refetch", got2 == "11.22" and not calls,
   f"got={got2} fetches={len(calls)}")

# force=True must refetch
got3 = _with_fetch("var _ctkk='33.44';", lambda: G.refresh_tkk(force=True))
ck("force bypasses cache", got3 == "33.44", got3)
G._TKK_CACHE = ("", 0.0)
G.Options.pop("GoogleTkk", None)

if fail:
    print("FAIL %d" % len(fail))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_tkk_markers: all checks ok (%d assertions)" % _N[0])
