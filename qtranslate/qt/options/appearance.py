"""The Appearance page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.

The four buttons of the "Icons:" row are ARTWORK, not font glyphs: the
native draws a small pictogram in each. The cells are recovered from the
capture (``assets/ui_icons/ap_icon1..4.png``) -- the button, its gradient
and the shadow the OS theme draws under it -- and a transparent button
sits over each one so the row is still clickable.

WIRED: every control reads/writes the ``Appearance`` section of
Options.json. ``PopupAutoPos``/``PopupAutoFocus``/``PopupTimeout``/
``Transparency`` are consumed live by ``qtranslate.qt.popup``; the theme
combo applies live through ``app.apply_theme``. The rest --
``PopupAutoSize``, ``PopupPinWhenDragging``,
``PopupWindowFrameThickness``, the three colour swatches and the
"Icons:" toggles -- persist correctly and are exposed to their
consumers through the ``qtranslate_style`` helpers
(``popup_auto_size``, ``popup_pin_when_dragging``,
``popup_frame_thickness``, ``popup_colors``, ``popup_icon_mask``);
``qtranslate.qt.popup`` is where they take effect.
"""

import os

from PySide6.QtWidgets import QColorDialog

from .base import OptionsBase, cfg_section, cfg_set, check, combo, \
    field, group, hline, label, notify_app, rect
from ..widgets import HEADING, HEADING_LINE, button


def _theme_names(app):
    """Built-in theme files plus extension-registered themes."""
    names = set()
    try:
        from qtranslate import theme as T
        # The bundled themes live beside the package assets; the
        # native's THEMES_DIR is a Windows path, so look there too.
        here = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))
        d = os.path.join(here, "qtranslate", "assets", "themes")
        names.update(T.list_themes(d))
    except Exception:
        pass
    try:
        mgr = getattr(app, "ext_manager", None)
        if mgr is not None:
            names.update(mgr.themes().keys())
    except Exception:
        pass
    return ["--- Default ---"] + sorted(names)


def _bgr(qcolor_int):
    """The settings file's colour int -> a QColor (0xBBGGRR order)."""
    from PySide6.QtGui import QColor
    v = int(qcolor_int or 0)
    return QColor(v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF)


def _to_int(qcolor):
    return (qcolor.blue() << 16) | (qcolor.green() << 8) | qcolor.red()


