"""Regression: every dictionary service consults ITS OWN language table.

The recovered `Services/*/Service.js` sources each declare a
`SupportedLanguages` array indexed by the app's shared language id, and
each dictionary request builder resolves the language through it. Native's
framework helper (`Common.js`, chunk[5] of the NSIS stream) is::

    function isLanguage(a){return a>AUTO_DETECT_LANGUAGE&&
                                a<SupportedLanguages.length}
    function codeFromLanguage(a){return a===AUTO_DETECT_LANGUAGE||isLanguage(a)
                                    ?SupportedLanguages[a]:UNKNOWN_LANGUAGE_CODE}

The entry is returned **unguarded** -- the index is tested, never the value
-- so an unsupported language interpolates as ``-1`` and native still sends
the request. There is no refusal path anywhere in the framework, so a port
that "skips the service" would be inventing policy the artifact does not
have. What the artifact does have is the table, and the table has to be
read: a service that never consults it sends the wrong code (Babylon's
numeric pair, Google's ``kz`` for Kazakh) or none at all.

THIS IS A BEHAVIOUR TEST. Every check below calls the port's real
lookup/builder/dispatch and asserts on the URL or request body it
actually produced. The native side is read out of the installer payload
(the chunk chain, not a filename search -- the payload stores bodies
positionally with no filename field), and the expected value is computed
from native's OWN table by a transcription of native's OWN
`codeFromLanguage`. Nothing here greps the port's source for a name.

Headless: the network is stubbed at `session._net_open`, the lowest point
the port's HTTP path goes through.
"""
import hashlib
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import registry                      # noqa: E402
from qtranslate.services import dictionary as D      # noqa: E402
from qtranslate.services import babylon as B         # noqa: E402
from qtranslate.services.google_translate import (   # noqa: E402
    SUPPORTED_LANGS as APP_LANGS)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD = os.path.join(ROOT, "docs", "review", "artifacts",
                       "nsis_payload_unpacked.bin")

# ---------------------------------------------------------------- evidence

if not os.path.exists(PAYLOAD):
    print("SKIP: recovered payload not present (%s)" % PAYLOAD)
    raise SystemExit(0)

_raw = open(PAYLOAD, "rb").read()


def walk_chunks(blob):
    """The payload is a chain of ``<uint32-LE length><body>`` records.

    Filenames are NOT in the stream -- a file is found by walking the
    chain or by matching a content marker, never by searching for its
    name.
    """
    out, off = [], 0
    while off + 4 <= len(blob):
        size = struct.unpack_from("<I", blob, off)[0]
        body = blob[off + 4:off + 4 + size]
        if len(body) != size:
            break
        out.append((off, body))
        off += 4 + size
    return out, off


_chunks, _consumed = walk_chunks(_raw)
ck("the payload chunk chain consumes every byte",
   _consumed == len(_raw), "%d of %d" % (_consumed, len(_raw)))
ck("the payload holds 131 chunks", len(_chunks) == 131, str(len(_chunks)))

_common = [b for _, b in _chunks if b.startswith(b"var Const={MAX_URI_LEN")]
ck("Common.js is in the chain", len(_common) == 1, str(len(_common)))
_common_js = _common[0].decode("utf-8", "replace")
ck("Common.js hashes to the recorded digest",
   hashlib.sha256(_common_js.encode("utf-8")).hexdigest()
   .startswith("a03d677a8b3788b5"),
   hashlib.sha256(_common_js.encode("utf-8")).hexdigest())
ck("Common.js carries codeFromLanguage unguarded",
   "function codeFromLanguage(a){return a===AUTO_DETECT_LANGUAGE||isLanguage(a)"
   "?SupportedLanguages[a]:UNKNOWN_LANGUAGE_CODE}" in _common_js)
ck("Common.js has no refusal path (no 'return null'/'return false')",
   "return null" not in _common_js and "return false" not in _common_js
   and "return !1" not in _common_js)

# service id -> (chunk body text, sha256)
SERVICES_JS = {}
for _off, _body in _chunks:
    if not _body.startswith(b"function serviceHeader"):
        continue
    _txt = _body.decode("utf-8", "replace")
    _m = re.search(r"new ServiceHeader\((\d+),", _txt)
    if _m:
        SERVICES_JS[int(_m.group(1))] = (
            _txt, hashlib.sha256(_body).hexdigest())
