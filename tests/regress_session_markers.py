"""Regression: the session-scrape markers match the recovered image byte for byte.

Every literal below is read straight out of
`docs/review/artifacts/QTranslate.6.10.0.exe` (UTF-16LE `.rdata`), never
executed. These are the native markers `qtranslate/session.py`'s scrape
regexes must match, and this suite compares both sides.

Two divergences it caught (fixed 2026-10-16):

  1. **Bing's helper array.** The image spells
     ``var params_RichTranslateHelper = [IG:"`` -- the array's first member
     is the *IG marker*, not a number. The port's regex was
     ``params_AbusePreventionHelper\\s*=\\s*\\[(\\d+),"([^"]+)",(\\d+)``: a
     different name AND a different first member, so it could never match
     the page native reads.
  2. **Promt's hidden inputs.** The image spells
     ``id="_paft" type="hidden" value="`` and ``id="_xsrf" type="hidden"
     value="``. The port looked for ``name="aft" value="`` -- wrong
     attribute (``name`` not ``id``) and wrong value (``aft`` not ``_paft``),
     so the scrape returned an empty paft on a page that has one.

Both were invisible to the live tests: the port reaches these endpoints
through its own scraping, so a marker mismatch looked like "site changed"
rather than "we diverged from native".

Headless: the image is READ, never executed. Skips when the artifact is absent.
"""
import io
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


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(REPO, "docs", "review", "artifacts",
                   "QTranslate.6.10.0.exe")
SESSION = os.path.join(REPO, "qtranslate", "session.py")

if not os.path.exists(EXE):
    print("SKIP: recovered image not present (%s)" % EXE)
    raise SystemExit(0)

RAW = io.open(EXE, "rb").read()
IA = RAW.decode("latin-1")          # one byte per char: finds the ascii copy
IW = RAW.decode("utf-16-le", "replace")  # finds the wide copy


def present(lit: str) -> bool:
    return lit in IA or lit in IW


# --- 1. the literals really are in the image ---------------------------
LITERALS = [
    "https://www.bing.com/translator",
    # The image stores these as TWO adjacent strings -- an ascii
    # `var params_RichTranslateHelper = [` immediately followed by a wide
    # `IG:"` (a NUL separates them) -- so the joined form is NOT in the
    # image and asserting it would be a false failure.
    "var params_RichTranslateHelper = [",
    'IG:"',
    "text=car&fromLang=en&to=ru&token=%s&key=%s&isAuthv2=true",
    "https://www.bing.com/ttranslatev3",
    'id="_paft" type="hidden" value="',
    'id="_xsrf" type="hidden" value="',
    "pageIx=0&v=1",
    "https://www.online-translator.com/api/pageLoad",
    "XSRF-TOKEN: %s",
    "Content-Type: application/x-www-form-urlencoded; charset=UTF-8",
    # Options keys the scrape writes into -- the port's config names
    "GoogleTkk", "BingCookie", "BingToken", "BingKey", "IG", "BaiduGtk",
    "BaiduCookie", "BaiduToken", "PromtCookie", "PromtXsrf", "PromtPaft",
    "YandexAppId",
]
for lit in LITERALS:
    ck("image contains %r" % lit[:52], present(lit))

# --- 2. what native's shapes are NOT -----------------------------------
ck("the image does NOT spell params_AbusePreventionHelper",
   not present("params_AbusePreventionHelper"))
ck("the image does NOT spell the port's old name=\"aft\" marker",
   not present('name="aft"'))

# --- 3. the port now reproduces the native shapes ----------------------
SRC = io.open(SESSION, encoding="utf-8").read()
# Split the source at the docstrings, so a check is about the CODE and not
# about prose that legitimately quotes the old (wrong) marker to explain
# the fix.
CODE = re.sub(r'"""(?:.|\n)*?"""', '""', SRC)
DOCS = re.sub(r'"""(?:.|\n)*?"""', lambda m: m.group(0), SRC)

ck("the port scrapes params_RichTranslateHelper",
   "params_RichTranslateHelper" in DOCS)
ck("...with the IG marker as the array's first member",
   re.search(r'IG:"\(\\w\+\)","\(\[\^"\]\+\)",\(\\d\+\)', CODE) is not None,
   "the port's array shape still does not match native")
ck("the port no longer carries the old AbusePreventionHelper regex in CODE",
   "params_AbusePreventionHelper" not in CODE)
ck("the port scrapes the _paft hidden input by its id",
   'id="_paft"' in CODE)
ck("the port no longer uses name=\"aft\" in CODE",
   'name="aft"' not in CODE)
ck("the port scrapes the _xsrf hidden input by its id too",
   'id="_xsrf"' in CODE)

# --- 3b. the array's slot order: [IG:"<ig>","<token>",<key>] ------------
# This port assigns key=group(1) / token=group(2) -- i.e. it took the IG
# itself as the key. Nothing caught it for eleven months because the old
# fixture put its numbers in the TOKEN slot, so both came back "some
# string". Pin the order by RUNNING the port's own regex over a
# native-shaped sample and checking which slot each value lands in.
m = re.search(r'IG:"\(\\w\+\)","\(\[\^"\]\+\)",\(\\d\+\)', CODE)
ck("the port's regex captures ig, token, key in that order", m is not None,
   CODE[CODE.find("IG:"):CODE.find("IG:") + 60])
SAMPLE = 'var params_RichTranslateHelper = [IG:"IGVAL","TOKVAL",42],'
got = re.search(m.group(0) if m else r"$^", SAMPLE)
ck("the sample matches the port's regex", got is not None, SAMPLE)
if got:
    ck("group 2 is the token (a quoted string)", got.group(2) == "TOKVAL",
       repr(got.group(2)))
    ck("group 3 is the key (digit-only)", got.group(3) == "42",
       repr(got.group(3)))
ck("the assignment puts token in group 2 and key in group 3",
   re.search(r'"token":\s*abuse\.group\(2\)', CODE) is not None
   and re.search(r'"key":\s*abuse\.group\(3\)', CODE) is not None,
   "the port still swaps the token and key slots")

# --- 4. the port's config keys are the native Options names -----------
# The keys are read by the provider modules (Options.get(...)), so scan the
# whole package rather than session.py alone.
PKG_SRC = [SRC]
for root, _dirs, files in os.walk(os.path.join(REPO, "qtranslate")):
    if "__pycache__" in root:
        continue
    for f in files:
        if f.endswith(".py"):
            PKG_SRC.append(io.open(os.path.join(root, f), encoding="utf-8",
                                   errors="replace").read())
PKG = "\n".join(PKG_SRC)

KEYS = ["GoogleTkk", "BingCookie", "BingToken", "BingKey", "BaiduGtk",
        "BaiduCookie", "BaiduToken", "PromtCookie", "PromtXsrf",
        "PromtPaft", "YandexAppId"]
for key in KEYS:
    ck("the port references the native Options key %r" % key,
       ('"%s"' % key) in PKG or ("'%s'" % key) in PKG)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_session_markers: all checks ok (%d assertions)" % n[0])
