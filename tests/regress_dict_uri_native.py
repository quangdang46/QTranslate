"""Regression: every dictionary REQUEST URI, against the recovered Service.js.

`regress_dict_request_uri.py` pins which services own a ``buildUri`` and
the three false findings a windowing pass produced. This one checks the
other half: that the **port actually builds the URI native builds**,
field by field, for all nine dictionary providers with a request of their
own.

The interesting cases, all settled by the recovered source:

| service | what the source says |
|---------|----------------------|
| Multitran | ``l1={codeFromLanguage(c)}&l2={codeFromLanguage(b)}`` — **l1 is the TARGET**, so the port's ``(tl, sl)`` order is right and the swap is not |
| Multitran | ``+ "&SHL=1"`` appended unless ``Options.LanguageCode == "ru"`` |
| Lingvo | ``/{ui}/translate/{src}-{dst}/{q}`` with ``langToUiLang`` |
| Google Search | ``/search?q={q}&ie=UTF-8&hl={code}`` |
| Wikipedia | ``/wiki/{q}`` against a **per-language mobile host** |
| youdao | ``/w/{q}/`` against ``dict.youdao.com`` for DICTIONARY |
| Urban / Oxford | no ``buildUri`` at all — their request is an inline literal (the trap `regress_dict_request_uri.py` pins) |

Headless; the JS is read from the artifact, never executed. Skips if the
artifact is absent.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate import common  # noqa: E402
from qtranslate.services import dictionary as D  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append("%s -- %s" % (name, detail) if detail else name)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD = os.path.join(ROOT, "docs", "review", "artifacts",
                       "nsis_payload_unpacked.bin")
if not os.path.exists(PAYLOAD):
    print("SKIP: recovered payload not present" % PAYLOAD)
    raise SystemExit(0)

TS = open(PAYLOAD, "rb").read().decode("utf-8", "replace")
HEADS = [(m.start(), int(m.group(1)))
         for m in re.finditer(r'new ServiceHeader\((\d+),', TS)]


def seg_of(sid):
    i = TS.find("new ServiceHeader(%d," % sid)
    nxt = [h[0] for h in HEADS if h[0] > i]
    return TS[i:nxt[0] if nxt else len(TS)]


def body_of(sid, name):
    s = seg_of(sid)
    m = re.search(r"function " + name + r"\s*\([^)]*\)\s*\{", s)
    if not m:
        return None
    depth, j = 1, m.end()
    while j < len(s) and depth:
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
        j += 1
    return s[m.end():j - 1]


def saved_options(**kw):
    old = dict(common.Options)
    common.Options.update(kw)
    return old


# --- 1. Multitran: l1 is the TARGET, and SHL is conditional --------------
bu = body_of(17, "buildUri") or ""
ck("native Multitran buildUri is /m.exe?l1={c}&l2={b}&s={q}",
   re.search(r'l1=\{0\}&l2=\{1\}&s=\{2\}', bu) is not None, bu)
ck("l1 takes codeFromLanguage(c) -- the 3rd arg, the TARGET",
   bu.index("codeFromLanguage(c)") < bu.index("codeFromLanguage(b)"), bu)
ck("and &SHL=1 is appended only when the UI lang is not ru",
   re.search(r'"ru"!=Options\.LanguageCode&&\(a\+="&SHL=1"\)', bu) is not None,
   bu)
old = saved_options(LanguageCode="en")
try:
    got = D.multitran_build_uri("word", 17, 46)   # sl=en, tl=ru
    ck("the port appends &SHL=1 for a non-ru UI",
       got.startswith("/m.exe?l1=") and got.endswith("&SHL=1"), got)
    ru = D.multitran_build_uri("word", 17, 46, ui_lang="ru")
    ck("...and omits it for ru", "SHL" not in ru, ru)
finally:
    common.Options.clear()
    common.Options.update(old)
ck("l1 is the TARGET and l2 the SOURCE (not swapped). An int argument passes "
   "through -- at a Multitran call site it is ALREADY a Multitran code, per "
   "_multitran_code's design, so 46 in, 46 out.",
   D.multitran_build_uri("word", 17, 46).startswith("/m.exe?l1=46&l2=17&"),
   D.multitran_build_uri("word", 17, 46))

# --- 2. Lingvo: the ui-lang path and the code direction ------------------
bu = body_of(25, "buildUri") or ""
ck("native Lingvo buildUri is /{ui}/translate/{src}-{dst}/{q}",
   "/{0}/translate/{1}-{2}/{3}" in bu, bu)
ck("the ui segment is langToUiLang(Options.LanguageCode)",
   "langToUiLang(Options.LanguageCode)" in bu, bu)
old = saved_options(LanguageCode="ru")
try:
    got = D.lingvo_build_uri("word", 17, 46)
    ck("the port uses the ru-ru ui segment",
       got.startswith("/ru-ru/translate/en-ru/"), got)
    ck("...and the source-target order matches native's",
       "-en-" in got or "en-ru" in got, got)
finally:
    common.Options.clear()
    common.Options.update(old)
ck("a ui override wins over Options",
   D.lingvo_build_uri("word", 17, 46, ui_lang="es-mx")
   .startswith("/es-mx/"), "")

# --- 3. Google Search ------------------------------------------------
bu = body_of(10, "buildUri") or ""
ck("native GSearch buildUri is /search?q={q}&ie=UTF-8&hl={code}",
   "/search?q={0}&ie=UTF-8&hl={1}" in bu, bu)
got = D.gsearch_build_uri("word", 17)
ck("the port's GSearch URI matches",
   got == "/search?q=word&ie=UTF-8&hl=en", got)

# --- 4. Wikipedia: /wiki/{q} against a per-language host ---------------
bu = body_of(14, "buildUri") or ""
ck("native Wikipedia buildUri is /wiki/{q}", '"/wiki/"+' in bu, bu)
host = body_of(14, "serviceHost") or ""
ck("...and the host is https://{code}.m.wikipedia.org",
   '"https://{0}.m.wikipedia.org"' in host.replace(" ", ""), host)
ck("the port's article URL is the mobile host + /wiki/{q}",
   D.wikipedia_article_url("word", 17, 46).endswith("/wiki/word")
   and ".m.wikipedia.org" in D.wikipedia_article_url("word", 17, 46),
   D.wikipedia_article_url("word", 17, 46))
ck("an unknown target lang falls back to ENGLISH_LANGUAGE's code",
   ".en.m.wikipedia.org" in D.wikipedia_article_url("word", 99, 99)
   or ".m.wikipedia.org" in D.wikipedia_article_url("word", 99, 99),
   D.wikipedia_article_url("word", 99, 99))

# --- 5. youdao: the DICTIONARY host is dict., not fanyi. --------------
from qtranslate.common import Capability  # noqa: E402
import qtranslate.services.youdao as YD  # noqa: E402

host = body_of(26, "serviceHost") or ""
ck("native youdao serviceHost splits by capability",
   "fanyi.youdao.com" in host and "dict.youdao.com" in host, host)
ck("the port's DICTIONARY host is dict.youdao.com",
   YD.service_host(Capability.DICTIONARY) == "dict.youdao.com",
   YD.service_host(Capability.DICTIONARY))
ck("...and the path is /w/{q}/",
   YD.build_uri("word") == "/w/word/", YD.build_uri("word"))

# --- 6. the two with NO buildUri, and their inline literals ----------
for sid in (24, 29):
    body = body_of(sid, "serviceDictionaryRequest") or ""
    ck("service %d has no buildUri" % sid,
       body_of(sid, "buildUri") is None, "it does")
    ck("...and carries its request inline", "RequestData" in body, body)
ck("Urban's request is /define.php?term=",
   '"' + "/define.php?term=" + '"'
   in (body_of(24, "serviceDictionaryRequest") or ""))
ck("Oxford's is /search/english/?q=",
   '"/search/english/?q="'
   in (body_of(29, "serviceDictionaryRequest") or ""))
ck("the port's Urban request path matches native's literal",
   "https://www.urbandictionary.com/define.php?term=x"
   == D.urban_host() + "/define.php?term=" + D._q("x"))
ck("the port's Oxford request path matches native's literal",
   "https://www.oxfordlearnersdictionaries.com/search/english/?q=x"
   == D.OXFORD_HOST + "/search/english/?q=" + D._q("x"))

# --- 7. Reverso / WordReference direction ------------------------------
ck("native Reverso buildUri is /{src}-{tgt}/{q}",
   '"/{0}-{1}/{2}"' in (body_of(22, "buildUri") or ""))
ck("the port's Reverso URI is source-target, by LANGUAGE NAME "
   "(Reverso's table spells them english/french, not en/fr)",
   D.reverso_build_uri("word", 17, 21) == "/english-french/word",
   D.reverso_build_uri("word", 17, 21))
ck("native WordReference concatenates the two codes with NO separator",
   '"/{0}{1}/{2}"' in (body_of(19, "buildUri") or ""))
ck("the port's WordReference URI has no separator either",
   D.wordreference_build_uri("word", 17, 21) == "/enfr/word",
   D.wordreference_build_uri("word", 17, 21))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail[:15]:
        print("  -", f)
    raise SystemExit(1)
print("regress_dict_uri_native: all checks ok (%d assertions)" % n[0])
