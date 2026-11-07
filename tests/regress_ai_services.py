#!/usr/bin/env python3
"""ai-services plugin ports: vision OCR, spell check, dictionary,
summarizer, rewriter -- all stubbed at _complete/_complete_with_image,
never live."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtranslate.services import ai_translate as AI  # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    if cond:
        print("  ok", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, detail)


# Stub the two network leaves; everything above them is pure.
CALLS = []


def fake_complete(system, user_content, s=None):
    CALLS.append(("complete", system, user_content))
    return fake_complete.reply


def fake_complete_img(system, user_text, image_bytes, s=None):
    CALLS.append(("image", system, user_text, image_bytes[:4]))
    return fake_complete_img.reply


AI._complete = fake_complete
AI._complete_with_image = fake_complete_img

print("== spell_check ==")
fake_complete.reply = (
    '```json\n{"corrected_text": "the quick brown fox", '
    '"corrections": [{"original": "teh", "corrected": "the", '
    '"start_index": 0, "end_index": 3, "type": "spelling", '
    '"message": "typo"}, '
    '{"original": "quik", "corrected": "quick", '
    '"start_index": 4, "end_index": 8, "type": "GRAMMAR"}]}\n```')
r = AI.spell_check("teh quik brown fox", "en")
ck("correctedText", r["correctedText"] == "the quick brown fox",
   repr(r["correctedText"]))
ck("two corrections", len(r["corrections"]) == 2)
c0 = r["corrections"][0]
ck("offsets", c0["startIndex"] == 0 and c0["endIndex"] == 3)
ck("suggestions", c0["suggestions"] == ["the"])
ck("type normalized", c0["type"] == "SPELLING"
   and r["corrections"][1]["type"] == "GRAMMAR")
ck("system mentions language", "English" in CALLS[-1][1])

# Out-of-range offsets clamp like upstream coerceIn.
fake_complete.reply = ('{"corrected_text": "x", "corrections": ['
                       '{"original": "a", "corrected": "b", '
                       '"start_index": -5, "end_index": 999, '
                       '"type": "SPELLING"}]}')
r = AI.spell_check("hello world", "en")
ck("clamped", r["corrections"][0]["startIndex"] == 0
   and r["corrections"][0]["endIndex"] == 11,
   repr(r["corrections"][0]))

# Blank input short-circuits without a call.
n0 = len(CALLS)
ck("blank -> empty", AI.spell_check("   ", "en")["corrections"] == []
   and len(CALLS) == n0)

print("== vision_ocr ==")
fake_complete_img.reply = (
    '```json\n{"text": "Hello\\nWorld", "detected_language": "en"}\n```')
r = AI.vision_ocr(b"\x89PNG\r\n\x1a\nXXXX", "eng")
ck("kind", CALLS[-1][0] == "image")
ck("text", r["text"] == "Hello\nWorld", repr(r))
ck("detected", r["detected_language"] == "en")
ck("hint in prompt", "English" in CALLS[-1][1])
ck("png sniff", AI._image_format(b"\x89PNG\r\n\x1a\nxx") == "png")
ck("jpeg sniff", AI._image_format(b"\xff\xd8\xff\xe0xx") == "jpeg")
ck("webp sniff", AI._image_format(b"RIFF\x00\x00\x00\x00WEBPxx")
   == "webp")
ck("fallback", AI._image_format(b"\x00\x01\x02") == "png")

print("== dict_lookup ==")
fake_complete.reply = (
    '{"entries": [{"word": "serendipity", "part_of_speech": "noun",'
    ' "phonetic": "/ˌser.ənˈdɪp.ə.ti/", "definitions": ['
    '{"text": "fortunate accident", "example": "a serendipity"}],'
    ' "synonyms": ["chance", "fluke"]}]}')
frag = AI.dict_lookup("serendipity", "en", "vi")
ck("html has word", "serendipity" in frag)
ck("html has pos", "noun" in frag)
ck("html has def", "fortunate accident" in frag)
ck("html has syn", "chance" in frag)
fake_complete.reply = '{"entries": []}'
ck("no entries -> empty", AI.dict_lookup("zzz", "en", "vi") == "")

print("== summarize / rewrite ==")
fake_complete.reply = "  A short summary.  "
ck("summarize strips", AI.summarize("long text...", "SHORT")
   == "A short summary.")
ck("summarize prompt", "single sentence" in CALLS[-1][1])
fake_complete.reply = '"Rewritten text."'
ck("rewrite strips quotes", AI.rewrite("blah", "CASUAL")
   == "Rewritten text.")
ck("rewrite prompt", "conversational" in CALLS[-1][1])

print("== _json_from_model ==")
ck("fence strip", AI._json_from_model('```json\n{"a":1}\n```')
   == {"a": 1})
ck("prose wrap", AI._json_from_model('sure! {"a":2} done')
   == {"a": 2})
try:
    AI._json_from_model("not json at all")
    ck("bad json raises", False)
except RuntimeError:
    ck("bad json raises", True)

print("== registration ==")
from qtranslate.extensions import ExtensionManager
m = ExtensionManager()
from qtranslate import registry as _RG
ck("ai-dictionary in DICT_EXT", "ai-dictionary" in _RG.DICT_EXT)
ck("dict_lookup wired", callable(_RG.DICT_EXT["ai-dictionary"]))
fake_complete.reply = '{"entries": []}'
frag = _RG.DICT_EXT["ai-dictionary"]("test", "en", "vi")
ck("wired returns frag", frag == "", repr(frag)[:60])
# The real unconfigured-raises check happens after the reload below.
import qtranslate.config as _C
saved = _C.DEFAULT_PATH
import tempfile
fd, tmp = tempfile.mkstemp(suffix=".json")
os.close(fd)
_C.DEFAULT_PATH = tmp
try:
    import importlib
    importlib.reload(AI)  # restores the real _complete/_with_image
    try:
        AI.spell_check("teh", "en")
        ck("unconfigured raises", False, "no exception")
    except RuntimeError as e:
        ck("unconfigured raises", "API key" in str(e)
           or "local" in str(e), str(e)[:60])
finally:
    _C.DEFAULT_PATH = saved
    try:
        os.unlink(tmp)
    except OSError:
        pass

print()
if FAIL:
    print("regress_ai_services: %d FAILED: %s" % (len(FAIL), FAIL))
    sys.exit(1)
print("regress_ai_services: all checks ok")