ck("all 19 Service.js files were recovered", len(SERVICES_JS) == 19,
   str(len(SERVICES_JS)))
ck("Lingvo's chunk hashes to the recorded digest",
   SERVICES_JS[25][1].startswith("4c0ef8506ff3"), SERVICES_JS[25][1])
ck("Babylon Dictionary's chunk hashes to the recorded digest",
   SERVICES_JS[20][1].startswith("f406c6fb3598"), SERVICES_JS[20][1])


def native_table(service_id):
    """That service's own ``SupportedLanguages`` array, straight from JS."""
    txt = SERVICES_JS[service_id][0]
    m = re.search(r"SupportedLanguages=\[(.*?)\];", txt, re.S)
    assert m, "no SupportedLanguages in service %d" % service_id
    return eval("[" + m.group(1) + "]")


def native_code(idx, table):
    """Common.js ``codeFromLanguage`` over the service's own table.

    A transcription of the two recovered lines, so a wrong port cannot
    make these pass.
    """
    if idx == 1 or (1 < idx < len(table)):
        return table[idx]
    return -1


# ------------------------------------------------- the port's own app index

IDX = {code: i for i, code in enumerate(APP_LANGS)}
ck("the app's language id for English is 17 (native's ENGLISH_LANGUAGE)",
   IDX.get("en") == 17, str(IDX.get("en")))
ck("the app's language id for Russian is 46",
   IDX.get("ru") == 46, str(IDX.get("ru")))

# The tables are indexed by the APP's ids, so native's entry at the app's
# id for a language is that provider's code for that language.
for _sid, _label in ((25, "Lingvo"), (20, "Babylon Dictionary"),
                     (22, "Reverso"), (19, "WordReference"),
                     (10, "Google Search"), (18, "ImTranslator"),
                     (17, "Multitran"), (14, "Wikipedia"),
                     (13, "Babylon")):
    _nat = native_table(_sid)
    ck("%s's table is indexed by the app's language ids" % _label,
       len(_nat) == 76, str(len(_nat)))

# ------------------------------------------------------------ the stub net

CAPTURED = []


class _FakeResponse:
    def __init__(self, body=b""):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def capture(fn):
    """Run ``fn`` with the network stubbed; return the URLs/bodies sent."""
    from qtranslate import session

    CAPTURED.clear()
    old = session._net_open

    def _fake(req, opener=None, data=None):
        CAPTURED.append(req)
        return _FakeResponse(b"")

    session._net_open = _fake
    try:
        out = fn()
    finally:
        session._net_open = old
    return out


def url_of(req):
    return req.full_url


def body_of(req):
    return req.data.decode("utf-8", "replace") if req.data else ""


# ==========================================================================
# 1. Google Search -- the table was bypassed for ISO codes
# ==========================================================================

nat = native_table(10)
ck("Google Search's native table entry for ru is 'ru'",
   native_code(IDX["ru"], nat) == "ru", repr(native_code(IDX["ru"], nat)))
ck("Google Search's native table entry for kk is 'kz', not 'kk'",
   native_code(IDX["kk"], nat) == "kz", repr(native_code(IDX["kk"], nat)))

ck("Google Search: an index resolves to the provider's own code",
   D.gsearch_build_uri("hello", IDX["ru"])
   == "/search?q=hello&ie=UTF-8&hl=" + native_code(IDX["ru"], nat),
   D.gsearch_build_uri("hello", IDX["ru"]))
ck("Google Search: an ISO code resolves through the SAME table",
   D.gsearch_build_uri("hello", "ru")
   == "/search?q=hello&ie=UTF-8&hl=" + native_code(IDX["ru"], nat),
   D.gsearch_build_uri("hello", "ru"))
ck("Google Search: the table's own code wins over the app's code (kk->kz)",
   D.gsearch_build_uri("hello", "kk")
   == "/search?q=hello&ie=UTF-8&hl=" + native_code(IDX["kk"], nat),
   D.gsearch_build_uri("hello", "kk"))

