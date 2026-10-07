"""Live provider verification (hits real endpoints). Run: python -I tests/live_providers.py.
Results recorded 2026-10-07, see tests/LIVE_RESULTS.md."""
import sys

sys.path.insert(0, ".")

results = []


def check(name, fn):
    try:
        out = fn()
        ok = bool(out)
        results.append((name, "LIVE-OK" if ok else "EMPTY", str(out)[:80]))
    except Exception as e:
        results.append((name, "DEAD", f"{type(e).__name__}: {e}"[:100]))


def main():
    from qtranslate.services import google_translate as g
    from qtranslate.services import deepl as d
    from qtranslate.services import baidu as b
    from qtranslate.services import yandex as y
    from qtranslate.session import bing_translate
    from qtranslate import tts

    check("google.translate EN->VI", lambda: g.translate("Good morning", "auto", "vi"))
    check("google.tts", lambda: len(tts.google_tts("Xin chào", "vi")) > 1000 and "mp3-bytes")
    check("deepl.detect", lambda: d.detect("Hello world"))
    check("deepl.translate EN->VI", lambda: d.translate("Good morning", "EN", "VI"))
    check("baidu.detect", lambda: b.detect("Hello world"))
    check("yandex.translate EN->RU", lambda: y.translate("Good morning", "en", "ru"))
    check("bing.translate EN->VI", lambda: bing_translate("Good morning", "en", "vi"))

    for name, status, detail in results:
        print(f"{status:8} {name:28} {detail}")
    fails = [r for r in results if r[1] != "LIVE-OK"]
    print(f"\n{len(results) - len(fails)}/{len(results)} live OK")
    return 1 if fails else 0


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    raise SystemExit(main())
