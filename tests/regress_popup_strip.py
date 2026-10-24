"""Clicking the popup's provider strip must select AND re-translate.

The operator's report (2026-10-24, with the capture 2164 attached):
clicking a provider cell in the popup's strip did NOTHING -- no active
highlight, no switch. The cells are clickable now: a click switches the
app's service, paints the active cell in the selection blue (ACCENT,
like the main window's listbox) with white text, and re-translates the
popup's source through the chosen provider on the app's WORKER (the
same one-request-at-a-time rule as on_go). A translation that arrives
from any other path re-points the highlight at the serving provider.

Offscreen; the providers are rigged, so no network.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


from qtranslate import registry as RG                    # noqa: E402
from qtranslate_style import ACCENT                      # noqa: E402
from qtranslate.qt.app import QtApp                      # noqa: E402
from qtranslate.qt.main_window import MainWindow         # noqa: E402

_ORIG = dict(RG.TRANSLATORS)
try:
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS["google"] = lambda t, s, g: "GOOGLE:" + t
    RG.TRANSLATORS["deepl"] = lambda t, s, g: "DEEPL:" + t
    RG.reset_router()

    app = QtApp([])
    app._load_session()
    app.source, app.target = "en", "vi"
    app.win = MainWindow(app)
    app.service = "google"

    app.show_translation("hello world", "GOOGLE:hello world",
                         provider="google")
    popup = getattr(app, "_popup", None)
    ck("the popup exists after show_translation", popup is not None)
    if popup is None:
        raise SystemExit(1)
    app.qapp.processEvents()

    ck("the strip lists the rigged providers",
       set(popup._strip_names) == {"google", "deepl"},
       str(popup._strip_names))
    ck("the active cell starts as the serving provider",
       popup._strip_names[popup._strip_buttons.index(
           popup._strip_buttons[0])] == "google"
       and "0078d7" in popup._strip_buttons[0].styleSheet(),
       popup._strip_buttons[0].styleSheet()[:80])
    ck("the inactive cell is not blue",
       "0078d7" not in popup._strip_buttons[1].styleSheet(),
       popup._strip_buttons[1].styleSheet()[:80])

    # --- the click: switch, highlight, re-translate --------------------
    popup._source_text = "hello world"
    popup._strip_clicked("deepl")
    ck("the click switches the app's service",
       app.service == "deepl", app.service)
    ck("the clicked cell is highlighted in the selection blue",
       "background:%s" % ACCENT in popup._strip_buttons[1].styleSheet()
       and "0078d7" not in popup._strip_buttons[0].styleSheet(),
       popup._strip_buttons[1].styleSheet()[:80])
    ck("the active label turns white",
       "#ffffff" in popup._strip_labels[1].styleSheet(),
       popup._strip_labels[1].styleSheet()[:60])

    ok = app.wait_for_translation(timeout=10.0)
    app.qapp.processEvents()
    ck("the re-translation lands in the popup",
       ok and "DEEPL:hello world"
       in popup.lbl_text.text(),
       popup.lbl_text.text()[:60])
    ck("the highlight still names the provider that answered",
       "background:%s" % ACCENT in popup._strip_buttons[1].styleSheet())

    # a translation from ANOTHER path re-points the highlight
    app.show_translation("hello world", "GOOGLE:again", provider="google")
    app.qapp.processEvents()
    popup = app._popup          # show_translation builds a fresh popup
    ck("a later translation re-points the highlight at its provider",
       "background:%s" % ACCENT in popup._strip_buttons[0].styleSheet()
       and "0078d7" not in popup._strip_buttons[1].styleSheet())

    popup.close()
    app.win.close()
finally:
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS.update(_ORIG)
    RG.reset_router()

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_popup_strip: all checks ok (%d assertions)" % n[0])