# consultation proof: change the table, the output must follow
_saved = D.GSEARCH_LANGS[IDX["ru"]]
D.GSEARCH_LANGS[IDX["ru"]] = "SENTINEL"
try:
    ck("Google Search: the output follows a changed table entry",
       "hl=SENTINEL" in D.gsearch_build_uri("hello", "ru"),
       D.gsearch_build_uri("hello", "ru"))
finally:
    D.GSEARCH_LANGS[IDX["ru"]] = _saved

# the dispatch path, end to end
capture(lambda: registry.DICTS["google-search"]("hello", "en", "kk"))
ck("the dict dispatch reaches Google Search with the table's code",
   len(CAPTURED) == 1 and "hl=" + native_code(IDX["kk"], nat)
   in url_of(CAPTURED[0]),
   url_of(CAPTURED[0]) if CAPTURED else "no request")

# ==========================================================================
# 2. Babylon (id 13) -- the table was never read at all
# ==========================================================================

nat = native_table(13)
ck("Babylon's native table entry for en is the number 0",
   native_code(IDX["en"], nat) == 0, repr(native_code(IDX["en"], nat)))
ck("Babylon's native table entry for ru is the number 7",
   native_code(IDX["ru"], nat) == 7, repr(native_code(IDX["ru"], nat)))

capture(lambda: D.babylon_lookup("hello", "en", "ru"))
ck("Babylon asks with its OWN numeric pair, not the raw codes",
   len(CAPTURED) == 1
   and "langpair=%s%%7C%s" % (native_code(IDX["en"], nat),
                              native_code(IDX["ru"], nat))
   in url_of(CAPTURED[0]),
   url_of(CAPTURED[0]) if CAPTURED else "no request")
ck("Babylon's request does NOT carry the raw language codes",
   len(CAPTURED) == 1 and "langpair=en%7Cru" not in url_of(CAPTURED[0]),
   url_of(CAPTURED[0]) if CAPTURED else "no request")

capture(lambda: B.translate("hello", "en", "ru"))
ck("the live Babylon translate path asks with the same numeric pair",
   len(CAPTURED) == 1
   and "langpair=%s%%7C%s" % (native_code(IDX["en"], nat),
                              native_code(IDX["ru"], nat))
   in url_of(CAPTURED[0]),
   url_of(CAPTURED[0]) if CAPTURED else "no request")

_saved = D.BABYLON_LANGS[IDX["ru"]]
D.BABYLON_LANGS[IDX["ru"]] = 4242
try:
    capture(lambda: D.babylon_lookup("hello", "en", "ru"))
    ck("Babylon: the output follows a changed table entry",
       len(CAPTURED) == 1 and "langpair=0%7C4242" in url_of(CAPTURED[0]),
       url_of(CAPTURED[0]) if CAPTURED else "no request")
finally:
    D.BABYLON_LANGS[IDX["ru"]] = _saved

# the port's own copy of Babylon's table must be native's table
_port_babylon = [-1 if v is None else v for v in D.BABYLON_LANGS]
ck("the port's BABYLON_LANGS is native's table, entry for entry",
   _port_babylon == native_table(13),
   "first difference at %s" % next(
       (i for i, (a, b) in enumerate(zip(_port_babylon, native_table(13)))
        if a != b), None))

# ==========================================================================
# 3. The services that already resolved -- still native's value
# ==========================================================================

nat = native_table(25)   # Lingvo
ck("Lingvo: the index resolves to the provider's own code",
   D.lingvo_build_uri("hello", IDX["ru"], IDX["en"], "en")
   == "/en/translate/%s-%s/hello" % (native_code(IDX["ru"], nat),
                                     native_code(IDX["en"], nat)),
   D.lingvo_build_uri("hello", IDX["ru"], IDX["en"], "en"))
ck("Lingvo: the ISO code resolves to the same thing",
   D.lingvo_build_uri("hello", "ru", "en", "en")
   == D.lingvo_build_uri("hello", IDX["ru"], IDX["en"], "en"))
_saved = D.LINGVO_LANGS[IDX["ru"]]
D.LINGVO_LANGS[IDX["ru"]] = "SENTINEL"
try:
    ck("Lingvo: the output follows a changed table entry",
       "SENTINEL" in D.lingvo_build_uri("hello", "ru", "en", "en"),
       D.lingvo_build_uri("hello", "ru", "en", "en"))
finally:
    D.LINGVO_LANGS[IDX["ru"]] = _saved

