"""Pin the .tmp serviceSelectorAppearance + toolbarVisibility port.

.tmp's LayoutPanel carries three settings the port now honours under
``General.*`` (qtranslate/config.py defaults, qtranslate/migrate.py
both directions, Options -> Basics "Toolbars"/"Service selector"
groups):

* ``serviceSelectorAppearance`` (ICONS_ONLY / ICONS_AND_TEXT /
  TEXT_ONLY) -- the provider strip's icon/text mix, applied to BOTH
  the main window's strip and the hover strip of the quick popup
  (TEXT_ONLY drops icons, ICONS_ONLY keeps the name only when the
  service has no icon -- .tmp rebuildClassic's own fallback).
* ``toolbarVisibility.isHistoryBarVisible`` /
  ``isLanguageBarVisible`` -- ``General.ShowHistoryBar`` hides the
  back/forward pair, ``General.ShowLanguageBar`` the whole tool row
  (.tmp's LanguageSelectionBar contents). ``isServicesPanelVisible``
  was already ``General.ShowServicesPane``.

Offscreen; the providers are rigged, so no network. The windows are
never shown, so visibility is asserted through ``isVisibleTo`` (the
hidden flag), not ``isVisible``.
"""
import os
import sys
import tempfile

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
from qtranslate import config as _CFG                    # noqa: E402

# Isolate from the developer's live Options.json.
_CFG.DEFAULT_PATH = os.path.join(tempfile.mkdtemp(prefix="qt-sel-"),
                                 "Options.json")


def _set(**general):
    cfg = _CFG.load() or {}
    cfg.setdefault("General", {}).update(general)
    _CFG.save(cfg)


def vis(w, top):
    try:
        return w.isVisibleTo(top)
    except Exception:
        return False


ck("default appearance is .tmp's ICONS_AND_TEXT",
   _CFG.service_selector_appearance() == "ICONS_AND_TEXT")
g = _CFG.default_config()["General"]
ck("defaults carry the three new keys",
   g.get("ShowHistoryBar") is True and g.get("ShowLanguageBar") is True
   and g.get("ServiceSelectorAppearance") == "ICONS_AND_TEXT")
_set(ServiceSelectorAppearance="bogus")
ck("bogus value falls back to ICONS_AND_TEXT",
   _CFG.service_selector_appearance() == "ICONS_AND_TEXT")
_set(ServiceSelectorAppearance="ICONS_AND_TEXT")

_ORIG = dict(RG.TRANSLATORS)
try:
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS["google"] = lambda t, s, g: "GOOGLE:" + t
    RG.TRANSLATORS["deepl"] = lambda t, s, g: "DEEPL:" + t
    RG.reset_router()

    from qtranslate.qt.app import QtApp               # noqa: E402
    from qtranslate.qt.main_window import MainWindow  # noqa: E402

    app = QtApp([])
    app._load_session()
    app.source, app.target = "en", "vi"
    app.win = MainWindow(app)
    win = app.win

    ck("the provider strip has cells", len(win._strip_cells) >= 2,
       str(len(win._strip_cells)))
    cells = [c for c in win._strip_cells if c[3]]
    ck("at least one cell has an icon", bool(cells))

    # ---- default: icons AND text -------------------------------------
    win.apply_pane_visibility()
    ck("default shows icons and labels",
       all(vis(ico, win) and vis(lab, win)
           for _b, ico, lab, _h in cells))

    # ---- TEXT_ONLY ----------------------------------------------------
    _set(ServiceSelectorAppearance="TEXT_ONLY")
    win.apply_pane_visibility()
    ck("TEXT_ONLY hides every icon, keeps labels",
       all(not vis(ico, win) and vis(lab, win)
           for _b, ico, lab, _h in cells))

    # ---- ICONS_ONLY ----------------------------------------------------
    _set(ServiceSelectorAppearance="ICONS_ONLY")
    win.apply_pane_visibility()
    ck("ICONS_ONLY hides labels on icon cells",
       all(vis(ico, win) and not vis(lab, win)
           for _b, ico, lab, h in cells if h))

    # ---- toolbarVisibility --------------------------------------------
    _set(ServiceSelectorAppearance="ICONS_AND_TEXT",
         ShowLanguageBar=False, ShowHistoryBar=False)
    win.apply_pane_visibility()
    ck("language bar off hides the tool row",
       not vis(win.cmb_src, win) and not vis(win.cmb_tgt, win)
       and not vis(win.btn_go, win) and not vis(win.btn_new, win)
       and not vis(win.btn_swap, win))
    ck("history bar off hides back/forward",
       not vis(win.btn_back, win) and not vis(win.btn_fwd, win))
    ck("source pane stays under ShowTopPane",
       vis(win.src, win))
    _set(ShowLanguageBar=True, ShowHistoryBar=True)
    win.apply_pane_visibility()
    ck("bars back on",
       vis(win.cmb_src, win) and vis(win.btn_back, win))

    # ShowServicesPane still gates the strip AND the appearance pass.
    _set(ShowServicesPane=False)
    win.apply_pane_visibility()
    ck("services pane off hides strip icons+labels too",
       all(not vis(ico, win) and not vis(lab, win)
           for _b, ico, lab, _h in win._strip_cells))
    _set(ShowServicesPane=True)
    win.apply_pane_visibility()

    # ---- the popup's hover strip honours the same key ------------------
    app.show_translation("hello world", "GOOGLE:hello world",
                         provider="google")
    popup = getattr(app, "_popup", None)
    ck("the popup exists", popup is not None)
    if popup is not None and popup._strip_icons:
        _set(ServiceSelectorAppearance="TEXT_ONLY")
        popup._set_hover(True)
        ck("popup TEXT_ONLY hides icons, keeps labels",
           all(not vis(ico, popup) and vis(lab, popup)
               for ico, lab in zip(popup._strip_icons,
                                   popup._strip_labels)))
        _set(ServiceSelectorAppearance="ICONS_ONLY")
        popup._set_hover(True)
        ck("popup ICONS_ONLY: label only where no icon",
           all(vis(lab, popup) == (not h)
               for lab, h in zip(popup._strip_labels,
                                 popup._strip_has_icon)))
        popup._set_hover(False)
        ck("hover off hides everything again",
           all(not vis(w, popup) for w in popup._strip_icons)
           and all(not vis(w, popup) for w in popup._strip_labels))
        _set(ServiceSelectorAppearance="ICONS_AND_TEXT")
finally:
    RG.TRANSLATORS.clear()
    RG.TRANSLATORS.update(_ORIG)
    RG.reset_router()

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print(" -", f)
    sys.exit(1)
print("PASS %d checks" % n[0])
