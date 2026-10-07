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

# yandex chunking (600-char boundary, lossless)
from qtranslate.services.yandex import make_chunks as _ch
assert _ch("Hello") == ["Hello"]
_long = "Sentence one. " * 100
_chs = _ch(_long)
assert sum(map(len, _chs)) == len(_long[:10000]) and max(map(len, _chs)) <= 700
print("OK: yandex chunks")

# google tk() determinism (same input -> same token)
from qtranslate.services.google_translate import tk as _tk
assert _tk("Hello world") == _tk("Hello world")
print("OK: google tk deterministic")

# signing known-answer vectors (cross-checked vs node 2026-10-08;
# endpoints dead/walled, algorithms must still be bit-exact)
from qtranslate.services.baidu import sign as _bs
from qtranslate.services.youdao import make_sign as _ys
from qtranslate.services.promt import ghcs as _gh
assert _bs("hello", "123.456") == "108862.108869"
assert _ys("hello", "12345") == "bfb0a174c7922ca03cff241587151159"
assert _gh("Hello world") == 586917305  # node 1-arg call agrees
import qtranslate.services.promt  # syntax regression guard
print("OK: signing known-answer vectors")

# naver HMAC determinism (endpoint 404, algorithm must still be exact)
import uuid as _uuid, time as _time
from qtranslate.services import naver as _nv
_ru, _rt = _uuid.uuid4, _time.time
_uuid.uuid4 = lambda: "test-device-id"
_time.time = lambda: 1700000000.0
try:
    _h1, _ = _nv._auth("https://papago.naver.com/apis/n2mt/translate")
    _h2, _ = _nv._auth("https://papago.naver.com/apis/n2mt/translate")
    assert _h1 == _h2 and "PPG test-device-id:" in _h1
finally:
    _uuid.uuid4, _time.time = _ru, _rt
print("OK: naver HMAC deterministic")

# deepl payload determinism (timestamp formula with mocked time)
import time as _t2
from qtranslate.services import deepl as _dl
_real_post, _real_time = _dl._post_jsonrpc, _t2.time
captured = {}
def _fake_post(payload):
    captured.update(payload["params"])
    return {"result": {"translations": [{"beams": [{"postprocessed_sentence": "X"}]} for _ in payload["params"]["jobs"]]}}
_dl._post_jsonrpc = _fake_post
_t2.time = lambda: 1700000.0
try:
    _dl.translate("Hi there", "EN", "VI")
    _ts = captured["timestamp"]
    assert _ts % 1 == 0 and _ts >= 1700000000
finally:
    _dl._post_jsonrpc, _t2.time = _real_post, _real_time
print("OK: deepl payload")

# config: load real Options.json + hotkey round-trip + theme palettes
from qtranslate import config as _cfg
import os as _os
_real = _os.path.expanduser("~/AppData/Roaming/QTranslate/Options.json")
_cfg.load(_real)
assert _cfg.decode_hotkey(593)["vk"] == 0x51, "Ctrl+Q decode"
assert "Ctrl" in _cfg.format_hotkey(593) and "Q" in _cfg.format_hotkey(593)
assert len(_cfg.HOTKEY_NAMES) == 17, "17 real HotKey* in Options.json"
assert len(set(_cfg.HOTKEY_NAMES)) == 17, "no duplicate hotkey names"
print("OK: config real Options.json + hotkey round-trip")
