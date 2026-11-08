"""Regression: ``dictionary.reverso_lookup``'s API fallback language legs.

The legacy HTML path is Cloudflare-walled, so ``reverso_lookup`` falls
back to ``reverso_translate`` (the live context API). That API speaks
language CODES, while ``_codes`` -- and therefore ``reverso_lookup``'s
own contract -- accepts native language INDICES too. The fallback used
to forward the raw arguments, so an index pair (17, 21) reached the API
as ``"from": 17`` and the lookup silently returned "".

Pinned here (offline -- ``_get`` and ``reverso_translate`` are stubbed):

  1. int legs resolve through REVERSO_LANGS to the table names the API
     map knows (17 -> "english" -> "eng");
  2. code strings pass through UNCHANGED so languages the dictionary
     table lacks but the API supports ("vi" -> "vie") still work;
  3. a leg resolving to -1 (unsupported in the table) is forwarded as
     the raw value, keeping the failure honest rather than substituting.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


from qtranslate.services import dictionary as D          # noqa: E402

seen = []
_orig_get = D._get
_orig_tr = D.reverso_translate
try:
    # The HTML path always fails -> the API fallback runs.
    D._get = lambda *a, **kw: (_ for _ in ()).throw(IOError("walled"))
    D.reverso_translate = lambda word, sl, tl: (
        seen.append((sl, tl)) or "bonjour")

    frag = D.reverso_lookup("hello", 17, 21)
    ck("index pair produces the fallback fragment",
       "bonjour" in frag, repr(frag))
    ck("index legs resolved to API-map names",
       seen[-1] == ("english", "french"), str(seen[-1]))

    frag = D.reverso_lookup("hello", "en", "fr")
    ck("code pair still works", "bonjour" in frag, repr(frag))
    ck("code legs pass through for the API's own map",
       seen[-1] == ("en", "fr"), str(seen[-1]))

    frag = D.reverso_lookup("hello", "en", "vi")
    ck("code outside the dict table passes through",
       seen[-1] == ("en", "vi"), str(seen[-1]))

    frag = D.reverso_lookup("hello", 60, 21)
    ck("unsupported index leg forwarded raw (honest -1 path)",
       seen[-1][0] in (60, -1), str(seen[-1]))
finally:
    D._get = _orig_get
    D.reverso_translate = _orig_tr

if fail:
    print("FAIL %d" % len(fail))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_reverso_fallback: all checks ok (%d assertions)" % n[0])
