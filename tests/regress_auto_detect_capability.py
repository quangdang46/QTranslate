"""Regression: the auto-detect capability is native's rule, derived and applied.

Native asks each service whether it accepts an auto source by calling the JS
hook `usesAutoDetectCode` (host call `FUN_0043b8ce(this,
L"usesAutoDetectCode", ...)`, answer stored at request+0x50). The translate
stage (`FUN_004606ba`) then runs detect itself only when that answer is
false, or when the destination is also unset.

The hook is **not** a per-service function. It is a framework function in
`Services/Common.js`:

    function usesAutoDetectCode(){
        return SupportedLanguages[AUTO_DETECT_LANGUAGE] !== UNKNOWN_LANGUAGE_CODE
    }

with `AUTO_DETECT_LANGUAGE = 1` and `UNKNOWN_LANGUAGE_CODE = -1`.
`SupportedLanguages` is the per-service language table, so the answer is
"does this service's own table hold a real code in slot 1?".

That rule was applied to the **recovered** `Services/*/Service.js` files on
2026-10-21; the truth table is committed at
`docs/review/auto_detect_capability_table.json` and the port's own
transcribed `SUPPORTED_LANGS` tables reproduce it exactly (same slot-1
values), so the port can derive the capability instead of declaring it.

What this suite pins, all by CALLING the code:

  1. the derived capability table equals native's measured truth table
  2. each provider's OWN auto code -- native sends `codeFromLanguage(1)`,
     which is "auto-detect" for Microsoft, "AUTO" for youdao, "au" for
     Promt -- and that is what reaches the wire
  3. `detect_language` answers with a CODE string. It used to hand back
     Google's language *index* unchanged: the request's `src` then carried
     an int, which a provider adapter read as that provider's own index
     (a different language) or crashed on (`str.upper` of an int).
  4. a service that does not accept an auto source still gets a locally
     detected concrete code.

Evidence:
  docs/review/AUTO_DETECT_CAPABILITY_2026-10-21.md
  docs/review/SOURCE_LANGUAGE_RULE_2026-10-10.md §1-§3
  docs/review/auto_detect_capability_table.json
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(f"{name} -- {detail}")


from qtranslate import registry as RG  # noqa: E402

# --- 1. the derived capability equals native's measured truth table --------
TABLE_PATH = os.path.join(ROOT, "docs", "review",
                          "auto_detect_capability_table.json")
ck("the measured truth table is committed", os.path.isfile(TABLE_PATH))
if os.path.isfile(TABLE_PATH):
    with open(TABLE_PATH, encoding="utf-8") as fh:
        table = json.load(fh)
    ck("the table records native's rule",
       "AUTO_DETECT_LANGUAGE" in table.get("rule", "")
       and table.get("auto_detect_language_index") == 1
       and table.get("unknown_language_code") == -1,
       repr(table.get("rule"))[:120])
    # The port's provider ids are a subset of native's service names; map the
    # ones the port has and check the answers agree.
    native = {row["service"]: row["uses_auto_detect"]
              for row in table["services"]}
    # port id -> native service name
    mapping = {
        "google": "Google",
        "microsoft": "Microsoft",
        "deepl": "DeepL",
        "yandex": "Yandex",
        "baidu": "Baidu",
        "naver": "Papago",
        "youdao": "youdao",
        "promt": "Promt",
        "babylon": "Babylon",
    }
    for port_id, native_name in mapping.items():
        ck(f"{port_id}: the port's answer matches native's ({native_name})",
           RG.uses_auto_detect(port_id) == native[native_name],
           f"port={RG.uses_auto_detect(port_id)} native={native[native_name]}")

# --- 2. each provider's OWN auto code --------------------------------------
for service, expected in (("google", "auto"), ("deepl", "auto"),
                           ("naver", "auto"), ("microsoft", "auto-detect"),
                           ("youdao", "AUTO"), ("promt", "au")):
    ck(f"{service}'s own auto code is {expected!r}",
       RG.auto_detect_code(service) == expected,
       repr(RG.auto_detect_code(service)))
ck("bing shares microsoft's auto code",
   RG.auto_detect_code("bing") == "auto-detect",
   repr(RG.auto_detect_code("bing")))
ck("a service without an auto slot has no auto code",
   RG.auto_detect_code("yandex") is None,
   repr(RG.auto_detect_code("yandex")))

# --- 3. detect_language answers with a CODE string -------------------------
# A detector that returns an INDEX must not leak it into the request's src.
saved = RG._google.detect
try:
    RG._google.detect = lambda t: 17          # an index, as Google returns
    got = RG.detect_language("hello")
    ck("detect_language returns a code string, not an index",
       isinstance(got, str) and got != "",
       repr(got))
    ck("the leaked index never reaches the caller",
       not isinstance(got, int), repr(got))
finally:
    RG._google.detect = saved

# --- 4. the engine sends the provider's OWN auto code ----------------------
from qtranslate import engine as ENG  # noqa: E402
from qtranslate.services import youdao as _YO  # noqa: E402
from qtranslate.services import naver as _NA  # noqa: E402
from qtranslate.services import yandex as _YA  # noqa: E402


def _capture(module, attr, result):
    """Patch module.attr to capture (sl, tl) and return `result`."""
    seen = {}
    original = getattr(module, attr)

    def wrapper(text, sl, tl, *a, **k):
        seen["sl"] = sl
        seen["tl"] = tl
        seen["text"] = text
        return result

    setattr(module, attr, wrapper)
    return seen, original


def _restore(module, attr, original):
    setattr(module, attr, original)


class _NoDetect:
    """A detector that must NOT be consulted."""

    def __init__(self):
        self.called = 0

    def __call__(self, text):
        self.called += 1
        raise AssertionError("the detect chain ran for a service that accepts auto")


# youdao: native sends from=codeFromLanguage(1) = "AUTO", and must NOT be
# detected locally first -- native passes the auto source through.
seen, orig = _capture(_YO, "translate_web", "translated")
saved_detect = RG.detect_language
nodetect = _NoDetect()
try:
    RG.detect_language = nodetect
    ENG.translate("youdao", "hello", "vi", src="auto")
    ck("youdao receives its OWN auto code ('AUTO')",
       seen.get("sl") == "AUTO", repr(seen.get("sl")))
    ck("youdao's auto source is NOT detected locally first",
       nodetect.called == 0, "detect ran %d time(s)" % nodetect.called)
finally:
    RG.detect_language = saved_detect
    _restore(_YO, "translate_web", orig)

# naver: slot 1 is "auto", so the wire value does not change -- but the
# detect chain must still not run.
seen, orig = _capture(_NA, "translate", ("translated", 1, 17))
nodetect = _NoDetect()
try:
    RG.detect_language = nodetect
    ENG.translate("naver", "hello", "vi", src="auto")
    ck("naver receives its OWN auto code ('auto')",
       seen.get("sl") == "auto", repr(seen.get("sl")))
    ck("naver's auto source is NOT detected locally first",
       nodetect.called == 0, "detect ran %d time(s)" % nodetect.called)
finally:
    RG.detect_language = saved_detect
    _restore(_NA, "translate", orig)

# A service that does NOT accept an auto source must be detected locally
# first: yandex's table slot 1 is -1. The detector is mocked so the
# assertion does not depend on the network.
seen, orig = _capture(_YA, "translate", "translated")
try:
    RG.detect_language = lambda text: "fr"
    ENG.translate("yandex", "hello", "vi", src="auto")
    ck("yandex (no auto slot) receives a concrete detected code",
       seen.get("sl") == "fr", repr(seen.get("sl")))
finally:
    RG.detect_language = saved_detect
    _restore(_YA, "translate", orig)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_auto_detect_capability: all checks ok (%d assertions)" % n[0])
