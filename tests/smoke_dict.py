"""Smoke test: import every dictionary/TTS entry point (no live calls)."""
import sys

sys.path.insert(0, "C:/Users/ADMIN/qtranslate-re")

from qtranslate.services import dictionary as d  # noqa: E402
from qtranslate import tts  # noqa: E402

DICT_FUNCS = ["babylon_lookup", "babylon_dict_lookup", "lingvo_lookup",
              "reverso_lookup", "wordreference_lookup", "oxford_lookup",
              "multitran_lookup", "imtranslator_lookup", "urban_lookup",
              "wikipedia_lookup", "google_search_lookup"]
TTS_FUNCS = ["google_tts", "yandex_tts", "baidu_tts"]
LANG_LISTS = ["BABYLON_LANGS", "BABYLON_DICT_LANGS", "LINGVO_LANGS",
              "REVERSO_LANGS", "WORDREF_LANGS", "OXFORD_LANGS",
              "MULTITRAN_LANGS", "IMTRANS_LANGS", "URBAN_LANGS",
              "WIKI_LANGS", "GSEARCH_LANGS"]

failures = []
for name in DICT_FUNCS:
    fn = getattr(d, name, None)
    if not callable(fn):
        failures.append("dictionary.%s missing" % name)
for name in LANG_LISTS:
    if not isinstance(getattr(d, name, None), list):
        failures.append("dictionary.%s missing" % name)
for name in TTS_FUNCS:
    if not callable(getattr(tts, name, None)):
        failures.append("tts.%s missing" % name)
assert set(getattr(f, "__name__", k) for k, f in d.PROVIDERS.items()) == set(DICT_FUNCS), "PROVIDERS registry incomplete"

# Pure offline check of the slicing helper (no network).
assert d._sub("a<div>x</div>b", "<div>", False, "</div>", False) == "x"
assert d._sub("a<div>x</div>b", "<div>", True, "</div>", True) == "<div>x</div>"
assert d._sub("nothing here", "<div>", False, "</div>", False) == ""
assert tts._yandex_voice("en") == "en_GB"
assert tts._yandex_voice("de") == "de_DE"

if failures:
    raise SystemExit("FAIL: " + "; ".join(failures))
print("OK: %d dict funcs, %d lang lists, %d tts funcs" % (
    len(DICT_FUNCS), len(LANG_LISTS), len(TTS_FUNCS)))

# common helper equivalence (ported from Common.js, verified 2026-10-07)
from qtranslate import common as _c
assert _c.trim_string("  a  ") == "a"
assert _c.unquote_html("&lt;b&gt;") == "<b>"
assert "https://e.com/p" in _c.update_html_links('<a href="/p">x</a>', "https://e.com")
assert _c.string_find_sub("a[START]mid[END]b", "[START]", False, "[END]", False) == "mid"
assert _c.is_language(17, [None] * 70) and not _c.is_language(1, [None] * 70)
print("OK: common helpers (trim/unquote/links/sub/lang)")

# deepl sentence splitting (matches JS parseText edge cases)
from qtranslate.services.deepl import split_text as _split
assert _split("Hello world. How are you? Fine!") == ["Hello world.", "How are you?", "Fine!"]
print("OK: deepl split")