class AppearancePage(OptionsBase):
    SEL = 5
    # Grew for the port-owned "Image search"/"Interface" sections and
    # the close-on-outside-click checkbox below the measured popup
    # controls (.tmp PopupsPanel/AppearancePanel carry the same
    # settings next to the translate popup's).
    SIZE = (644, 536)
    CHROME = dict(OptionsBase.CHROME)
    CHROME["panel"] = (4, 29, 142, 498)
    CHROME["shadow_row"] = (3, 527, 144, 1)
    CHROME["rule"] = (532, 3, 638)
    CHROME["buttons"] = {k: (x, y + 174, w, sh)
                         for k, (x, y, w, sh)
                         in OptionsBase.CHROME["buttons"].items()}

    def build(self):
        ap = cfg_section("Appearance")
        group(self, 152, 35, 484, 58, "General")
        check(self, 159, 54, "Enable window style",
              bool(ap.get("EnableWindowStyle", False))
              ).toggled.connect(
            lambda v: cfg_set("Appearance", "EnableWindowStyle", bool(v)))
        label(self, 158, 77, "Theme:")
        names = _theme_names(self.app)
        cur = ap.get("ThemeName", "") or "--- Default ---"
        if cur not in names:
            names.insert(1, cur)
        c_theme = combo(self, 398, 67, 232, cur, values=names)
        c_theme.currentTextChanged.connect(
            lambda v: _theme_changed(self, v))

        group(self, 152, 100, 484, 229, "Popup window")
        for cy, t, key, default in [
                (121, "Enable auto size", "PopupAutoSize", True),
                (143, "Enable auto position", "PopupAutoPos", True),
                (166, "Activate when opened", "PopupAutoFocus", False),
                (189, "Pin when dragging", "PopupPinWhenDragging", True)]:
            check(self, 159, cy, t, bool(ap.get(key, default))
                  ).toggled.connect(
                lambda v, k=key: cfg_set("Appearance", k, bool(v)))
        label(self, 158, 212, "Auto-hide delay:")
        delays = ["0", "3", "5", "10", "15", "30"]
        cur_d = str(ap.get("PopupTimeout", 0))
        c_d = combo(self, 398, 204, 114,
                   cur_d if cur_d in delays else "5", values=delays)
        c_d.currentTextChanged.connect(
            lambda v: cfg_set("Appearance", "PopupTimeout",
                              int(v) if v.isdigit() else 0))
        label(self, 524, 212, "seconds")
        # The stored value is a 0-255 alpha (popup.py divides by 255),
        # NOT a percent -- the old "(0 - 90)" label invited values like
        # 15, which render as ~6% opacity (the audit's finding).
        label(self, 158, 235, "Transparency (0 - 255):")
        f_tr = field(self, 398, 226, 232, 22,
                     str(ap.get("Transparency", 217)))
        f_tr.editingFinished.connect(
            lambda: cfg_set("Appearance", "Transparency",
                            int(f_tr.text())
                            if f_tr.text().isdigit() else 217))
        label(self, 158, 258, "Frame thickness:")
        frames = ["1", "2", "3", "4"]
        cur_f = str(ap.get("PopupWindowFrameThickness", 2))
        c_f = combo(self, 398, 251, 232,
                   cur_f if cur_f in frames else "2", values=frames)
        c_f.currentTextChanged.connect(
            lambda v: cfg_set("Appearance", "PopupWindowFrameThickness",
                              int(v) if v.isdigit() else 2))
        label(self, 158, 284, "Icons:")
        # Native's row is four TOGGLE buttons (spec §5.4: "4 nút toggle
        # 22×22 đang nhấn"), one per popup header icon the user can
        # hide -- book, headphone, copy, transliteration (the star is
        # not toggleable). The stored Appearance.PopupIcons int is the
        # bitmask: bit 1..4 per icon, default 30 = all four shown.
        # qtranslate_style.popup_icon_mask() exposes it; the popup is
        # the pending consumer that hides the cleared icons.
        try:
            mask = int(ap.get("PopupIcons", 30))
        except Exception:
            mask = 30
        for i in range(4):
            x = 398 + 24 * i
            # The recovered cell artwork goes down FIRST: the module
            # docstring's "a transparent button sits over each one" is
            # the z-order. Creating the icon after the button painted
            # the artwork over it, hiding the state frame entirely.
            from ..widgets import icon
            icon(self, x, 274, "ui_icons", "ap_icon%d" % (i + 1))
            b = button(self, x, 274, 21, "", h=21)
            b.setObjectName("flat")
            b.setCheckable(True)
            bit = 1 << (i + 1)
            b.setChecked(bool(mask & bit))
            # The buttons are transparent overlays on the recovered
            # artwork; the accent frame is the on-state, since the
            # artwork PNG itself has no pressed look of its own. The
            # :checked selector -- not a build-time branch -- keeps the
            # frame in step with every later toggle.
            b.setStyleSheet(
                "QPushButton{border:1px solid transparent;"
                "background:transparent;padding:0;}"
                "QPushButton:checked{border:1px solid #0078d7;"
                "background:transparent;padding:0;}")
            b.toggled.connect(
                lambda on, k=i: _icon_toggled(self, k, on))
        # The three colour swatches: click opens the colour dialog and
        # stores the int the popup reads (ColorBack/ColorText/ColorFrame).
        label(self, 159, 312, "Background color:")
        label(self, 321, 312, "Text color:")
        label(self, 483, 312, "Frame color:")
        self._swatches = {}
        for x, w, key, default, rgb in [
                (379, 86, "ColorBack", 15790320, _bgr(ap.get(
                    "ColorBack", 15790320))),
                (549, 78, "ColorText", 0, _bgr(ap.get("ColorText", 0))),
                (627, 16, "ColorFrame", 8023133, _bgr(ap.get(
                    "ColorFrame", 8023133)))]:
            # The frame-color swatch runs off the client's right edge
            # in the native capture; the port draws the 16px that fits
            # (x 627 + 16 = 643 of the 644px client) so the setting is
            # actually reachable -- a zero-width rect was never created
            # at all (audit C2).
            r = rect(self, x, 304, w, 18, rgb.name())
            from PySide6.QtCore import Qt as _Qt
            r.setCursor(_Qt.PointingHandCursor)
            r.mousePressEvent = (lambda _e, k=key, wdg=r:
                                 _pick_color(self, k, wdg))
            self._swatches[key] = r

        # ---- Image search (.tmp PopupsPanel imageSearch* fields) ----
        # Port-owned: the Commons image-search dialog is a port feature,
        # so its automatic-position toggle and transparency percent
        # live here next to the translate popup's own transparency.
        from qtranslate.qt import image_search as _IS
        icfg = _IS._imgsearch_cfg()
        label(self, 167, 344, "Image search", color=HEADING, size=12)
        hline(self, 344, 330, 608, HEADING_LINE)
        cb_pos = check(self, 159, 362,
                       "Automatic window position",
                       bool(icfg.get("AutoPosition", True)), blue=True)
        cb_pos.toggled.connect(
            lambda v: _imgsearch_set("AutoPosition", bool(v)))
        try:
            pct = int(icfg.get("Transparency", 5))
        except Exception:
            pct = 5
        pct = max(5, min(50, pct))
        label(self, 158, 390, "Transparency (5 - 50 %):")
        vals = [str(v) for v in range(5, 51, 5)]
        c_tr = combo(self, 398, 382, 114, str(pct), values=vals)
        c_tr.activated.connect(
            lambda _i: _imgsearch_set(
                "Transparency", int(c_tr.currentText())))

        # .tmp closePopupsOnClickOutside (PopupsPanel): whether an
        # outside click dismisses the quick-translate popup. Default
        # on, matching upstream; the popup reads it live per click.
        ap_now = cfg_section("Appearance")
        cb_out = check(self, 159, 420,
                       "Close popup when clicking outside",
                       bool(ap_now.get("ClosePopupsOnClickOutside",
                                       True)), blue=True)
        cb_out.toggled.connect(
            lambda v: cfg_set("Appearance",
                              "ClosePopupsOnClickOutside", bool(v)))

        # .tmp AppearancePanel uiScale (JSpinner 75-300 step 25,
        # applied live via FlatLaf UIScale). Qt's equivalent is
        # QT_SCALE_FACTOR, which is read once at QApplication creation,
        # so the port applies it on the NEXT start -- the hint says so.
        label(self, 167, 446, "Interface", color=HEADING, size=12)
        hline(self, 446, 330, 608, HEADING_LINE)
        try:
            scale = int(ap_now.get("UiScale", 100))
        except Exception:
            scale = 100
        scale = max(75, min(300, scale))
        svals = [str(v) for v in range(75, 301, 25)]
        if str(scale) not in svals:
            svals.insert(0, str(scale))
        label(self, 158, 472, "UI scale:")
        c_scale = combo(self, 398, 464, 114, str(scale), values=svals)
        c_scale.activated.connect(
            lambda _i: cfg_set("Appearance", "UiScale",
                               int(c_scale.currentText())))
        label(self, 522, 472, "%  (applies after restart)",
              color="#777777")

        # .tmp AppearancePanel fonts_group: the editor font is separate
        # from the UI font (Basics page "Font name"/"Text size"). Empty
        # name inherits the UI font; Qt's own per-glyph fallback covers
        # upstream's editorFallbackFontConfig, so no third combo.
        try:
            from PySide6.QtGui import QFontDatabase
            families = sorted(QFontDatabase.families())
        except Exception:
            families = []
        cur_ef = (general.get("EditorFontName", "")
                  if (general := cfg_section("General")) else "") or ""
        ef_names = ["(inherit UI font)"] + (
            families if cur_ef in families or not cur_ef
            else [cur_ef] + families)
        label(self, 158, 500, "Editor font:")
        c_ef = combo(self, 398, 492, 232,
                     cur_ef if cur_ef in ef_names else ef_names[0],
                     values=ef_names)
        c_ef.currentTextChanged.connect(
            lambda v: cfg_set("General", "EditorFontName",
                              "" if v == ef_names[0] else v))
        label(self, 158, 524, "Editor text size:")
        esizes = [str(s) for s in (8, 9, 10, 11, 12, 13, 14, 15, 16,
                                   18, 20, 24, 28, 32)]
        try:
            cur_es = str(int(general.get("EditorTextSize", 0) or 0))
        except Exception:
            cur_es = "0"
        c_es = combo(self, 398, 516, 114,
                     cur_es if cur_es in esizes else "0", values=["0"] + esizes)
        c_es.currentTextChanged.connect(
            lambda v: cfg_set("General", "EditorTextSize",
                              int(v) if v.isdigit() and v != "0" else ""))
        label(self, 522, 524, "pt  (0 = inherit)", color="#777777")