nat = native_table(22)   # Reverso
ck("Reverso: the index resolves to the provider's own code",
   D.reverso_build_uri("hello", IDX["ru"], IDX["en"])
   == "/%s-%s/hello" % (native_code(IDX["ru"], nat),
                        native_code(IDX["en"], nat)),
   D.reverso_build_uri("hello", IDX["ru"], IDX["en"]))
ck("Reverso: the ISO code resolves to the same thing",
   D.reverso_build_uri("hello", "ru", "en")
   == D.reverso_build_uri("hello", IDX["ru"], IDX["en"]))

nat = native_table(19)   # WordReference
ck("WordReference: the index resolves to the provider's own code",
   D.wordreference_build_uri("hello", IDX["ru"], IDX["en"])
   == "/%s%s/hello" % (native_code(IDX["ru"], nat),
                       native_code(IDX["en"], nat)),
   D.wordreference_build_uri("hello", IDX["ru"], IDX["en"]))
ck("WordReference: the ISO code resolves to the same thing",
   D.wordreference_build_uri("hello", "ru", "en")
   == D.wordreference_build_uri("hello", IDX["ru"], IDX["en"]))

nat = native_table(17)   # Multitran
ck("Multitran: the ISO codes resolve to the provider's own numbers",
   D.multitran_build_uri("hello", "ru", "en", "en")
   == "/m.exe?l1=%s&l2=%s&s=hello&SHL=1"
   % (native_code(IDX["en"], nat), native_code(IDX["ru"], nat)),
   D.multitran_build_uri("hello", "ru", "en", "en"))
_saved = D.MULTITRAN_LANGS[IDX["ru"]]
D.MULTITRAN_LANGS[IDX["ru"]] = 4242
try:
    ck("Multitran: the output follows a changed table entry",
       "l2=4242" in D.multitran_build_uri("hello", "ru", "en", "en"),
       D.multitran_build_uri("hello", "ru", "en", "en"))
finally:
    D.MULTITRAN_LANGS[IDX["ru"]] = _saved

nat = native_table(14)   # Wikipedia -- the TARGET leg only
ck("Wikipedia: the host resolves the target through the table",
   D.wikipedia_host_for("en", "ru")
   == "https://%s.m.wikipedia.org" % native_code(IDX["ru"], nat),
   D.wikipedia_host_for("en", "ru"))
_saved = D.WIKI_LANGS[IDX["ru"]]
D.WIKI_LANGS[IDX["ru"]] = "sentinel"
try:
    ck("Wikipedia: the output follows a changed table entry",
       "sentinel.m.wikipedia.org" in D.wikipedia_host_for("en", "ru"),
       D.wikipedia_host_for("en", "ru"))
finally:
    D.WIKI_LANGS[IDX["ru"]] = _saved

nat = native_table(20)   # Babylon Dictionary -- a POST body
capture(lambda: D.babylon_dict_lookup("hello", "ru", "en"))
ck("Babylon Dictionary: the POST body carries the provider's own codes",
   len(CAPTURED) == 1
   and "sourceLanguage=%s" % native_code(IDX["ru"], nat) in body_of(CAPTURED[0])
   and "targetLanguage=%s" % native_code(IDX["en"], nat) in body_of(CAPTURED[0]),
   body_of(CAPTURED[0]) if CAPTURED else "no request")
_saved = D.BABYLON_DICT_LANGS[IDX["ru"]]
D.BABYLON_DICT_LANGS[IDX["ru"]] = "sentinel"
try:
    capture(lambda: D.babylon_dict_lookup("hello", "ru", "en"))
    ck("Babylon Dictionary: the body follows a changed table entry",
       len(CAPTURED) == 1
       and "sourceLanguage=sentinel" in body_of(CAPTURED[0]),
       body_of(CAPTURED[0]) if CAPTURED else "no request")
finally:
    D.BABYLON_DICT_LANGS[IDX["ru"]] = _saved

nat = native_table(18)   # ImTranslator
capture(lambda: D.imtranslator_lookup("hello", "ru", "en"))
ck("ImTranslator: the query carries the provider's own codes",
   len(CAPTURED) == 1
   and "lang=%s%%2F%s" % (native_code(IDX["ru"], nat),
                          native_code(IDX["en"], nat)) in url_of(CAPTURED[0]),
   url_of(CAPTURED[0]) if CAPTURED else "no request")
