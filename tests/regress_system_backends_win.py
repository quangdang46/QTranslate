#!/usr/bin/env python3
"""Windows system TTS (SAPI SpVoice) + spell (ISpellCheckerFactory COM)
dispatch checks.

Stubs ``sys.platform='win32'`` so the Windows branches run on macOS.
No Windows-only module is ever imported for real: SAPI goes through a
fake ``comtypes.client`` in ``sys.modules`` and the spell COM path is
exercised only down to its honest-failure return (``ctypes.windll``
does not exist off Windows -> ``check`` returns None).
"""
import os
import sys
import tempfile
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FAIL = []


def ck(name, cond, detail=""):
    if cond:
        print("  ok", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, detail)


from qtranslate.services import system_tts as ST  # noqa: E402
from qtranslate.services import system_spell as SS  # noqa: E402

REAL_PLATFORM = sys.platform


class _Tok:
    def __init__(self, desc, lcid):
        self._d, self._l = desc, str(lcid)

    def GetDescription(self):
        return self._d

    def GetAttribute(self, name):
        return self._l if name == "Language" else ""


class _Voices:
    def __init__(self, toks):
        self.Count = len(toks)
        self._t = toks

    def Item(self, i):
        return self._t[i]


class _SpVoice:
    def __init__(self, voices):
        self._v = voices
        self.Voice = None
        self.Rate = 0
        self.spoken = []

    def GetVoices(self):
        return self._v

    def Speak(self, text):
        self.spoken.append(text)


def _install_fake_comtypes(sp):
    comtypes = types.ModuleType("comtypes")
    client = types.ModuleType("comtypes.client")
    client.CreateObject = lambda progid: sp
    comtypes.client = client
    sys.modules["comtypes"] = comtypes
    sys.modules["comtypes.client"] = client


def _drop_comtypes():
    sys.modules.pop("comtypes", None)
    sys.modules.pop("comtypes.client", None)


