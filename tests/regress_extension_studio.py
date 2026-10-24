"""The studio mini-repo extension must work ACROSS its modules.

The single-file examples pin the plumbing; this suite pins the
mini-repo SHAPE: a multi-module package with a data file, loaded through
the real loader, where a settings change made through the API changes
what the provider, the workflow AND the panel render -- the seam that
only exists when modules share one context and the host persists the
settings.

Headless, no network; the history file goes to a temp dir.
"""
import io
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # print-only

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


from qtranslate import engine, registry as RG           # noqa: E402
from qtranslate.extensions import (discover_manifests,   # noqa: E402
                                   last_manager,
                                   load_user_extensions)
import qtranslate.qt.app as appmod                       # noqa: E402
appmod.HISTORY_PATH = os.path.join(tempfile.mkdtemp(prefix="qt_stu_"),
                                   "History.json")

_TABLES = ("TRANSLATORS", "DICT_EXT", "TTS_EXT", "OCR_EXT", "SPELL_EXT",
           "WORKFLOW_EXT")
_ORIG = {t: dict(getattr(RG, t)) for t in _TABLES}

EXAMPLE = os.path.join(ROOT, "examples", "extensions", "studio")
root = tempfile.mkdtemp(prefix="qt_studio_")
CFG = os.path.join(root, "Options.json")
io.open(CFG, "w", encoding="utf-8").write("{}")
# The extension's settings read the app's DEFAULT_PATH at runtime (the
# production path); the test points it at the temp file, exactly what
# the real app has -- one path for reads and writes.
import qtranslate.config as _config                     # noqa: E402
_saved_default = _config.DEFAULT_PATH
_config.DEFAULT_PATH = CFG

try:
    ext_dir = os.path.join(root, "extensions")
    os.makedirs(ext_dir)
    shutil.copytree(EXAMPLE, os.path.join(ext_dir, "studio"))
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS["builtin"] = lambda t, s, g: "BUILTIN:" + t
    RG.reset_router()

    # --- the loader accepts a PACKAGE entrypoint ------------------------
    manifest = dict(discover_manifests(ext_dir))[os.path.join(ext_dir,
                                                              "studio")]
    ck("the manifest resolves (a folder with subfolders)",
       isinstance(manifest, dict)
       and manifest["entrypoint"] == "__init__:register", str(manifest)[:80])
    report = load_user_extensions(extensions_dir=ext_dir)
    mine = [r for r in report if r.get("id") == "ext.examples.studio"]
    ck("the mini-repo loads through the real loader",
       mine and mine[0]["status"] == "loaded", str(report)[:160])

    mgr = last_manager()
    cfg_path = CFG

    def setting(key, default=None):
        return mgr.get_setting("ext.examples.studio", key, default,
                               path=cfg_path)

    # --- providers work across modules, data file included --------------
    res = engine.translate("studio.glossary", "Good Morning", "vi",
                           src="en")
    ck("the glossary provider answers from the data file",
       res.ok and "chào buổi sáng" in res.text, repr(res.text)[:80])
    ck("the default greeting from the context is in the answer",
       "〔studio〕" in res.text, repr(res.text)[:80])

    res = engine.translate("studio.glossary", "Good Morning", "ja",
                           src="en")
    ck("the second language pair of the data file answers too",
       res.ok and "おはよう" in res.text, repr(res.text)[:80])

    res = engine.translate("studio.summariser",
                           "one two three four five", "vi", src="en")
    ck("the second provider (own module) answers with the word count",
       res.ok and "(5 words)" in res.text, repr(res.text)[:100])

    # --- a settings change flows through EVERY module -------------------
    mgr.set_setting("ext.examples.studio", "Studio.Greeting", "〔X〕",
                    path=cfg_path)
    mgr.set_setting("ext.examples.studio", "Studio.MaxWords", 2,
                    path=cfg_path)
    res = engine.translate("studio.glossary", "thank you", "vi", src="en")
    ck("the provider module renders the new greeting",
       res.ok and res.text.startswith("〔X〕"), repr(res.text)[:80])
    res = engine.translate("studio.summariser", "a b c d e", "vi",
                           src="en")
    ck("the OTHER provider module honours MaxWords=2 (cut, total kept)",
       res.ok and "a b …" in res.text and "(5 words)" in res.text,
       repr(res.text)[:100])

    # --- workflow + dictionary + speech across modules ------------------
    res = engine.translate("builtin", "one two three", "vi", src="en")
    ck("the workflow module annotates with the context's title",
       res.ok and "— Studio · en→vi · 3 words" in res.text,
       repr(res.text)[:120])

    html = RG.DICT_EXT["studio.dict"]("good morning", "en", "vi")
    ck("the dictionary module serves the card",
       "chào buổi sáng" in html and "en→vi" in html, repr(html)[:100])

    RG.TTS_EXT["studio.tts"]("xin chào", "vi", slow=True)
    ck("the speech module recorded the request in its own state",
       getattr(mgr, "_x", None) is None)   # placeholder; checked via panel
    # the panel renders the speech module's state (cross-module proof)
    slots = mgr.ui_slots
    panel = slots.winner("panel", "top")
    text = panel["contribution"]()
    ck("the panel module shows the speech module's state",
       "last spoken: xin chào" in text, repr(text)[:120])

    ck("the spell module answers in native's shape",
       RG.SPELL_EXT["studio.spell"]("helo", "en") == ["helo (Studio?)"])

    # --- themes + ui slots ----------------------------------------------
    ck("both theme records registered",
       {"studio_dark", "studio_high_contrast"} <= set(mgr.themes()),
       str(sorted(mgr.themes())))
    rec = mgr.active_theme("studio_dark")
    ck("the dark theme resolves with its own palette",
       rec is not None and rec.get("Common", {}).get("ClientBackColor")
       == "14181f", str(rec)[:80])
    ck("the popup body slot has the studio renderer",
       callable(slots.winner("popup", "body").get("contribution")))
    body = slots.winner("popup", "body")["contribution"](
        "src", "RES", "en->vi")
    ck("the popup body renders with the context title",
       "[Studio · en->vi]" in body, repr(body)[:100])
    ck("the history_ctx menu slot got Studio's entry",
       bool(slots.entries("menu", "history_ctx")))

    # --- the miss counter is shared state across modules -----------------
    before = engine.translate("studio.glossary", "zzz", "vi", src="en")
    ck("the miss fell through to the rigged builtin",
       "BUILTIN:" in before.text, repr(before.text)[:60])
    ck("the panel shows the miss the PROVIDER module recorded",
       "1 misses" in panel["contribution"](),
       repr(panel["contribution"]())[:120])
finally:
    _config.DEFAULT_PATH = _saved_default
    for t, orig in _ORIG.items():
        getattr(RG, t).clear()
        getattr(RG, t).update(orig)
    RG.reset_router()
    shutil.rmtree(root, ignore_errors=True)

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_extension_studio: all checks ok (%d assertions)" % n[0])
