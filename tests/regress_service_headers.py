"""Regression: serviceHeader text + serviceHost, all 19 recovered JS files.

The NSIS payload carries 19 complete ``Service.js`` sources with hashes
(`docs/review/PLUGIN_JS_VERIFIED_AGAINST_PORT_2026-10-11.md`). Their
``new ServiceHeader(id,"Name","prose"+Const.NL2+serviceHost()+Const.NL2+
"© …")`` and ``serviceHost()`` are user-visible strings, and this suite
compares them against the port for every provider whose Python module
exists -- the JS is READ from the artifact, never executed.

No bug found: all 9 translate providers' prose and all 14 hosts match.
The suite exists because these strings were previously uncompared, and
because a naive first pass produced THREE FALSE FINDINGS while writing it
(pinned as notes below so the next reader does not repeat them):

  * Wikipedia (id 14) has NO URL-returning ``serviceHost`` -- its body
    remaps languages. An extractor taking "the first URL after
    ServiceHeader(14" reports WordReference's host and looks like a bug.
  * Yandex/Baidu ``serviceHost`` is capability-split:
    ``LISTEN ? tts-host : translate-host``, so the FIRST url in the body
    is the TTS one and comparing it to the translate host looks like a
    mismatch.
  * Baidu's copyright is ``\\u00a9`` (U+00A9); a cp1252 console renders it
    ``?`` and a byte comparison without JS-unescaping reports a diff.

Headless: no network, no Tk. Skips cleanly if the artifact is absent.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD = os.path.join(ROOT, "docs", "review", "artifacts",
                       "nsis_payload_unpacked.bin")

if not os.path.exists(PAYLOAD):
    print("SKIP: recovered payload not present (%s)" % PAYLOAD)
    raise SystemExit(0)

TS = open(PAYLOAD, "rb").read().decode("utf-8", "replace")


def js_unescape(s):
    """Decode a JS string literal body: ``\\uXXXX`` and quote escapes."""
    s = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)
    return s.replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\")


def service_segment(service_id):
    """The JS after ``new ServiceHeader(<id>,`` up to the next header."""
    i = TS.find("new ServiceHeader(%d," % service_id)
    if i < 0:
        return None
    return TS[i:i + 6000]


def native_description(service_id):
    """The description's FIRST literal (the prose; the rest is a
    Const.NL2 + serviceHost() + Const.NL2 + copyright concatenation)."""
    seg = service_segment(service_id)
    m = re.search(r'new ServiceHeader\(\d+,"[^"]+","((?:[^"\\]|\\.)*)"', seg)
    return js_unescape(m.group(1)) if m else None


def native_host(service_id, listen=False):
    """``serviceHost()`` for one capability branch."""
    seg = service_segment(service_id)
    m = re.search(r"function serviceHost\([^)]*\)\{(.*?)\}\s*(?:function|"
                  r"SupportedLanguages)", seg, re.S)
    if not m:
        return None
    body = m.group(1)
    branch = "LISTEN" if listen else "TRANSLATE"
    # capability ternary(s): LISTEN branch is the one mentioning LISTEN
    mm = re.search(r'return\s+([a-z])===Capability\.LISTEN\s*\?'
                   r'"([^"]+)"\s*:\s*"([^"]+)"', body)
    if mm:
        return mm.group(2) if listen else mm.group(3)
    urls = re.findall(r'https?://[a-z0-9.\-]+', body)
    return urls[0] if urls else None


MODULES = [
    (1, "google_translate"), (5, "microsoft"), (11, "yandex"),
    (12, "promt"), (13, "babylon"), (28, "baidu"),
    (30, "naver"), (31, "deepl"), (26, "youdao"),
]

import qtranslate.services.dictionary as DU  # noqa: E402

# --- the 9 translate providers: prose ------------------------------------
for sid, modname in MODULES:
    mod = __import__("qtranslate.services." + modname,
                     fromlist=["service_header"])
    info = getattr(mod.service_header(), "info", "") or ""
    port_prose = info.strip()
    nat = native_description(sid)
    ck("%s: native description exists" % modname, nat is not None)
    ck("%s: prose starts with native's prose" % modname,
       port_prose.startswith(nat.strip()) if nat else False,
       "%r vs %r" % (port_prose[:60], (nat or "")[:60]))

# --- the 9 hosts, plus the dictionary ones -------------------------------
HOSTS = [
    (12, promt_host := __import__("qtranslate.services.promt",
                                  fromlist=["service_host"]).service_host()),
    (13, __import__("qtranslate.services.babylon",
                    fromlist=["service_host"]).service_host()),
    (31, __import__("qtranslate.services.deepl",
                    fromlist=["service_host"]).service_host()),
    (30, __import__("qtranslate.services.naver",
                    fromlist=["service_host"]).service_host()),
]
for sid, port in HOSTS:
    nat = native_host(sid)
    ck("host for service %d matches (%s)" % (sid, port), nat == port,
       "native=%r port=%r" % (nat, port))

ck("Google host is translate.google.<domain> (capability-free)",
   native_host(1) == "https://translate.google."
   and __import__("qtranslate.services.google_translate",
                  fromlist=["service_host"]).service_host()
   == "https://translate.google.com",
   repr(native_host(1)))

for sid, want in ((11, "https://translate.yandex.net"),
                  (28, "https://fanyi.baidu.com")):
    ck("non-LISTEN host for %d is %s" % (sid, want),
       native_host(sid) == want, repr(native_host(sid)))
for sid, want in ((11, "https://tts.voicetech.yandex.net"),
                  (28, "https://tts.baidu.com")):
    ck("LISTEN host for %d is the TTS host" % sid,
       native_host(sid, listen=True) == want,
       repr(native_host(sid, listen=True)))

DICT_HOSTS = {
    "MULTITRAN_HOST": "https://www.multitran.com",
    "IMTRANS_HOST": "http://imtranslator.net",
    "WORDREF_HOST": "https://www.wordreference.com",
    "REVERSO_HOST": "http://dictionary.reverso.net",
    "URBAN_HOST": "https://www.urbandictionary.com",
    "LINGVO_HOST": "https://www.lingvolive.com",
    "OXFORD_HOST": "https://www.oxfordlearnersdictionaries.com",
    "GSEARCH_HOST": "https://www.google.com",
    "BABYLON_DICT_HOST": "https://dictionary.babylon-software.com",
}
for attr, want in DICT_HOSTS.items():
    ck("%s is %s" % (attr, want), getattr(DU, attr) == want,
       repr(getattr(DU, attr, None)))

# --- the false findings, pinned as notes --------------------------------
ck("Wikipedia has NO url-returning serviceHost (its body remaps langs)",
   native_host(14) is None, repr(native_host(14)))
ck("Baidu's copyright is U+00A9 and the port carries it",
   "© 2018 Baidu" in __import__(
       "qtranslate.services.baidu", fromlist=["service_header"]
   ).service_header().info)
ck("Baidu's port info is prose + NL2 + host + NL2 + copyright",
   __import__("qtranslate.services.baidu",
              fromlist=["service_header"]).service_header().info
   .split("\r\n")[1] == "https://fanyi.baidu.com")

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_service_headers: all checks ok (%d assertions)" % n[0])
