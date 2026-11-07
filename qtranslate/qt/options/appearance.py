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
    field, group, label, notify_app, rect
from ..widgets import button


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
        label(self, 158, 235, "Transparency (0 - 90):")
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
            b = button(self, x, 274, 21, "", h=21)
            b.setObjectName("flat")
            b.setCheckable(True)
            bit = 1 << (i + 1)
            b.setChecked(bool(mask & bit))
            # The buttons are transparent overlays on the recovered
            # artwork; the accent frame is the on-state, since the
            # artwork PNG itself has no pressed look of its own.
            b.setStyleSheet(
                "QPushButton{border:none;background:transparent;padding:0;}"
                if not (mask & bit) else
                "QPushButton{border:1px solid #0078d7;background:transparent;"
                "padding:0;}")
            b.toggled.connect(
                lambda on, k=i: _icon_toggled(self, k, on))
            from ..widgets import icon
            icon(self, x, 274, "ui_icons", "ap_icon%d" % (i + 1))
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