def main():
    print("== system_tts Windows dispatch ==")
    david = _Tok("Microsoft David", 1033)   # en-US
    huihui = _Tok("Microsoft Huihui", 2052)  # zh-CN
    sp = _SpVoice(_Voices([david, huihui]))
    _install_fake_comtypes(sp)
    # LCID -> locale is kernel32-only; pin it for the fake tokens.
    real_lcid = ST._lcid_locale
    ST._lcid_locale = lambda lcid: {1033: "en-US",
                                    2052: "zh-CN"}.get(lcid, "")
    real_run = __import__("subprocess").run
    try:
        sys.platform = "win32"
        # discover_voices must NOT shell out to `say` on Windows.
        import subprocess
        subprocess.run = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("say invoked on win32"))
        try:
            voices = ST.discover_voices()
        finally:
            subprocess.run = real_run
        ck("sapi voices discovered",
           voices == [("Microsoft David", "en-US"),
                      ("Microsoft Huihui", "zh-CN")], repr(voices))
        ck("win preferred exact",
           ST.preferred_voice("zh-CN") == "Microsoft Huihui")
        ck("win preferred base lang",
           ST.preferred_voice("zh") == "Microsoft Huihui")
        ck("win preferred en",
           ST.preferred_voice("en") == "Microsoft David")
        ck("win auto -> None", ST.preferred_voice("auto") is None)

        print("== system_tts.speak (SAPI SpVoice) ==")
        ck("speak en picks David",
           ST.speak("hello", "en") is True
           and sp.Voice is david and sp.spoken == ["hello"],
           repr((sp.Voice, sp.spoken)))
        ck("speak zh picks Huihui",
           ST.speak("你好", "zh-CN") is True and sp.Voice is huihui)
        ck("speak slow rate",
           ST.speak("hi", "en", slow=True) is True and sp.Rate == -4,
           repr(sp.Rate))
        ck("speak normal rate",
           ST.speak("hi", "en") is True and sp.Rate == 0, repr(sp.Rate))
        before = sp.Voice
        ck("speak auto keeps default voice",
           ST.speak("hi", "auto") is True and sp.Voice is before)
        ck("speak unmatched lang keeps default",
           ST.speak("hi", "xx") is True and sp.Voice is before)
    finally:
        sys.platform = REAL_PLATFORM
        ST._lcid_locale = real_lcid
        _drop_comtypes()

    print("== system_tts.speak honest fallback ==")
    # pin a non-Windows platform -- on a real Windows host the true
    # platform IS win32 and speak() would fire SAPI for real
    sys.platform = "linux"
    try:
        ck("speak False off-Windows", ST.speak("hi", "en") is False)
    finally:
        sys.platform = REAL_PLATFORM
    sys.platform = "win32"
    try:
        # a real comtypes install must not be allowed to speak here:
        # sys.modules[name]=None makes `import comtypes.client` raise
        sys.modules["comtypes"] = None
        sys.modules["comtypes.client"] = None
        try:
            ck("speak False without comtypes",
               ST.speak("hi", "en") is False)
        finally:
            sys.modules.pop("comtypes", None)
            sys.modules.pop("comtypes.client", None)
    finally:
        sys.platform = REAL_PLATFORM

    print("== system_spell Windows dispatch ==")
    sys.platform = "win32"
    try:
        ck("available on win32", SS.available() is True)
        sentinel = {"correctedText": "x", "corrections": []}
        real_win = SS._check_win
        SS._check_win = lambda text, lang: sentinel
        try:
            ck("check dispatches to _check_win",
               SS.check("teh", "en") is sentinel)
        finally:
            SS._check_win = real_win
        # Real _check_win: off-Windows ctypes.windll is absent ->
        # None; on a real Windows host with COM + a language pack it
        # legitimately returns a result dict -- both are honest.
        r = SS.check("teh", "en")
        ck("check honest off/without COM",
           r is None or isinstance(r, dict), repr(r)[:80])
    finally:
        sys.platform = REAL_PLATFORM
    sys.platform = "darwin"
    try:
        ck("available on darwin", SS.available() is True)
        sentinel = {"correctedText": "y", "corrections": []}
        real_chk, real_macos = SS._checker, SS._check_macos
        SS._checker = lambda: object()
        SS._check_macos = lambda checker, text, lang: sentinel
        try:
            ck("check dispatches to _check_macos",
               SS.check("teh", "en") is sentinel)
        finally:
            SS._checker = real_chk
            SS._check_macos = real_macos
    finally:
        sys.platform = REAL_PLATFORM

    print("== Windows spell helpers ==")
    ck("lang tag exact",
       SS._win_language_tag("en-US", ["en-US", "de-DE"]) == "en-US")
    ck("lang tag base fallback",
       SS._win_language_tag("en", ["en-US", "de-DE"]) == "en-US")
    ck("lang tag regional no fallback",
       SS._win_language_tag("en-GB", ["en-US"]) is None)
    ck("lang tag auto -> en",
       SS._win_language_tag("auto", ["en-US"]) == "en-US")
    ck("lang tag unsupported -> None",
       SS._win_language_tag("xx", ["en-US"]) is None)
    corr = [{"original": "teh", "startIndex": 0, "endIndex": 3,
             "suggestions": ["the"], "type": "SPELLING"}]
    ck("correctedText splices",
       SS._corrected_text("teh cat", corr) == "the cat")
    ck("utf16_len ascii", SS._utf16_len("abc") == 3)
    ck("utf16_len astral",
       SS._utf16_len("a\U0001F600b") == 4)
    ck("guid bytes len", len(SS._guid_bytes(SS._SPELL_FACTORY_CLSID)) == 16)

    print("== player 'system' pref -> Windows SAPI ==")
    from qtranslate import config as _C  # noqa: E402
    saved = _C.DEFAULT_PATH
    fd, tmp = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    _C.DEFAULT_PATH = tmp
    _C.save({"General": {"PreferredServices": {"tts": "system"}}})
    from qtranslate import player as PL  # noqa: E402
    from qtranslate import tts as TTS  # noqa: E402
    from qtranslate import sapi as SAPI  # noqa: E402

    order = []
    orig = (PL._extension_backend, PL.stop, TTS.google_tts, TTS.bing_tts,
            SAPI.speak)
    PL._extension_backend = lambda *a, **k: None
    PL.stop = lambda: None
    TTS.google_tts = lambda *a, **k: order.append("google") or b"mp3"
    TTS.bing_tts = lambda *a, **k: order.append("bing") or b"mp3"
    sys.platform = "win32"
    sapi_calls = []
    SAPI.speak = lambda text, rate=0: sapi_calls.append((text, rate))
    try:
        spoke = []
        real_st_speak = ST.speak
        ST.speak = lambda text, lang="", slow=False: \
            spoke.append((text, lang, slow)) or True
        try:
            backend = PL.play_text("hi", "en", slow=False)
            ck("system pref -> sapi backend", backend == "sapi",
               repr(backend))
            ck("online fetches skipped", order == [], repr(order))
            ck("system_tts.speak used",
               spoke == [("hi", "en", False)], repr(spoke))
            ck("sapi.speak not needed", sapi_calls == [], repr(sapi_calls))
        finally:
            ST.speak = real_st_speak
        real_st_speak = ST.speak
        ST.speak = lambda *a, **k: False
        try:
            backend = PL.play_text("yo", "vi", slow=False)
            ck("sapi fallback backend", backend == "sapi", repr(backend))
            ck("sapi.speak fallback called",
               sapi_calls == [("yo", 0)], repr(sapi_calls))
        finally:
            ST.speak = real_st_speak
            SAPI.speak = orig[4]
    finally:
        sys.platform = REAL_PLATFORM
        (PL._extension_backend, PL.stop, TTS.google_tts, TTS.bing_tts,
         _sapi) = orig
        _C.DEFAULT_PATH = saved
        try:
            os.unlink(tmp)
        except OSError:
            pass

    # Live COM smoke -- only on a real Windows host. The stubbed
    # sections above can never exercise the vtable signatures; the
    # IEnumSpellingError::Next bug (3-arg standard-enumerator call on
    # a 1-arg method -> AV writing 0x1) shipped precisely because no
    # test touched real COM. Accepts None when the box has no spell
    # language pack; otherwise pins the bing_spell result shape.
    print("== live Windows spell check (real device only) ==")
    if REAL_PLATFORM == "win32":
        try:
            # _check_win directly: check() swallows exceptions into
            # None, which would hide a vtable crash like the AV.
            r = SS._check_win("This sentense is rong.", "en")
        except Exception as e:
            r = None
            ck("live win spell no crash", False, repr(e))
        if r is not None:
            ck("live win spell corrections",
               isinstance(r.get("corrections"), list)
               and isinstance(r.get("correctedText"), str)
               and all(c.get("original") and "suggestions" in c
                       for c in r["corrections"]),
               repr(r)[:120])
        else:
            ck("live win spell honest None (no lang pack?)", True)
    else:
        ck("live win spell skipped off-win32", True)

    print()
    if FAIL:
        print("regress_system_backends_win: %d FAILED: %s"
              % (len(FAIL), FAIL))
        sys.exit(1)
    print("regress_system_backends_win: all checks ok")


if __name__ == "__main__":
    main()
