"""The Comparison page of the Options dialog.

A port-owned page (like Extensions): native 6.10 has no comparison
feature, and .tmp manages comparison translators through service
presets the port does not have -- so the flat equivalent is a
checklist of the enabled translation services. The checked set lands
in ``General.ComparisonServices``; the app re-translates the source
through each of them in parallel and shows the rows in the main
window's extra pane ("Compare" mode).
"""

from .base import OptionsBase, check, hline, label, panel, put, rect
from ..widgets import HEADING, HEADING_LINE
from qtranslate_style import DIM, FACE


def _comparison_services():
    try:
        from qtranslate import config as _C
        v = ((_C.load() or {}).get("General", {}) or {}
             ).get("ComparisonServices")
        if isinstance(v, str):
            v = [s for s in v.replace("|", ",").split(",") if s.strip()]
        return {str(s).strip() for s in (v or []) if str(s).strip()}
    except Exception:
        return set()


def _persist(shell):
    from qtranslate import config as _C
    try:
        cfg = _C.load() or {}
        cfg.setdefault("General", {})["ComparisonServices"] = sorted(
            getattr(shell, "_compare_checked", set()))
        _C.save(cfg)
    except Exception:
        pass


class ComparisonPage(OptionsBase):
    SEL = 10

    def build(self):
        lst = panel(self, 155, 31, 481, 272)
        rect(lst, 619, 32, 16, 270, FACE)
        label(lst, 167, 42, "Compare with", color=HEADING, size=12)
        hline(lst, 42, 320, 608, HEADING_LINE)

        checked = _comparison_services()
        self._compare_checked = set(checked)
        app = getattr(self, "app", None)
        try:
            svcs = list(app.ordered_services()) if app else []
        except Exception:
            svcs = []
        if not svcs:
            label(lst, 167, 60, "No translation services enabled.",
                  color=DIM)
            return
        y = 58
        for svc in svcs:
            name = svc
            try:
                name = app.service_display(svc)
            except Exception:
                pass
            on = svc in checked
            cb = check(lst, 167, y + 8, name, on=on, blue=True)
            cb.stateChanged.connect(
                lambda st, s=svc: _toggle(self, s, bool(st)))
            y += 20
            if y > 280:
                break
        from PySide6.QtWidgets import QLabel
        hint = QLabel(
            "Checked services re-translate every main-window "
            "translation; answers show in the Compare pane.")
        hint.setStyleSheet("QLabel{color:%s;}" % DIM)
        hint.setWordWrap(True)
        put(self, hint, 155, 310, 481, 22)


def _toggle(shell, svc, on):
    if on:
        shell._compare_checked.add(svc)
    else:
        shell._compare_checked.discard(svc)
    _persist(shell)
