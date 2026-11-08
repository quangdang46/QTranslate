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
    check("youdao.dictionary",
          lambda: (lambda r: r and r[0] and len(r[0]) > 1000
                   and "dict-html")(yd.dictionary("hello")))
    from qtranslate.services import naver as n
    check("naver.detect", lambda: n.detect_code("Hello world"))
    check("naver.translate EN->VI",
          lambda: (n.translate("Hello world", "en", "vi") or [""])[0])
    check("naver.dict",
          lambda: len(((n.dictionary_search("hello", "en", "ko")
                        or {}).get("items")) or []) > 0
          and "dict-items")
    check("naver.tts", lambda: len(n.tts("Hello", "en")) > 1000 and "mp3-bytes")
    from qtranslate.services import dictionary as dd
    check("dict.oxford", lambda: dd.oxford_lookup("hello"))
    check("dict.lingvo", lambda: dd.lingvo_lookup("hello", "en", "ru"))
    check("dict.urban", lambda: dd.urban_lookup("hello"))
    check("dict.wikipedia", lambda: dd.wikipedia_lookup("hello", "en", "en"))
    check("dict.multitran", lambda: dd.multitran_lookup("hello", 1, 2))
    check("reverso.translate EN->FR",
          lambda: dd.reverso_translate("Hello world", "en", "fr"))
    check("reverso.lookup idx-pair",
          lambda: dd.reverso_lookup("hello", 17, 21))
    check("dict.wordreference",
          lambda: dd.wordreference_lookup("hello", "en", "ru"))
    # Registered providers the original sweep did not cover: the
    # extension-plugin ports (mymemory/mozhi/yandex_web) and the
    # keyless Wikimedia Commons image backend.
    from qtranslate.services import mymemory as mm
    check("mymemory.translate EN->VI",
          lambda: mm.translate("Hello world", "en", "vi"))
    from qtranslate.services import mozhi as mz
    check("mozhi.translate EN->VI",
          lambda: mz.translate("Hello world", "en", "vi"))
    from qtranslate.services import yandex_web as yw
    check("yandex_web.translate EN->VI",
          lambda: yw.translate("Hello world", "en", "vi"))
    from qtranslate.services import commons_images as ci
    check("commons_images.search",
          lambda: ci.search_images("cat", limit=3) and "thumb-results")
    # Spell backends (keyless): google spell-check, google suggest,
    # yandex speller.
    from qtranslate.services import google_spell as gs
    check("google_spell.check",
          lambda: (gs.check("This sentense has wurds", "en")
                   or {}).get("corrections"))
    from qtranslate.services import spell as sp
    check("spell.google_suggest",
          lambda: sp.google_suggest("wrold", "en"))
    check("spell.yandex_spell",
          lambda: sp.yandex_spell("wrold", "en"))
    # The registered "reverso" TRANSLATE provider (services/reverso.py,
    # distinct from dictionary.reverso_translate above) and the
    # extension-port Google dictionary card.
    from qtranslate.services import reverso as rv
    check("reverso.svc.translate EN->FR",
          lambda: rv.translate("Hello world", "en", "fr"))
    from qtranslate.services import google_dict as gd
    check("google_dict.lookup",
          lambda: gd.lookup("hello", "en"))

    for name, status, detail in results:
        print(f"{status:8} {name:28} {detail}")
    fails = [r for r in results if r[1] != "LIVE-OK"]
    print(f"\n{len(results) - len(fails)}/{len(results)} live OK")
    return 1 if fails else 0


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    raise SystemExit(main())
