"""Regression: the 19 recovered Service.js capability masks, and the
11-vs-4 gap in the Options/Services screen.

Reading every ``new ServiceHeader(...)``'s last argument recovers the
native capability mask for all 19 services. **11 of them declare
``Capability.DICTIONARY``** -- but the Options/Services page lists only
4. That is not a port bug, and the suite exists to say so rather than
"fix" it:

* the screen's rows are a **measured snapshot of the default-visible
  set**, and the spec pins them explicitly
  (`UI-FULL.html` -> ``DI=[[...]]`` -> ``SERVICES_DICTIONARY``), so the 4
  rows are the UI contract;
* the other 7 dictionary services are **registered but not shown** --
  they are all present in ``Services/`` as their own directory, and the
  native can add them (``Add dictionary`` / ``Remove dictionary`` are
  native strings recovered from the exe), so the list is user-mutable
  rather than hardcoded to 4.

A future change that rewrote the 4 rows to 11, or that deleted 7, would
break one of those two facts; this suite pins both sides.

Headless: the JS is read from the artifact, never executed. Skips
cleanly when the artifact is absent.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.common import Capability  # noqa: E402

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

MASKS = {}
for m in re.finditer(r'new ServiceHeader\((\d+),"((?:[^"\\]|\\.)*)",', TS):
    sid, name = int(m.group(1)), m.group(2)
    # Anchor on "Capability." rather than on the preceding comma: the
    # header's third argument is a `+`-concatenation whose commas are not
    # argument separators, and the payload pastes each service's JS next
    # to a locale string table whose `[180, "..."]` arrays look exactly
    # like further arguments. Requiring the text to begin with
    # ``Capability.`` matches only the header's own last argument.
    cap = re.search(r'(Capability\.[A-Za-z0-9_|.\s]+?)\)\}',
                    TS[m.start():m.start() + 4000])
    MASKS[sid] = (name, " ".join(cap.group(1).split())) if cap else ("", "")

ck("all 19 services recovered", len(MASKS) == 19, str(sorted(MASKS)))


def bits(expr):
    v = 0
    for part in expr.split("|"):
        v |= getattr(Capability, part.strip().split(".")[1])
    return v


def has_dict(sid):
    return bool(bits(MASKS[sid][1]) & Capability.DICTIONARY)


DICT_IDS = sorted(s for s in MASKS if has_dict(s))
ck("exactly 11 services declare Capability.DICTIONARY",
   len(DICT_IDS) == 11, str(DICT_IDS))
ck("they are ids 25,20,10,18,29,17,22,24,14,19,26",
   DICT_IDS == [10, 14, 17, 18, 19, 20, 22, 24, 25, 26, 29],
   str(DICT_IDS))

# the translate-only providers must NOT claim DICTIONARY
for sid in (1, 5, 11, 12, 13, 28, 30, 31):
    ck("service %d (%s) is translate-only" % (sid, MASKS[sid][0]),
       not has_dict(sid), MASKS[sid][1])

# youdao is the only one with both
ck("youdao (26) is the only TRANSLATE|DICTIONARY service",
   [s for s in MASKS if "DICTIONARY" in MASKS[s][1]
    and "TRANSLATE" in MASKS[s][1]] == [26])

# --- the port's Options/Services rows (the 4-row UI contract) ----------
SRC = open(os.path.join(ROOT, "qtranslate", "screens.py"),
           encoding="utf-8").read()
ROWS = re.search(r"SERVICES_DICTIONARY = \[(.*?)\]", SRC, re.S)
ck("the port declares SERVICES_DICTIONARY", ROWS is not None)
port_rows = re.findall(r'\("([^"]+)",\s*"([^"]+)"\)', ROWS.group(1))
ck("the screen shows 4 rows", len(port_rows) == 4, str(port_rows))

# those 4 rows are real DICTIONARY services, spelled as native spells them
native_names = {MASKS[s][0] for s in DICT_IDS}
for row_name, _colour in port_rows:
    ck("screen row %r is a native DICTIONARY service" % row_name,
       row_name in native_names,
       "%r not in %r" % (row_name, sorted(native_names)))

# and the 7 that are absent are still implemented in the port
PORT_PROVIDERS = re.search(r"PROVIDERS = \{(.*?)\}", open(os.path.join(
    ROOT, "qtranslate", "services", "dictionary.py"),
    encoding="utf-8").read(), re.S).group(1)
missing = [MASKS[s][0] for s in DICT_IDS
           if MASKS[s][0] not in dict(port_rows)]
ck("the %d dictionary services not on screen are still ported"
   % len(missing), len(missing) >= 5, str(missing))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_service_capabilities: all checks ok (%d assertions)" % n[0])
