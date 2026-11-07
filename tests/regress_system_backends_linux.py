#!/usr/bin/env python3
"""Linux system TTS (eSpeak/eSpeak-NG + spd-say), spell (aspell -a)
and OCR (tesseract) dispatch checks.

Stubs ``sys.platform='linux'`` so the Linux branches run on macOS.
No real binary is ever executed: ``shutil.which`` and
``subprocess.run``/``subprocess.Popen`` are faked, and every missing
binary must degrade to an honest empty/None/False -- never a crash.
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
from qtranslate.services import ocr as OCR  # noqa: E402

REAL_PLATFORM = sys.platform

import shutil  # noqa: E402
import subprocess  # noqa: E402

REAL_WHICH = shutil.which
REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen

WHICH = {}          # name -> fake path (or None)
RUNS = []           # subprocess.run argv lists
POPENS = []         # subprocess.Popen argv lists


def fake_which(name, *a, **k):
    if name in WHICH:
        return WHICH[name]
    return None


class _Proc:
    def __init__(self, out=None, err=b"", rc=0, text_out=None):
        self.stdout = text_out if text_out is not None else (out or b"")
        self.stderr = err
        self.returncode = rc


def make_run(handler):
    """handler(argv, kwargs) -> _Proc."""
    def run(argv, *a, **k):
        RUNS.append(list(argv))
        return handler(list(argv), k)
    return run


class FakePopen:
    def __init__(self, cmd, *a, **k):
        self.cmd = list(cmd)
        POPENS.append(self.cmd)
        self.killed = False

    def wait(self, *a, **k):
        return 0

    def kill(self):
        self.killed = True


def fake_popen(cmd, *a, **k):
    return FakePopen(cmd, *a, **k)


ESPEAK_VOICES = """\
Pty Language Age/Gender VoiceName File Other Languages
 5 en-us M english-us en
 5 ar F arabic ar
