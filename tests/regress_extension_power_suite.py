"""The power_suite example must DO everything it claims.

The three earlier examples pin single plumbing paths; this suite loads
``examples/extensions/power_suite`` -- the all-capabilities worked
example -- through the REAL loader (``load_user_extensions``, the same
call ``main()`` makes) and then drives each capability through the call
path the app uses, not through the extension's own functions:

* provider: engine.translate serves a glossary hit; a MISS raises into
  ``Result.failures`` and the rigged next provider answers instead;
* workflow: the annotation lands on a finished translation;
* dictionary / tts / ocr / spell: the live ``*_EXT`` tables got the
  entries, in the shapes the hosts call;
* ui: the slots are registered -- the running hosts are pinned by
  ``regress_qt_extension_ui`` already -- and the popup body renders;
* theme: the manager holds the partial record and ``active_theme``
  resolves it;
* state: the persisted counter survives a reload, and the tray entry
  reports it;
* manifest: all eight capabilities declared are the eight registered.

Headless-safe: no network, no audio, no real Options.json writes (the
state file lands under a temp data dir via the loader's own import).
"""
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
# The example's strings are Vietnamese; this console is cp1252. Print-only.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


from qtranslate import engine, registry as RG          # noqa: E402
from qtranslate.extensions import load_user_extensions, \
    last_manager                                        # noqa: E402


def _raises(fn):
    try:
        fn()
        return False
    except Exception:                   # noqa: BLE001
        return True


EXAMPLE = os.path.join(ROOT, "examples", "extensions", "power_suite")
_TABLES = ("TRANSLATORS", "DICT_EXT", "TTS_EXT", "OCR_EXT", "SPELL_EXT",
           "WORKFLOW_EXT")
_ORIG = {t: dict(getattr(RG, t)) for t in _TABLES}

