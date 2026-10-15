"""Regression: dictionary request URIs, and which services even have a ``buildUri``.

The 19 recovered ``Service.js`` files build their dictionary request in
``serviceDictionaryRequest``, which either delegates to ``buildUri`` or
carries its own literal. **Only 7 of 19 services have a ``buildUri``**
(ids 25, 10, 17, 22, 14, 19, 26) -- a fact established by mapping every
``function buildUri(`` position to its owning ``ServiceHeader`` in the
payload, not by windowing.

That mapping matters: a first pass windowed a fixed 4000 bytes after each
header and produced THREE FALSE FINDINGS, all pinned here so they are not
repeated:

  1. "Urban Dictionary's buildUri is ``/wiki/<word>``" -- the ``/wiki/``
     literal belongs to **Wikipedia (id 14)**. Urban has no ``buildUri``
     at all; its request is the inline ``/define.php?term=``.
  2. "ImTranslator has Multitran's ``/m.exe?...``" -- the window bled
     into the neighbouring service. ImTranslator has no ``buildUri``; its
     request is its own
     ``/translation/dictionary/DicService.asmx/lookup?…`` literal.
  3. "Yandex/Baidu hosts mismatch" -- those come from
     ``serviceHost``'s LISTEN ternary, unrelated here.

Verified: every inline request literal matches the port byte-for-byte.
Headless -- the JS is read, never executed. Skips if the artifact is
absent.
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

# --- which service each position belongs to (no windowing) ---------------
HEADS = [(m.start(), int(m.group(1)))
         for m in re.finditer(r'new ServiceHeader\((\d+),', TS)]


def owner_of(pos):
    prev = [h for h in HEADS if h[0] < pos]
    return prev[-1][1] if prev else None


HAVE_BUILD_URI = sorted({owner_of(m.start())
                         for m in re.finditer(r"function buildUri\(", TS)})
ck("exactly 7 services declare a buildUri", len(HAVE_BUILD_URI) == 7,
   str(HAVE_BUILD_URI))
ck("they are ids 25,10,17,22,14,19,26",
   HAVE_BUILD_URI == [10, 14, 17, 19, 22, 25, 26], str(HAVE_BUILD_URI))


def segment(service_id):
    """This service's JS only, cut at the NEXT header."""
    i = TS.find("new ServiceHeader(%d," % service_id)
    if i < 0:
        return ""
    rest = [h[0] for h in HEADS if h[0] > i]
    end = rest[0] if rest else len(TS)
    return TS[i:end]


def build_uri(service_id):
    m = re.search(r"function buildUri\([^)]*\)\{return\s*(.{0,130})",
                  segment(service_id), re.S)
    return m.group(1).strip() if m else None


def request_literal(service_id):
    """The request's own path literal; None when it delegates to buildUri."""
    seg = segment(service_id)
    m = re.search(r"function serviceDictionaryRequest\([^)]*\)"
                  r"\{(.{0,240})", seg, re.S)
    body = m.group(1) if m else ""
    if "buildUri(" in body:
        return None
    lit = re.search(r'"((?:/[^"]{4,140})|\?[^"]{4,140})"', body)
    return lit.group(1) if lit else None


# --- false finding 1 & 2, pinned ----------------------------------------
ck("Urban (24) has NO buildUri -- the /wiki/ one is Wikipedia's",
   build_uri(24) is None, repr(build_uri(24)))
ck("Wikipedia (14) is the service whose buildUri is /wiki/<word>",
   build_uri(14) is not None and "/wiki/" in build_uri(14),
   repr(build_uri(14)))
ck("Urban's REQUEST literal is /define.php?term=",
   request_literal(24) == "/define.php?term=", repr(request_literal(24)))
ck("ImTranslator (18) has NO buildUri",
   build_uri(18) is None, repr(build_uri(18)))
ck("ImTranslator's REQUEST is its own lookup literal",
   (request_literal(18) or "").startswith("/translation/dictionary/"),
   repr(request_literal(18)))
ck("Oxford (29) has NO buildUri either", build_uri(29) is None)
ck("Oxford's REQUEST literal is /search/english/?q=",
   request_literal(29) == "/search/english/?q=", repr(request_literal(29)))

# --- the delegating services really do delegate --------------------------
for sid in HAVE_BUILD_URI:
    ck("service %d delegates its request to buildUri" % sid,
       request_literal(sid) is None,
       "literal=%r" % request_literal(sid))

# --- buildUri shapes the port must reproduce ----------------------------
def shape(sid, needle):
    got = build_uri(sid)
    return got is not None and needle in got.replace(" ", "")


ck("WordReference (19) buildUri is /{src}{tgt}/{word}",
   shape(19, '"/{0}{1}/{2}"'), repr(build_uri(19)))
ck("Reverso (22) buildUri is /{src}-{tgt}/{word}",
   shape(22, '"/{0}-{1}/{2}"'), repr(build_uri(22)))
ck("Google Search (10) buildUri is /search?q=…&ie=UTF-8&hl=…",
   shape(10, "/search?q={0}"), repr(build_uri(10)))

# --- the port's literals, byte for byte --------------------------------
SRC = open(os.path.join(ROOT, "qtranslate", "services", "dictionary.py"),
           encoding="utf-8").read()
ck("the port's Urban request literal is verbatim",
   '"/define.php?term="' in SRC)
ck("the port's Oxford request literal is verbatim",
   "/search/english/?q=" in SRC)
IMTRANS_HEAD = "/translation/dictionary/DicService.asmx/lookup"
IMTRANS_TAIL = ("?text={0}&dicID=&lang={1}%2F{2}"
                "&langs={1}%2F{2}&flags=DEFAULT")
ck("the port's ImTranslator request carries native's path",
   IMTRANS_HEAD in SRC)
ck("...and native's query verbatim, %2F separators included",
   IMTRANS_TAIL in SRC)
ck("the two halves are ADJACENT string constants (one literal, not two "
   "requests)",
   IMTRANS_HEAD + '"\n' in SRC
   or (SRC.find(IMTRANS_HEAD) < SRC.find(IMTRANS_TAIL)
       < SRC.find(IMTRANS_HEAD) + len(IMTRANS_HEAD) + 60),
   "the halves are far apart")

# --- the port's own helpers exist for the delegating services ----------
import qtranslate.services.dictionary as DU  # noqa: E402

for fn in ("multitran_build_uri", "reverso_build_uri",
           "gsearch_build_uri", "lingvo_build_uri"):
    ck("port has %s" % fn, hasattr(DU, fn))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_dict_request_uri: all checks ok (%d assertions)" % n[0])