xx bad line
"""

ASPELL_DICTS = "en\nen_US\npt_BR\nde\n"


def aspell_run(argv, kw):
    if "dump" in argv:
        return _Proc(text_out=ASPELL_DICTS)
    if "-a" in argv:
        data = kw.get("input") or b""
        line = data.decode("utf-8", "replace")
        if "teh" in line:
            return _Proc(out=b"@(#) Aspell 0.60.8\n& teh 1: the, ten\n")
        if "wrd" in line:
            return _Proc(out=b"@(#) Aspell 0.60.8\n& wrd 1: word\n")
        if "bad" in line:
            return _Proc(out=b"garbage no header\n", rc=0)
        return _Proc(out=b"@(#) Aspell 0.60.8\n*\n")
    raise AssertionError("unexpected argv %r" % (argv,))


def main():
    print("== system_tts Linux dispatch ==")
    WHICH.clear()
    WHICH.update({"espeak-ng": "/usr/bin/espeak-ng"})
    shutil.which = fake_which
    subprocess.run = make_run(lambda argv, kw: _Proc(
        text_out=ESPEAK_VOICES if "--voices" in argv else ""))
    sys.platform = "linux"
    try:
        ck("espeak-ng preferred",
           ST._espeak_exe() == "/usr/bin/espeak-ng")
        voices = ST.discover_voices()
        ck("espeak voices parsed",
           voices == [("english-us", "en-us"), ("arabic", "ar")],
           repr(voices))
        ck("no say subprocess",
           all("say" not in a[0] for a in RUNS), repr(RUNS))
        ck("linux preferred exact",
           ST.preferred_voice("en-us", voices) == "english-us")
        ck("linux preferred base lang",
           ST.preferred_voice("en", voices) == "english-us")
        ck("linux preferred ar",
           ST.preferred_voice("ar", voices) == "arabic")
        ck("linux auto -> None", ST.preferred_voice("auto", voices) is None)
    finally:
        pass
    # espeak fallback when espeak-ng absent
    WHICH.clear()
    WHICH.update({"espeak": "/usr/bin/espeak"})
    try:
        ck("espeak fallback", ST._espeak_exe() == "/usr/bin/espeak")
    finally:
        pass
    # nothing installed -> honest empty
    WHICH.clear()
    try:
        ck("no engine -> None exe", ST._espeak_exe() is None)
        ck("no engine -> [] voices", ST.discover_voices() == [])
    finally:
        pass

    print("== player._speak_linux ==")
    from qtranslate import player as PL  # noqa: E402
    WHICH.clear()
    WHICH.update({"espeak-ng": "/usr/bin/espeak-ng"})
    subprocess.Popen = fake_popen
    POPENS.clear()
    real_pv = ST.preferred_voice
    ST.preferred_voice = lambda lang="": (
        None if not lang or lang.lower() in ("auto", "autodetect")
        else "english-us")
    try:
        name = PL._speak_linux("hello", "en", slow=True)
        ck("espeak-ng spoke", name == "espeak-ng", repr(name))
        cmd = POPENS[-1]
        ck("voice flag", "-v" in cmd and "english-us" in cmd, repr(cmd))
        ck("slow rate", "-s" in cmd and "110" in cmd, repr(cmd))
        ck("text is argv tail", cmd[-1] == "hello", repr(cmd))
        name = PL._speak_linux("hi", "auto")
        ck("auto -> default voice (no -v)",
           POPENS[-1] == ["/usr/bin/espeak-ng", "-s", "175", "hi"],
           repr(POPENS[-1]))
    finally:
        ST.preferred_voice = real_pv
    # spd-say fallback when no espeak
    WHICH.clear()
    WHICH.update({"spd-say": "/usr/bin/spd-say"})
    POPENS.clear()
    try:
        name = PL._speak_linux("hola", "es-MX")
        ck("spd-say fallback", name == "spd-say", repr(name))
        ck("spd-say lang flag",
           POPENS[-1][:3] == ["/usr/bin/spd-say", "-l", "es-MX"],
           repr(POPENS[-1]))
    finally:
        pass
    # nothing installed -> None
    WHICH.clear()
    try:
        ck("no engine -> None", PL._speak_linux("x", "en") is None)
    finally:
        pass

    print("== player._play_mp3_bytes_linux ==")
    WHICH.clear()
    WHICH.update({"mpv": "/usr/bin/mpv"})
    POPENS.clear()
    try:
        name = PL._play_mp3_bytes_linux(b"mp3bytes", block=True)
        ck("mpv player name", name == "mpv", repr(name))
        cmd = POPENS[-1]
        ck("mpv argv", cmd[:4] == ["/usr/bin/mpv", "--no-video",
                                "--really-quiet", "--"], repr(cmd))
        ck("mp3 temp file", cmd[-1].endswith(".mp3"), repr(cmd))
    finally:
        pass
    WHICH.clear()  # no players at all
    try:
        try:
            PL._play_mp3_bytes_linux(b"x")
            ck("no player raises", False)
        except RuntimeError:
            ck("no player raises", True)
    finally:
        pass

    print("== play_text Linux dispatch ==")
    from qtranslate import config as _C  # noqa: E402
    from qtranslate import tts as TTS  # noqa: E402
    saved = _C.DEFAULT_PATH
    fd, tmp = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    _C.DEFAULT_PATH = tmp
    try:
        # "system" pref -> straight to offline speak
        _C.save({"General": {"PreferredServices": {"tts": "system"}}})
        order = []
        orig = (PL._extension_backend, PL.stop, TTS.google_tts,
                TTS.bing_tts)
        PL._extension_backend = lambda *a, **k: None
        PL.stop = lambda: None
        TTS.google_tts = lambda *a, **k: order.append("google") or b"m"
        TTS.bing_tts = lambda *a, **k: order.append("bing") or b"m"
        WHICH.clear()
        WHICH.update({"espeak": "/usr/bin/espeak"})
        POPENS.clear()
        try:
            backend = PL.play_text("hola", "es", slow=False)
            ck("system pref -> espeak backend", backend == "espeak",
               repr(backend))
            ck("online fetches skipped", order == [], repr(order))
            ck("espeak argv used",
               POPENS and POPENS[-1][0] == "/usr/bin/espeak",
               repr(POPENS))
        finally:
            (PL._extension_backend, PL.stop, TTS.google_tts,
             TTS.bing_tts) = orig
        # default pref -> online mp3 through a Linux player
        _C.save({})
        orig = (PL._extension_backend, PL.stop, TTS.google_tts,
                TTS.bing_tts)
        PL._extension_backend = lambda *a, **k: None
        PL.stop = lambda: None
        TTS.google_tts = lambda *a, **k: order.append("google") or b"m"
        TTS.bing_tts = lambda *a, **k: order.append("bing") or b"m"
        order.clear()
        WHICH.clear()
        WHICH.update({"ffplay": "/usr/bin/ffplay"})
        POPENS.clear()
        try:
            backend = PL.play_text("hi", "en", slow=False)
            ck("online -> ffplay backend", backend == "ffplay",
               repr(backend))
            ck("google fetch first", order == ["google"], repr(order))
            ck("ffplay argv",
               POPENS[-1][:2] == ["/usr/bin/ffplay", "-nodisp"],
               repr(POPENS))
        finally:
            (PL._extension_backend, PL.stop, TTS.google_tts,
             TTS.bing_tts) = orig
        # playback failure -> offline speak fallback
        orig = (PL._extension_backend, PL.stop, TTS.google_tts,
                TTS.bing_tts)
        PL._extension_backend = lambda *a, **k: None
        PL.stop = lambda: None
        TTS.google_tts = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("net down"))
        TTS.bing_tts = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("net down"))
        WHICH.clear()
        WHICH.update({"spd-say": "/usr/bin/spd-say"})
        POPENS.clear()
        try:
            backend = PL.play_text("yo", "vi", slow=False)
            ck("fetch fail -> spd-say", backend == "spd-say",
               repr(backend))
        finally:
            (PL._extension_backend, PL.stop, TTS.google_tts,
             TTS.bing_tts) = orig
        # nothing at all -> honest ""
        orig = (PL._extension_backend, PL.stop, TTS.google_tts,
                TTS.bing_tts)
        PL._extension_backend = lambda *a, **k: None
        PL.stop = lambda: None
        TTS.google_tts = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("net down"))
        TTS.bing_tts = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("net down"))
        WHICH.clear()
        try:
            backend = PL.play_text("yo", "vi", slow=False)
            ck("no engines -> empty backend", backend == "",
               repr(backend))
        finally:
            (PL._extension_backend, PL.stop, TTS.google_tts,
             TTS.bing_tts) = orig
    finally:
        _C.DEFAULT_PATH = saved
        try:
            os.unlink(tmp)
        except OSError:
            pass

    print("== system_spell Linux dispatch ==")
    ck("available on linux", SS.available() is True)
    sentinel = {"correctedText": "x", "corrections": []}
    real_chk = SS._check_linux
    SS._check_linux = lambda text, lang: sentinel
    try:
        ck("check dispatches to _check_linux",
           SS.check("teh", "en") is sentinel)
    finally:
        SS._check_linux = real_chk
    WHICH.clear()  # no aspell -> honest None
    try:
        ck("check None without aspell", SS.check("teh", "en") is None)
    finally:
        pass

    print("== aspell dictionary selection ==")
    dicts = {"en", "en_US", "pt_BR", "de"}
    ck("dict exact regional",
       SS._aspell_dict("en-US", dicts) == "en_US")
    ck("dict exact underscore",
       SS._aspell_dict("pt_BR", dicts) == "pt_BR")
    ck("dict base lang",
       SS._aspell_dict("de", dicts) == "de")
    ck("dict auto -> en",
       SS._aspell_dict("auto", dicts) == "en")
    ck("dict unsupported -> None",
       SS._aspell_dict("fr", dicts) is None)

    print("== _ispell_findings parsing ==")
    found = SS._ispell_findings(
        "teh cat wrd",
        "@(#) Aspell 0.60.8\n& teh 1: the, ten\n& wrd 9\n")
    ck("two findings", found is not None and len(found) == 2,
       repr(found))
    if found and len(found) == 2:
        ck("teh offsets", found[0]["startIndex"] == 0
           and found[0]["endIndex"] == 3, repr(found[0]))
        ck("teh suggestions", found[0]["suggestions"] == ["the", "ten"],
           repr(found[0]))
        ck("wrd offsets", found[1]["startIndex"] == 8
           and found[1]["endIndex"] == 11, repr(found[1]))
        ck("wrd no suggestions", found[1]["suggestions"] == [])
    ck("clean line -> []",
       SS._ispell_findings("the cat", "@(#) Aspell\n*\n") == [])
    ck("no header -> None",
       SS._ispell_findings("teh", "garbage\n") is None)
    ck("bad offset -> None",
       SS._ispell_findings("teh", "@(#) Aspell\n& teh 2: the\n")
       is None)
    # emoji: UTF-16 offset math like the other backends
    found = SS._ispell_findings("😀 teh", "@(#) Aspell\n& teh 4: the\n")
    ck("emoji utf16 offset",
       found is not None and found[0]["startIndex"] == 3
       and found[0]["endIndex"] == 6, repr(found))

    print("== _check_linux end-to-end (faked aspell) ==")
    WHICH.clear()
    WHICH.update({"aspell": "/usr/bin/aspell"})
    shutil.which = fake_which
    SS._ASPELL_DICTS = None
    subprocess.run = make_run(aspell_run)
    try:
        r = SS.check("teh cat\nwrd dog", "en")
        ck("returns dict", isinstance(r, dict), repr(r)[:100])
        if isinstance(r, dict):
            corr = r["corrections"]
            ck("two line findings", len(corr) == 2, repr(corr))
            ck("line2 offset shifted",
               corr[1]["startIndex"] == 8 and corr[1]["endIndex"] == 11,
               repr(corr))
            ck("correctedText",
               r["correctedText"] == "the cat\nword dog",
               repr(r["correctedText"]))
            ck("text over stdin not argv",
               all("teh cat" not in " ".join(a) for a in RUNS))
        ck("bad engine output -> None",
           SS.check("bad", "en") is None)
        # known dicts, unsupported language -> None (no aspell -a run)
        n_runs = len(RUNS)
        ck("unsupported lang -> None",
           SS.check("teh", "fr") is None)
        ck("no -a run for unsupported lang",
           len(RUNS) == n_runs, repr(RUNS[n_runs:]))
    finally:
        SS._ASPELL_DICTS = None

    print("== OCR Linux path ==")
    ck("vision stage None on linux",
       OCR._ocr_stage("vision", b"x", "eng", "k") is None)
    WHICH.clear()
    WHICH.update({"tesseract": "/usr/bin/tesseract"})
    subprocess.run = make_run(
        lambda argv, kw: _Proc(out=b"recognized text\n"))
    try:
        out = OCR._offline_ocr(b"pngbytes", "eng")
        ck("offline_ocr -> tesseract", out == "recognized text",
           repr(out))
        ck("tesseract argv",
           RUNS and RUNS[-1][:2] == ["/usr/bin/tesseract", "stdin"],
           repr(RUNS[-1] if RUNS else None))
    finally:
        pass
    WHICH.clear()  # no tesseract -> honest None
    try:
        ck("no tesseract -> None",
           OCR._tesseract_ocr(b"x", "eng") is None)
    finally:
        pass

    # restore everything
    sys.platform = REAL_PLATFORM
    shutil.which = REAL_WHICH
    subprocess.run = REAL_RUN
    subprocess.Popen = REAL_POPEN

    print()
    if FAIL:
        print("regress_system_backends_linux: %d FAILED: %s"
              % (len(FAIL), FAIL))
        sys.exit(1)
    print("regress_system_backends_linux: all checks ok")


if __name__ == "__main__":
    main()
