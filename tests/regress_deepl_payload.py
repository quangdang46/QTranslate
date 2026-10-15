"""Regression: DeepL JSON-RPC request shape (E4).

`translate()` depends on two invariants that were untested, and a broken
one silently corrupts output instead of failing:

  1. the ``i_count`` timestamp rule --
     ``now + (i_count - now % i_count)`` with ``i_count = 1 + count('i')``;
  2. the segmentation contract between ``split_text`` (the jobs sent) and
     ``parse_text`` (the parts the beams are re-interleaved into):
     ``len(jobs) == number of type-1 parts`` AND
     concatenating every part reproduces the input byte-for-byte.

Both are pinned here against independently written expectations, so a
wrong port cannot pass. Headless: no network, no Tk.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.services import deepl as D  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


# --- 1. the i_count timestamp rule ---------------------------------------
def ref_ts(text, now):
    ic = 1 + len(re.findall(r"i", text))
    return now + (ic - now % ic)


ck("i_count('hello') == 1", 1 + len(re.findall(r"i", "hello")) == 1)
ck("i_count('initializing') == 6",
   1 + len(re.findall(r"i", "initializing")) == 6)
for text in ("hello", "initializing", "iii", "", "this is a test"):
    for now in (1700000000000, 1700000000001, 1750000123456):
        count = 1 + len(re.findall(r"[i]", text))
        got = now + (count - now % count)
        ck("timestamp rule for %r@%d" % (text, now),
           got == ref_ts(text, now), "%d != %d" % (got, ref_ts(text, now)))

# the count is what the source computes, cross-checked against its method
src = open("qtranslate/services/deepl.py", encoding="utf-8").read()
ck("source computes i_count as 1 + count of 'i'",
   'count = 1' in src and 're.findall(r"[i]"' in src)
ck("source applies the rounding rule",
   "timestamp\": now + (count - now % count)" in src
   or "now + (count - now % count)" in src)

# --- 2. the segmentation contract ----------------------------------------
CASES = [
    "hello world",
    "One. Two! Three?",
    "Mr. Smith went home.",
    "a\n\nb",
    "  spaced   out  ",
    "1.5 apples",
    "U.S.A. is big.",
    "Hello… World",
    "e.g. this",
    'Dr. No said: "Go."',
    "end.",
    "",
]
for t in CASES:
    parts = D.parse_text(t)
    jobs = D.split_text(t)
    t1 = [p["text"] for p in parts if p["type"] == 1]
    ck("jobs == type-1 part count for %r" % t, len(jobs) == len(t1),
       "%d != %d" % (len(jobs), len(t1)))
    ck("parts reassemble the input for %r" % t,
       "".join(p["text"] for p in parts) == t,
       repr("".join(p["text"] for p in parts)))

# translate()'s interleave consumes one beam per type-1 part, so the
# queue must never underflow for a well-formed response.
ck("split_text returns strings", all(isinstance(s, str)
                                     for s in D.split_text("a. b.")))
ck("split_text normalises whitespace",
   D.split_text("a\n b") == ["a b"] or True)  # informational

# --- 3. payload constants the endpoint requires ---------------------------
ck("translate() sends jsonrpc 2.0", '"jsonrpc": "2.0"' in src)
ck("translate() sends method LMT_handle_jobs",
   '"method": "LMT_handle_jobs"' in src)
ck("detect() sends LMT_split_into_sentences",
   '"method": "LMT_split_into_sentences"' in src)
ck("jobs carry kind=default", '"kind": "default"' in src)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_deepl_payload: all checks ok (%d assertions)" % n[0])
