"""Regression: the payload DOES carry the dictionary hosts the sweep called absent.

`ENDPOINT_SWEEP_2026-10-14.md` §"Dictionary placement" measured 0 hits for
nine dictionary hostnames, which was correct **for the exe** — then drew a
wrong conclusion from it: *"the JS plugin files that the recovered artifact
does not contain"*. It does contain them. `nsis_payload_unpacked.bin` carries
all 19 `Service.js` files, and eight of the nine hostnames appear in them.

Only `merriam` is genuinely absent from both artifacts. (It is also absent
from the 19 services: there is no Merriam-Webster plugin in 6.10.0.)

This suite pins the counts so the claim cannot silently become wrong
again in either direction -- and so a future reader who hits "0 hits"
in the sweep can tell immediately that it was an exe-only measurement.

Headless; both artifacts are read, never executed. Skips if absent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append("%s -- %s" % (name, detail) if detail else name)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD = os.path.join(ROOT, "docs", "review", "artifacts",
                       "nsis_payload_unpacked.bin")
EXE = os.path.join(ROOT, "docs", "review", "artifacts",
                   "QTranslate.6.10.0.exe")

# (hostname, times in the payload, times in the exe)
HOSTS = [
    ("multitran", 2),
    ("oxfordlearnersdictionaries", 2),
    ("reverso.net", 2),
    ("imtranslator", 2),
    ("wikipedia", 3),
    ("wordreference", 1),
    ("lingvolive", 1),
    ("urbandictionary", 1),
    # the only one absent from both -- and there is no such plugin
    ("merriam", 0),
]

if not os.path.exists(PAYLOAD):
    print("SKIP: recovered payload not present")
    raise SystemExit(0)

TS = open(PAYLOAD, "rb").read().decode("utf-8", "replace")

for host, want in HOSTS:
    got = TS.count(host)
    ck("payload carries %r %d time(s)" % (host, want), got == want,
       "found %d" % got)

# --- the sweep's exe-side numbers were right ---------------------------
if os.path.exists(EXE):
    img = open(EXE, "rb").read()
    for host, _ in HOSTS:
        ck("the exe genuinely has 0 %r (the sweep's number was right)" % host,
           img.count(host.encode("ascii")) == 0,
           str(img.count(host.encode("ascii"))))
    ck("the exe's only dictionary strings are local-XDXF ones (UTF-16)",
       img.count("XdxfArticle.xslt".encode("utf-16-le")) == 1
       and img.count("XDXF".encode("utf-16-le")) >= 1)
else:
    ck("the exe is available to check the sweep's half", False,
       "artifact missing")

# --- the hosts sit inside the 19 Service.js files, not loose in the pad -
# A host that appeared only once, outside any service header, would be a
# fluke; every one of these should be inside the block its ServiceHeader
# begins.
import re  # noqa: E402

HEADS = [m.start() for m in re.finditer(r'new ServiceHeader\((\d+),', TS)]
ck("the payload has 19 service headers", len(HEADS) == 19, str(len(HEADS)))


def owner_of(host):
    i = TS.find(host)
    if i < 0:
        return None
    prev = [h for h in HEADS if h < i]
    return int(re.search(r'new ServiceHeader\((\d+),',
                         TS[prev[-1]:]).group(1)) if prev else None


EXPECTED_OWNER = {
    "multitran": 17,
    "wordreference": 19,
    "lingvolive": 25,
    "oxfordlearnersdictionaries": 29,
    "urbandictionary": 24,
    "reverso.net": 22,
    "wikipedia": 14,
    "imtranslator": 18,
}
for host, sid in EXPECTED_OWNER.items():
    ck("%r's first occurrence is inside service %d's block"
       % (host, sid), owner_of(host) == sid, "owner=%r" % owner_of(host))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail[:15]:
        print("  -", f)
    raise SystemExit(1)
print("regress_payload_dict_hosts: all checks ok (%d assertions)" % n[0])
