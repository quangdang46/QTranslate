"""Regression: DeepL request shape.

History: this suite originally pinned the legacy ``www2.deepl.com``
JSON-RPC ``LMT_handle_jobs`` payload (i_count timestamp rule and the
split_text/parse_text segmentation contract). Live probing showed that
endpoint now answers every translate with an "update DeepL" wall of
text, and plugins/deepl-services upstream replaced it with the
``oneshot-free.www.deepl.com/v1/translate`` JSON API -- so translate()
was re-ported onto that contract and the dead-protocol invariants were
dropped with it. ``detect()`` still uses the jsonrpc endpoint (that
method remains alive upstream of this port).

Pinned here, headless:

  1. translate() prefers the official api.deepl.com/v2 endpoint when
     General.DeeplApiKey is set, and falls back to the free web path;
  2. the free web path posts {text, target_lang, source_lang?} to
     oneshot-free with Authorization: None, paces requests >=2s,
     chunks >5000 chars, and retries once on rate-limit markers;
  3. _web_code/_official_code language mappings;
  4. detect() keeps the jsonrpc LMT_split_into_sentences shape.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.services import deepl as D  # noqa: E402

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


src = open("qtranslate/services/deepl.py", encoding="utf-8").read()

# --- 1. official-first ----------------------------------------------------
ck("official endpoint constant",
   'OFFICIAL_HOST = "https://api.deepl.com"' in src)
ck("official path /v2/translate",
   '"/v2/translate?key="' in src)
ck("translate() tries official when keyed",
   "_deepl_api_key()" in src and "official_translate(" in src)
ck("official failure falls through to web",
   "_web_translate(text, sl_code, tl_code)" in src)

# --- 2. free web contract -------------------------------------------------
ck("web endpoint is oneshot-free",
   'WEB_HOST = "https://oneshot-free.www.deepl.com"' in src)
ck("web path /v1/translate", '"/v1/translate"' in src)
ck("Authorization: None header", '"Authorization": "None"' in src)
ck("pace >= 2s", "WEB_MIN_INTERVAL = 2.0" in src
   and "_pace_web_request()" in src)
ck("rate-limit retry budget = 1", "WEB_MAX_RETRIES = 1" in src)
ck("rate-limit markers",
   "too many requests" in src and "1042911" in src)
ck("chunk cap 5000", "WEB_MAX_CHARS = 5_000" in src)
ck("random UA pool", "_WEB_UAS" in src and "_r.choice(_WEB_UAS)" in src)

# _web_code: toWebCode
ck("web_code zh collapses", D._web_code("ZH-HANS") == "zh"
   and D._web_code("ZH") == "zh")
ck("web_code lowercases tag", D._web_code("EN") == "en"
   and D._web_code("VI") == "vi")
ck("web_code strips region", D._web_code("PT-BR") == "pt")

# _split_for_web boundaries
ck("short text is one chunk", D._split_for_web("hello") == ["hello"])
long_text = "word " * 1200 + "END"
chunks = D._split_for_web(long_text)
ck(">5000 chars splits", len(chunks) > 1, str(len(chunks)))
ck("chunks respect the cap",
   all(len(c) <= D.WEB_MAX_CHARS for c in chunks),
   str([len(c) for c in chunks]))
ck("chunks reassemble the input", "".join(chunks) == long_text)

# request body shape via a stubbed post
seen = []


def fake_post(body):
    seen.append(body)
    return json.dumps({"translations": [{"text": "Xin chào"}]})


orig = D._web_post
D._web_post = fake_post
try:
    out = D._web_translate_once("Hello", "EN", "VI")
finally:
    D._web_post = orig
ck("once returns translated text", out == "Xin chào", out)
ck("body text list", seen and seen[0].get("text") == ["Hello"])
ck("body target_lang web code", seen and seen[0].get("target_lang") == "vi")
ck("body source_lang web code", seen and seen[0].get("source_lang") == "en")

seen.clear()
D._web_post = fake_post
try:
    D._web_translate_once("hi", "auto", "VI")
finally:
    D._web_post = orig
ck("auto omits source_lang", "source_lang" not in seen[0], str(seen[0]))

# --- 3. detect() keeps jsonrpc ---------------------------------------------
ck("detect() sends LMT_split_into_sentences",
   '"method": "LMT_split_into_sentences"' in src)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_deepl_payload: all checks ok (%d assertions)" % n[0])