def _imgsearch_set(key, value):
    """Write one ``ImageSearch`` key (the image-search dialog reads the
    section live on each open, so no restart or notify is needed)."""
    from qtranslate.qt import image_search as _IS
    _IS._imgsearch_save(**{key: value})


def _theme_changed(shell, name):
    cfg_set("Appearance", "ThemeName",
            "" if name == "--- Default ---" else name)
    notify_app(getattr(shell, "app", None))
    try:
        app = getattr(shell, "app", None)
        if app is not None and getattr(app, "apply_theme", None):
            app.apply_theme("" if name == "--- Default ---" else name)
    except Exception:
        pass


def _icon_toggled(shell, index, on):
    """Flip bit ``index + 1`` of Appearance.PopupIcons and persist."""
    try:
        mask = int(cfg_section("Appearance").get("PopupIcons", 30))
    except Exception:
        mask = 30
    bit = 1 << (index + 1)
    cfg_set("Appearance", "PopupIcons",
            (mask | bit) if on else (mask & ~bit))


def _pick_color(shell, key, swatch):
    cur = _bgr(cfg_section("Appearance").get(key, 0))
    c = QColorDialog.getColor(cur, shell)
    if not c.isValid():
        return
    cfg_set("Appearance", key, _to_int(c))
    swatch.setStyleSheet(
        "QFrame{background:%s;border:1px solid #999999;}" % c.name())
