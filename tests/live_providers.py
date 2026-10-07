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
    check("deepl.detect", lambda: d.detect_code("Hello world"))
    check("deepl.translate EN->VI", lambda: d.translate("Good morning", "EN", "VI"))
    check("baidu.detect", lambda: b.detect_code("Hello world"))
    check("baidu.suggest", lambda: b.suggest("Hello") and "suggest-entries")
    check("yandex.translate EN->RU", lambda: y.translate("Good morning", "en", "ru"))
    check("bing.translate EN->VI", lambda: bing_translate("Good morning", "en", "vi"))
    from qtranslate.services import youdao as yd
    check("youdao.translate_web EN->ZH", lambda: yd.translate_web("Good morning", "en", "zh-CHS"))
    check("youdao.dictionary", lambda: "results-contents" in yd.dictionary("hello")[0] and "dict-html")
    from qtranslate.services import naver as n
    check("naver.detect", lambda: n.detect_code("Hello world"))
    check("naver.translate EN->VI", lambda: n.translate("Hello world", "en", "vi")[0])
    check("naver.dict", lambda: len(n.dictionary_search("hello", "en", "ko").get("items", [])) > 0 and "dict-items")
    check("naver.tts", lambda: len(n.tts("Hello", "en")) > 1000 and "mp3-bytes")
    from qtranslate.services import dictionary as dd
    check("dict.oxford", lambda: dd.oxford_lookup("hello"))
    check("dict.lingvo", lambda: dd.lingvo_lookup("hello", "en", "ru"))
    check("dict.urban", lambda: dd.urban_lookup("hello"))
    check("dict.wikipedia", lambda: dd.wikipedia_lookup("hello", "en", "en"))
    check("dict.multitran", lambda: dd.multitran_lookup("hello", 1, 2))
    check("reverso.translate EN->FR",
          lambda: dd.reverso_translate("Hello world", "en", "fr"))
    check("dict.wordreference",
          lambda: dd.wordreference_lookup("hello", "en", "ru"))

    for name, status, detail in results:
        print(f"{status:8} {name:28} {detail}")
    fails = [r for r in results if r[1] != "LIVE-OK"]
    print(f"\n{len(results) - len(fails)}/{len(results)} live OK")
    return 1 if fails else 0


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    raise SystemExit(main())
