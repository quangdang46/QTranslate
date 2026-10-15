"""Pin session scraping parsers (rows E3/E8: Bing + Promt bootstrap).

Native loads each provider page through its JS engine to seed session
tokens before calling serviceTranslateRequest; the port scrapes the
same pages with urllib + regex. `_net_open` is the seam: mock it and
the parsers never touch the network.

Offline: fake translator pages with the real marker formats; the
layout-change errors are asserted too.
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


from qtranslate import session as S


class _Resp:
    def __init__(self, html, cookies=()):
        self._html = html.encode()
        self.headers = _H(cookies)

    def read(self):
        return self._html

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _H:
    def __init__(self, cookies):
        self._c = list(cookies)

    def get_all(self, _k):
        return list(self._c)


BING_HTML = ('IG:"ABC123XYZ", other params_AbusePreventionHelper '
             '=[42,"tok.en789",0], '
             'data-iid="translator.5023" data-iid="translator.5026"')
PROMT_HTML = '<input name="aft" value="PAFT-VALUE-1">'


def _bing():
    return _Resp(BING_HTML, ["MUID=aaa; path=/", "X=1; path=/"])


def _promt():
    return _Resp(PROMT_HTML, ["XSRF-TOKEN=xsrftok; path=/",
                              "sess=zzz; path=/"])


# --- bing --------------------------------------------------------------
_orig_net = S._net_open
S._net_open = lambda req, opener=None, data=None: _bing()
try:
    s = S.bing_session()
    ck("bing IG scraped", s.get("IG") == "ABC123XYZ", repr(s.get("IG")))
    ck("bing key scraped", s.get("key") == "42", repr(s.get("key")))
    ck("bing token scraped", s.get("token") == "tok.en789",
       repr(s.get("token")))
    ck("bing cookie jar flattened", "MUID=aaa" in s.get("cookie", ""),
       repr(s.get("cookie")))
    ck("bing iid list scraped",
       s.get("iids") == ["translator.5023", "translator.5026"],
       repr(s.get("iids")))
    ck("bing iid defaults to the first", s.get("iid") == "translator.5023",
       repr(s.get("iid")))
finally:
    S._net_open = _orig_net

# layout change -> honest error, not a silent empty dict
S._net_open = lambda req, opener=None, data=None: _Resp(
    "no markers here", ["MUID=x; path=/"])
try:
    _raised = False
    try:
        S.bing_session()
    except RuntimeError:
        _raised = True
    ck("bing layout change raises RuntimeError (not silent)",
       _raised)
finally:
    S._net_open = _orig_net

# --- promt -------------------------------------------------------------
S._net_open = lambda req, opener=None, data=None: _promt()
try:
    p = S.promt_session()
    ck("promt XSRF scraped", p.get("xsrf") == "xsrftok",
       repr(p.get("xsrf")))
    ck("promt paft scraped", p.get("paft") == "PAFT-VALUE-1",
       repr(p.get("paft")))
    ck("promt cookies flattened", "sess=zzz" in p.get("cookie", ""),
       repr(p.get("cookie")))
    ck("promt paft missing -> empty, not crash",
       S.promt_session() is not None)
finally:
    S._net_open = _orig_net


def _promt_nopaft():
    return _Resp("no aft here", ["a=b; path=/"])


S._net_open = lambda req, opener=None, data=None: _promt_nopaft()
try:
    p2 = S.promt_session()
    ck("promt without paft yields empty paft", p2.get("paft") == "",
       repr(p2.get("paft")))
finally:
    S._net_open = _orig_net

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_session: all checks ok (%d assertions)" % n[0])
