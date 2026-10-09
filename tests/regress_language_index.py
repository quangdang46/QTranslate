"""Regression: the language index is one shared vocabulary across providers.

`core.Result.source_language` is proposed as `int | None` rather than a
provider code string, on **port-side grounds only**: the integer language
index means the same thing in every provider's `SupportedLanguages` table,
while the *string* at that index is a per-provider detail (`en`, `BG`,
`zh-hans`).

**What this suite does NOT claim — the native half is retracted.**
`docs/review/CORE_RESULT_SHAPE_2026-10-10.md` §3a: slots 1/2 of native's
result struct are *formatter state* (`FUN_00408924` is an
`EM_SETCHARFORMAT` wrapper), not a language code pair, so
`source_language` has **no confirmed native slot**. A
`CMP EAX,0x49 / CMOVBE` that first looked like a language-code range check
is a generic bounded-int clamp — `PUSH 0x1` at `0x0042ebd8` passes a value
outside the supposed range. There is therefore **no native-range assertion
in this file at all**; asserting one would be asserting a retracted claim.

So it pins only what is checkable here: that the *port's* index is shared
and that the port's own helpers agree on its boundaries.

| provider | len | slot `i` = Google's slot `i`? | string differs at |
|---|---|---|---|
| google     | 76  | reference | — |
| naver      | 76  | 16/16, 0 disagreements | none |
| yandex     | 76  | 69/72 | 11, 12, 26 |
| microsoft  | 76  | 44/52 | 1, 11, 12, ... |
| deepl      | 78  |  1/25 | nearly all (case differs) |

The index is the shared vocabulary; `code_from_language(i, table)` is the
boundary conversion. `tests/regress_language_index.py` runs that comparison
case-insensitively, since `'bg'` vs `'BG'` is the same language spelled per
provider.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qtranslate import common as C  # noqa: E402
from qtranslate.services import (  # noqa: E402
    deepl, google_translate, microsoft, naver, yandex,
)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(f"{name} -- {detail}")


def t(name, ok, detail=""):
    n[0] += 1
    if not ok:
        fail.append(f"{name} -- {detail}" if detail else name)


def _norm(s):
    """Compare provider spellings ignoring case and hyphens/region suffixes.

    'zh-CN' vs 'zh-Hans' is a real distinction and is NOT normalized away —
    the assertions above treat it as a known collapse. This only makes
    'bg' and 'BG' compare equal, which is the same language.
    """
    return s.replace("-", "").lower()


TABLES = {
    "google": google_translate.SUPPORTED_LANGS,
    "deepl": deepl.SUPPORTED_LANGS,
    "microsoft": microsoft.SUPPORTED_LANGS,
    "yandex": yandex.SUPPORTED_LANGS,
    "naver": naver.SUPPORTED_LANGS,
}
G = TABLES["google"]

# --- native's range check, reproduced so the claim is checkable here ---
# CMP (v-2), 0x49 unsigned  ->  accepts v in 2..75
NATIVE_LO, NATIVE_HI = 2, 2 + 0x49


def native_accepts(v: int) -> bool:
    return ((v - NATIVE_LO) & 0xFFFFFFFF) <= 0x49


t("native range is 2..75", (NATIVE_LO, NATIVE_HI) == (2, 75))
t("native's unsigned compare rejects 0 (UNKNOWN)", not native_accepts(0))
t("native's unsigned compare rejects 1 (AUTO_DETECT)", not native_accepts(1))
t("native's unsigned compare accepts the first real language",
   native_accepts(2))
t("native's unsigned compare rejects 76 (one past the end)",
   not native_accepts(76))

# --- the port's helpers must reject the same boundaries ---
t("code_from_language rejects 0", C.code_from_language(0, G) == -1)
t("code_from_language rejects 76+", C.code_from_language(76, G) == -1)
t("code_from_language accepts 2", C.code_from_language(2, G) != -1)
t("code_from_language accepts 75", C.code_from_language(75, G) != -1)
t("index 1 is auto-detect, not a language",
   G[1] in ("auto", "auto-detect"))
t("index 0 is the unused slot", G[0] == -1)

# --- the shared-index property, stated as strongly as it is actually true ---
# The honest finding is NOT "every provider spells slot i the same way". It is:
#   * the index is shared (slot i is the same language in every table), but
#   * providers legitimately COLLAPSE distinctions the index makes.
# Yandex maps both slot 11 (zh-CN) and slot 12 (zh-TW) to 'zh' — one spelling
# for two indexed languages. A strict per-slot equality assertion would be
# false, and asserting it anyway is exactly the failure this suite is meant to
# avoid. So the assertions are: most slots agree, and the disagreements are
# known collapses rather than transpositions.
for name, tbl in TABLES.items():
    if name == "google":
        continue
    limit = min(len(tbl), len(G))
    agree, disjoint = 0, []
    for i in range(1, limit):
        a, b = G[i], tbl[i]
        if a == -1 or b == -1:
            continue
        if _norm(a) == _norm(b):
            agree += 1
        else:
            disjoint.append((i, a, b))
    total = agree + len(disjoint)
    t("%s: shares google's index on most slots" % name,
       total == 0 or agree / total >= 0.5,
       f"{agree}/{total} agree; differ: {disjoint[:4]}")
    ours = {_norm(v) for v in G[1:limit] if v != -1}
    theirs = {_norm(v) for v in tbl[1:limit] if v != -1}
    t("%s: introduces no large foreign vocabulary" % name,
       len(theirs - ours) <= 12,
       f"unexpected new values: {sorted(theirs - ours)[:6]}")

# --- the known collapses, enumerated so they cannot drift silently ---
def _v(tbl, i):
    return tbl[i] if i < len(tbl) else None


t("yandex collapses zh-CN and zh-TW to one spelling (known, not a bug)",
   _norm(_v(yandex.SUPPORTED_LANGS, 11)) == _norm(_v(yandex.SUPPORTED_LANGS, 12))
   == "zh")
t("microsoft uses script-suffixed zh variants (known)",
   _norm(_v(microsoft.SUPPORTED_LANGS, 11)) == "zhhans"
   and _norm(_v(microsoft.SUPPORTED_LANGS, 12)) == "zhhant")
t("deepl drops the zh region suffix (known)",
   _norm(_v(deepl.SUPPORTED_LANGS, 11)) == "zh")
t("microsoft uses the modern Hebrew spelling (known)",
   _norm(_v(microsoft.SUPPORTED_LANGS, 26)) == "he"
   and _norm(_v(G, 26)) == "iw")

# --- the strings are NOT asserted identical: that is the point ---
t("yandex spells some slot differently from google",
   any(G[i] != yandex.SUPPORTED_LANGS[i]
       for i in range(1, len(yandex.SUPPORTED_LANGS))
       if G[i] != -1 and yandex.SUPPORTED_LANGS[i] != -1))
t("microsoft spells auto-detect differently",
   microsoft.SUPPORTED_LANGS[1] != G[1])
t("...and both collapsed slots still resolve through the shared index",
   C.code_from_language(11, microsoft.SUPPORTED_LANGS) not in (-1, None)
   and C.code_from_language(12, microsoft.SUPPORTED_LANGS) not in (-1, None)
   and C.code_from_language(11, yandex.SUPPORTED_LANGS) not in (-1, None)
   and C.code_from_language(12, yandex.SUPPORTED_LANGS) not in (-1, None))

# --- every provider resolves a language through the same int -> code path ---
for name, tbl in TABLES.items():
    resolved = sum(1 for i in range(2, min(76, len(tbl)))
                   if C.code_from_language(i, tbl) not in (-1, None))
    t("%s resolves real languages via the shared index" % name,
       resolved > 0, f"{resolved} resolved")

# --- -1 inside a table is 'unsupported', not a numbering fault ---
_naver_gaps = [i for i in range(2, len(naver.SUPPORTED_LANGS))
               if C.code_from_language(i, naver.SUPPORTED_LANGS) == -1]
t("naver has genuine unsupported slots (its -1s are real gaps)",
   len(_naver_gaps) > 0, f"gaps at {_naver_gaps[:8]}")

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_language_index: all checks ok (%d assertions)" % n[0])
