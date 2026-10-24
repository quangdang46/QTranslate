"""Pin session scraping parsers (rows E3/E8: Bing + Promt bootstrap).

Native loads each provider page through its JS engine to seed session
tokens before calling serviceTranslateRequest; the port scrapes the
same pages with urllib + regex. `_net_open` is the seam: mock it and
the parsers never touch the network.

Offline: fake translator pages with the real marker formats; the
layout-change errors are asserted too.
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


# The PROMT fixture spells the markers the recovered image spells
# (tests/regress_session_markers.py reads them out of .rdata):
#   id="_paft" type="hidden" value="<paft>"
# The BING fixture spells the LIVE page (2026-10-24): the IG marker on
# its own, the credentials in params_AbusePreventionHelper as
# [<expiry-ts>,"<token>",<TTL>]. The old adjacent `IG:"<ig>","<token>",<key>`
# form the image documents no longer exists on the page that serves
# today -- bing live-translate with key=<expiry> is the proof the shape
# is right (LIVE_RESULTS.md).
BING_HTML = ('var params_RichTranslateHelper = [IG:"ABC123XYZ"], '
             'params_AbusePreventionHelper = [1792814899847,"tok.en789",'
             '3600000], '
             'data-iid="translator.5023" data-iid="translator.5026"')
PROMT_HTML = ('<input id="_paft" type="hidden" value="PAFT-VALUE-1">'
              '<input id="_xsrf" type="hidden" value="PAGE-XSRF-1">')


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
    ck("bing key scraped (the expiry timestamp, not the TTL)",
       s.get("key") == "1792814899847", repr(s.get("key")))
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

# --- Baidu: the page markers the image names, token:/gtk = -------------
# .rdata holds "http://fanyi.baidu.com", "BAIDUID" and the two page-side
# markers 'token: ' and 'gtk = ' (tests/regress_session_markers.py). The
# port read Options.BaiduGtk/BaiduToken but had nothing that FILLED them,
# so every Baidu request signed with the default 0.0 seed.
BAIDU_HTML = ("<script>var token: 'TOK-123', gtk = '320305.131321201';"
              "</script>")


def _baidu():
    return _Resp(BAIDU_HTML, ["BAIDUID=BFEED-1; path=/",
                              "_EDGE_S=x; path=/"])


S._net_open = lambda req, opener=None, data=None: _baidu()
try:
    b = S.baidu_session()
    ck("baidu token scraped from the page marker", b.get("token") == "TOK-123",
       repr(b.get("token")))
    ck("baidu gtk scraped from the page marker",
       b.get("gtk") == "320305.131321201", repr(b.get("gtk")))
    ck("baidu cookie kept (BAIDUID)",
       "BAIDUID=BFEED-1" in b.get("cookie", ""), repr(b.get("cookie")))
    ck("baidu keeps the opener for the translate call",
       b.get("opener") is not None)
finally:
    S._net_open = _orig_net


def _baidu_empty():
    return _Resp("<html>no markers</html>", [])


S._net_open = lambda req, opener=None, data=None: _baidu_empty()
try:
    b2 = S.baidu_session()
    ck("baidu without markers yields empty fields, not a crash",
       b2.get("token") == "" and b2.get("gtk") == "", repr(b2))
finally:
    S._net_open = _orig_net

# --- the helper-array slot order, and the Options seeds ----------------
# The array native's page carries is [IG:"<ig>","<token>",<key>] -- the
# token is the QUOTED member and the key the trailing NUMBER. This port
# used to assign key=group(1) (the IG itself) and token=group(2), which
# the old fixture hid by putting its numbers in the token slot.
_orig = S._net_open
S._net_open = lambda req, opener=None, data=None: _bing()
try:
    s3 = S.bing_session()
    ck("bing token comes from the quoted member",
       s3.get("token") == "tok.en789", repr(s3.get("token")))
    ck("bing key comes from the leading expiry timestamp",
       s3.get("key") == "1792814899847", repr(s3.get("key")))
    ck("bing key is not the IG", s3.get("key") != s3.get("IG"),
       repr(s3.get("key")))
finally:
    S._net_open = _orig

# Microsoft honours BingToken/BingKey/BingCookie from Options like every
# other provider honours its own (Baidu: Baidu*; Promt: Promt*; Google:
# GoogleTkk). Without it a saved session was ignored and re-scraped.
try:
    from qtranslate import common as _Cm
    from qtranslate.services import microsoft as _Ms
    _Cm.add_option("BingToken", "SEED-TOKEN")
    _Cm.add_option("BingKey", "777")
    _Cm.add_option("BingCookie", "SEED=1")
    _i, _t, _k, _c = _Ms._seed("", "", "", "")
    ck("microsoft reads BingToken from Options", _t == "SEED-TOKEN",
       repr(_t))
    ck("microsoft reads BingKey from Options", _k == "777", repr(_k))
    ck("microsoft reads BingCookie from Options", _c == "SEED=1", repr(_c))
    _i2, _t2, _k2, _c2 = _Ms._seed("XIG", "XTOK", "XKEY", "XC")
    ck("an explicit argument still wins over the seed",
       (_t2, _k2, _c2) == ("XTOK", "XKEY", "XC"),
       repr((_t2, _k2, _c2)))
except Exception as _e:  # pragma: no cover - import guard
    ck("microsoft Options seed import", False, repr(_e))

if fails:
    print("FAIL %d" % len(fails))
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("regress_session: all checks ok (%d assertions)" % n[0])