root = tempfile.mkdtemp(prefix="qt_power_")
try:
    # --- load the REAL example folder through the REAL loader ----------
    ext_dir = os.path.join(root, "extensions")
    os.makedirs(ext_dir)
    shutil.copytree(EXAMPLE, os.path.join(ext_dir, "power_suite"))

    # A rigged next-in-chain so the miss path proves the FALLBACK, not
    # an empty chain -- and the REAL built-ins are cleared first, or the
    # miss would fall through to actual google (a network call).
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS["builtin"] = lambda t, s, g: "BUILTIN:" + t
    RG.reset_router()

    report = load_user_extensions(extensions_dir=ext_dir)
    mine = [r for r in report if r.get("id") == "ext.examples.power_suite"]
    ck("the example loads through the real loader",
       mine and mine[0].get("status") == "loaded", str(report))

    man = json.load(open(os.path.join(EXAMPLE, "manifest.json"),
                         encoding="utf-8"))
    ck("the manifest declares all eight capabilities",
       sorted(man["capabilities"]) == sorted(
           ["provider", "dictionary", "tts", "ocr", "spell",
            "workflow", "theme", "ui"]), str(man["capabilities"]))
    ck("the manifest's sdk_version matches the host gate",
       man["sdk_version"].split(".")[0] == "1", man["sdk_version"])

    # --- provider: hit, and MISS-into-fallback -------------------------
    res = engine.translate("power.glossary", "Good Morning", "vi",
                           src="en")
    ck("a glossary hit serves through engine.translate",
       res.ok and "chào buổi sáng" in res.text, repr(res.text)[:80])
    ck("the engine names the extension as the provider used",
       res.provider_used == "power.glossary", repr(res.provider_used))

    res = engine.translate("power.glossary", "no such phrase", "vi",
                           src="en")
    ck("a glossary MISS is recorded as the extension's failure",
       any(getattr(f, "provider", None) == "power.glossary"
           for f in (res.failures or ())), repr(res)[:120])
    ck("the miss falls through: the rigged next provider ANSWERS",
       res.ok and res.provider_used == "builtin"
       and "BUILTIN:" in res.text, repr(res)[:120])

    # --- workflow: the annotation lands on a finished translation ------
    res = engine.translate("builtin", "one two three", "vi", src="en")
    ck("the workflow step annotates the finished translation",
       res.ok and "〔3 words, en->vi〕" in res.text, repr(res.text)[:100])

    # --- the live dispatch tables, in the shapes the hosts call --------
    ck("dictionary entry live", "power.glossary" in RG.DICT_EXT,
       str(sorted(RG.DICT_EXT)))
    ck("tts entry live", "power.beep" in RG.TTS_EXT,
       str(sorted(RG.TTS_EXT)))
    ck("ocr entry live", "power.ocr" in RG.OCR_EXT,
       str(sorted(RG.OCR_EXT)))
    ck("spell entry live", "power.spell" in RG.SPELL_EXT,
       str(sorted(RG.SPELL_EXT)))
    ck("workflow entry live", "power.annotate" in RG.WORKFLOW_EXT,
       str(sorted(RG.WORKFLOW_EXT)))

    ck("the dict fn returns native-like marked-up HTML",
       "glossary" in RG.DICT_EXT["power.glossary"](
           "good morning", "en", "vi"))
    ck("the tts fn is callable in the player's shape",
       RG.TTS_EXT["power.beep"]("hello", "en", slow=True) is None)
    ck("the ocr fn refuses without a key (error path visible)",
       _raises(lambda: RG.OCR_EXT["power.ocr"](b"png", "en", None)))
    ck("the spell fn returns native's suggest list shape",
       RG.SPELL_EXT["power.spell"]("helo", "en") == ["helo-ish"])

    # --- ui: the slots got the contributions, and the body renders -----
    mgr = last_manager()
    ck("the loader exposes the manager via last_manager", mgr is not None)
    slots = mgr.ui_slots
    entries = slots.entries("menu", "tray")
    ck("the tray slot got the example's entry",
       any(e.get("contribution") is not None for e in entries),
       str(entries)[:100])
    body = slots.winner("popup", "body")
    ck("the popup body slot has a winner",
       bool(body) and callable(body.get("contribution")), str(body)[:100])
    if body and callable(body.get("contribution")):
        out = body["contribution"]("src text", "RES", "en->vi")
        ck("the popup body renders source-pair-and-result",
           "RES" in out and "en->vi" in out, repr(out)[:100])
    ck("the top panel slot got the example's entry",
       bool(slots.entries("panel", "top")))

    # --- theme: the manager holds the PARTIAL record --------------------
    themes = mgr.themes()
    ck("the theme registered under the example's name",
       "power_dark" in themes, str(sorted(themes)))
    rec = mgr.active_theme("power_dark")
    ck("active_theme resolves the extension theme",
       rec is not None and "Common" in rec, str(rec)[:80])

    # --- state: the counter persists across a reload --------------------
    import importlib
    import qtranslate.config as config
    state_path = os.path.join(root, "data", "extensions",
                              "power_suite_state.json")
    # The example writes under app_data_dir(); for the test, exercise
    # the SAME functions the provider uses by pointing the module's
    # state path at the temp dir and driving them directly.
    import examples.extensions.power_suite.ext as ps
    ps._STATE_PATH = state_path
    ps.glossary_translate("good morning", "en", "vi")
    first = ps._load_state().get("lookups")
    ps.glossary_translate("thank you", "en", "vi")
    second = ps._load_state().get("lookups")
    ck("the state file counts lookups", second == first + 1,
       "%s -> %s" % (first, second))
    # corrupt the file: the extension must fail OPEN, not crash
    with open(state_path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    ck("a corrupt state file falls back to defaults",
       ps._load_state() == {"lookups": 0}, repr(ps._load_state()))
    ck("the provider still serves with corrupt state",
       "chào buổi sáng" in ps.glossary_translate("Good morning", "en",
                                                 "vi"))
    # the serve above re-persisted from the defaults: 0 + 1
    ck("the tray entry reports the re-persisted counter",
       "1 glossary lookups" in ps.tray_entry(), ps.tray_entry())
finally:
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
print("regress_extension_power_suite: all checks ok (%d assertions)" % n[0])