_saved = D.IMTRANS_LANGS[IDX["ru"]]
D.IMTRANS_LANGS[IDX["ru"]] = "sentinel"
try:
    capture(lambda: D.imtranslator_lookup("hello", "ru", "en"))
    ck("ImTranslator: the query follows a changed table entry",
       len(CAPTURED) == 1
       and "lang=sentinel%2F" in url_of(CAPTURED[0]),
       url_of(CAPTURED[0]) if CAPTURED else "no request")
finally:
    D.IMTRANS_LANGS[IDX["ru"]] = _saved

# ==========================================================================
# 4. Native does NOT refuse an unsupported pair -- it sends -1
# ==========================================================================

nat = native_table(25)
_unsup = next(i for i in range(2, 76) if native_code(i, nat) == -1)
ck("the unsupported probe index is inside the table", 1 < _unsup < 76,
   str(_unsup))
ck("native interpolates an unsupported language as -1",
   native_code(_unsup, nat) == -1, repr(native_code(_unsup, nat)))
ck("the port interpolates an unsupported language as -1 too",
   D.lingvo_build_uri("hello", _unsup, IDX["en"], "en")
   == "/en/translate/-1-%s/hello" % native_code(IDX["en"], nat),
   D.lingvo_build_uri("hello", _unsup, IDX["en"], "en"))
capture(lambda: D.imtranslator_lookup("hello", _unsup, IDX["en"]))
ck("an unsupported pair still issues its request (native has no refusal)",
   len(CAPTURED) == 1, "no request was sent")

# ==========================================================================
# 5. Oxford and Urban: native never consults their tables, so neither
#    does the port -- and the port's table must stay unread
# ==========================================================================

for _sid, _label in ((29, "Oxford"), (24, "Urban")):
    _txt = SERVICES_JS[_sid][0]
    _req = re.search(r"function serviceDictionaryRequest\((.*?)\)\{(.*?)\}",
                     _txt, re.S)
    ck("%s: native's request builder is recovered" % _label, _req is not None)
    ck("%s: native's request builder never calls codeFromLanguage" % _label,
       _req is not None and "codeFromLanguage" not in _req.group(2),
       _req.group(2) if _req else "")

ck("Oxford: the URI carries no language at all",
   D.oxford_lookup.__doc__ is not None
   and "/search/english/?q=" in (D.oxford_lookup.__code__.co_consts[1]
                                 if len(D.oxford_lookup.__code__.co_consts) > 1
                                 else ""),
   "checked through the request below")
capture(lambda: D.oxford_lookup("hello", "ru", "en"))
ck("Oxford: the request is the language-free path native builds",
   CAPTURED
   and url_of(CAPTURED[0])
   == "https://www.oxfordlearnersdictionaries.com/search/english/?q=hello",
   url_of(CAPTURED[0]) if CAPTURED else "no request")
ck("Oxford: no request of the lookup carries a language",
   all("hl=" not in url_of(r) and "lang=" not in url_of(r) for r in CAPTURED),
   " | ".join(url_of(r) for r in CAPTURED))
capture(lambda: D.urban_lookup("hello", "ru", "en"))
ck("Urban: the request is the language-free path native builds",
   CAPTURED
   and url_of(CAPTURED[0])
   == "https://www.urbandictionary.com/define.php?term=hello",
   url_of(CAPTURED[0]) if CAPTURED else "no request")
ck("Urban: no request of the lookup carries a language",
   all("hl=" not in url_of(r) and "lang=" not in url_of(r) for r in CAPTURED),
   " | ".join(url_of(r) for r in CAPTURED))

# ==========================================================================
# 6. Every dictionary service in the dispatch table reaches a real lookup
# ==========================================================================

ck("the dispatch table has all ten dictionary services",
   len(registry.DICTS) == 11, str(sorted(registry.DICTS)))
for _name in ("google-search", "lingvo", "reverso", "wordreference",
              "babylon", "imtranslator", "multitran", "wikipedia", "urban",
              "oxford", "youdao"):
    ck("the dispatch table carries %s" % _name, _name in registry.DICTS)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_dict_lang_tables: all checks ok (%d assertions)" % n[0])
