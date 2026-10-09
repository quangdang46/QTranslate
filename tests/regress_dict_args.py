"""Regression: dictionary call-site argument pass-through (native-faithful).

Guards two fixes against native evidence:

1. Multitran URI/codes — native buildUri() is
   ``/m.exe?l1=codeFromLanguage(target)&l2=codeFromLanguage(source)&s=word``
   (l1 = TARGET, l2 = SOURCE; numeric codes from SupportedLanguages). The port
   previously hard-coded ``multitran_lookup(w, 1, 2)`` at the call site, which
   pinned every lookup to Ru->En regardless of the selected pair.
2. App DICTS call site must pass the selected (sl, tl) through, not constants.

Offline only (no network).
"""
import sys

sys.path.insert(0, "C:/Users/ADMIN/qtranslate-re")

from qtranslate.services import dictionary as d  # noqa: E402

failures = []


def check(name, cond, detail=""):
    if not cond:
        failures.append("%s%s" % (name, (" -- " + detail) if detail else ""))


# ---- Multitran codes: ISO in, native numeric code out --------------------
# en->1, ru->2, de->3, fr->4, uk->33 (from SupportedLanguages indexing).
ui = "en"  # non-ru UI => SHL=1 appended
u = d.multitran_build_uri("hello", "en", "ru", ui_lang=ui)
check("mt en->ru l1=2(target ru) l2=1(source en)",
      "l1=2" in u and "l2=1" in u and "s=hello" in u, u)

u = d.multitran_build_uri("hello", "ru", "en", ui_lang=ui)
check("mt ru->en l1=1 l2=2", "l1=1" in u and "l2=2" in u, u)

u = d.multitran_build_uri("x", "de", "fr", ui_lang=ui)
check("mt de->fr l1=4(fr) l2=3(de)", "l1=4" in u and "l2=3" in u, u)

# ---- Numeric (native-style) args still interpreted as SOURCE/TARGET ------
u = d.multitran_build_uri("hello", 1, 2, ui_lang=ui)  # sl=1(en), tl=2(ru)
check("mt numeric (1,2) => l1=2 l2=1 (source=1,target=2)",
      "l1=2" in u and "l2=1" in u, u)

# ---- SHL only when UI lang != ru ----------------------------------------
check("mt SHL present for non-ru UI", "SHL=1" in d.multitran_build_uri(
    "x", "en", "ru", ui_lang="en"))
check("mt SHL absent for ru UI", "SHL" not in d.multitran_build_uri(
    "x", "en", "ru", ui_lang="ru"))

# ---- Unsupported language is passed through, not invented ---------------
u = d.multitran_build_uri("x", "vi", "en", ui_lang=ui)  # vi has MT code None
check("mt unsupported lang passed through (no crash, no fake code)",
      "l1=1" in u and "l2=vi" in u, u)

# ---- App call site must forward (sl, tl), not hard-code (1, 2) ----------
import inspect  # noqa: E402

# qtranslate.app imports tkinter etc.; guard so this passes headless.
try:
    import qtranslate.app as app  # noqa: E402
    src = inspect.getsource(app)
    check("app DICTS multitran forwards sl,tl (no hard-coded 1,2)",
          "_dict.multitran_lookup(w, sl, tl)" in src
          and "_dict.multitran_lookup(w, 1, 2)" not in src)
except Exception as e:  # pragma: no cover - environment dependent
    check("app import for call-site check", False, repr(e))

if failures:
    raise SystemExit("FAIL:\n  " + "\n  ".join(failures))
print("OK: multitran args + call-site pass-through")
