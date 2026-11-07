#!/usr/bin/env python3
"""system-services MacTtsBackend + VoiceLocaleMapper port:
`say -v ?` parsing, exact-then-language voice preference, auto/empty
-> system default."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAIL = []


def ck(name, cond, detail=""):
    if cond:
        print("  ok", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, detail)


from qtranslate.services import system_tts as ST  # noqa: E402

SAY_OUT = """\
Albert              en_US    # Hello! My name is Albert.
Bad parsing line without hash
Flo (English (US))  en_US    # Hello! My name is Flo.
Samantha            en_US    # Hello! My name is Samantha.
Eddy (German (Germany)) de_DE # Hallo! Ich heiße Eddy.
Linh                vi_VN    # Xin chào! Tôi là Linh.
Tingting            zh_CN    # 你好，我叫婷婷。
Meijia              zh_TW    # 你好，我叫美佳。
Kyoko               ja_JP    # こんにちは、京子です。
"""


def main():
    print("== voice line parsing ==")
    import subprocess
    real_run = subprocess.run

    class R:
        stdout = SAY_OUT

    subprocess.run = lambda *a, **k: R()
    try:
        voices = ST.discover_voices()
    finally:
        subprocess.run = real_run
    ck("voices parsed", len(voices) == 8, str(voices))
    ck("bad line skipped",
       all("without hash" not in v[0] for v in voices))
    ck("locale captured", ("Linh", "vi_VN") in voices, str(voices))

    print("== preferred_voice ==")
    ck("exact tag wins",
       ST.preferred_voice("vi_VN", voices) == "Linh")
    ck("language fallback",
       ST.preferred_voice("vi", voices) == "Linh")
    ck("zh-CN -> Simplified voice",
       ST.preferred_voice("zh-CN", voices) == "Tingting")
    ck("zh-TW -> Traditional voice",
       ST.preferred_voice("zh-TW", voices) == "Meijia")
    ck("case-insensitive",
       ST.preferred_voice("JA", voices) == "Kyoko")
    ck("underscore normalized",
       ST.preferred_voice("de-DE", voices) == "Eddy (German (Germany))")
    ck("auto -> None", ST.preferred_voice("auto", voices) is None)
    ck("empty -> None", ST.preferred_voice("", voices) is None)
    ck("unsupported -> None",
       ST.preferred_voice("xx", voices) is None)
    ck("empty voice list -> None",
       ST.preferred_voice("en", []) is None)

    print("== _speak_darwin wiring ==")
    from qtranslate import player
    import inspect
    src = inspect.getsource(player._speak_darwin)
    ck("voice flag wired", '"-v", voice' in src)
    ck("slow rate kept", '"-r", "120"' in src)
    ck("lang param", "lang: str" in src)

    print()
    if FAIL:
        print("regress_system_tts: %d FAILED: %s" % (len(FAIL), FAIL))
        sys.exit(1)
    print("regress_system_tts: all checks ok")


if __name__ == "__main__":
    main()
