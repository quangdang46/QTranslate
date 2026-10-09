"""Regression: Google full-duplex speech-input URL builder (J5).

Native evidence: FUN_004434FE (rev 2026-10-09) builds both endpoints; the key
literal and every query parameter is byte-verified from the binary. Pair id
is random (FUN_00443b9a). Offline only -- no network.
"""
import sys

sys.path.insert(0, "C:/Users/ADMIN/qtranslate-re")

from qtranslate import speech_input as S  # noqa: E402

failures = []


def check(name, cond, detail=""):
    if not cond:
        failures.append("%s%s" % (name, (" -- " + detail) if detail else ""))


u = S.build_urls(lang="en-US", rate=16000, pair="deadbeefdeadbeef",
                 pfilter=2, continuous=False)

check("up endpoint", u["up"].startswith(
    "https://www.google.com/speech-api/full-duplex/v1/up?"), u["up"])
check("down endpoint", u["down"].startswith(
    "https://www.google.com/speech-api/full-duplex/v1/down?"), u["down"])
check("embedded key verbatim", "key=AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw"
      in u["up"] and "key=AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw" in u["down"])
check("pair id present both", "pair=deadbeefdeadbeef" in u["up"]
      and "pair=deadbeefdeadbeef" in u["down"])
check("output=json both", "output=json" in u["up"] and "output=json" in u["down"])
check("lang param", "lang=en-US" in u["up"])
check("pFilter=2", "pFilter=2" in u["up"])
check("maxAlternatives=1", "maxAlternatives=1" in u["up"])
check("app=chromium", "app=chromium" in u["up"])
check("endpoint=1 when not continuous", "endpoint=1" in u["up"]
      and "continuous" not in u["up"])
check("Content-Type audio/x-flac; rate=", u["content_type"] ==
      "audio/x-flac; rate=16000", u["content_type"])

# down endpoint has NO lang/pFilter/app (native: key+pair+output only).
check("down has no lang/app", "lang=" not in u["down"]
      and "app=" not in u["down"])

# continuous + interim + pfilter=0 variants.
u2 = S.build_urls(lang="vi-VN", rate=44100, pair="p", pfilter=0,
                  continuous=True, interim=True)
check("continuous variant", "continuous" in u2["up"]
      and "endpoint=1" not in u2["up"])
check("interim variant", "&interim" in u2["up"] or u2["up"].endswith("interim"))
check("pFilter=0 variant", "pFilter=0" in u2["up"])
check("rate reflected in content-type", u2["content_type"] ==
      "audio/x-flac; rate=44100", u2["content_type"])

# pair id is random-8-byte hex.
pid = S.new_pair_id()
check("pair id is 16 hex chars (8 random bytes)", len(pid) == 16
      and all(c in "0123456789abcdef" for c in pid), pid)
check("two pair ids differ", S.new_pair_id() != S.new_pair_id())

if failures:
    raise SystemExit("FAIL:\n  " + "\n  ".join(failures))
print("OK: full-duplex speech URL builder matches native FUN_004434FE")
