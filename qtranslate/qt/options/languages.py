"""The Languages page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.

The native's language list is a LISTVIEW with checkboxes, not a column of
checkbox widgets: the boxes are 12x13, sit ON the panel's left border and
are drawn by the OS theme. The exact sprite is recovered from the capture
(``assets/ui_icons/check_blue.png``) and the words are separate labels, so
the box and the word land on the native's pixels.

WIRED: clicking a language toggles it in ``DisabledLanguages`` (the
unchecked state dims the word, since the capture only ships the checked
sprite); "Check / Uncheck all" flips the whole list. ``build`` runs on
the shell instance, so the toggles are module functions reading state
off the shell (``_lang_disabled`` / ``_lang_labels``).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from .base import OptionsBase, cfg_load, button, icon, label, panel, rect
from qtranslate_style import DIM, TEXT, THUMB

# The native's list, in the native's columns. "Swahili" is between
# "Spanish" and "Swedish" -- the list is alphabetical and the capture
# shows all eighteen of the last column.
LANGUAGES = [
    "Afrikaans Albanian Arabic Armenian Azerbaijani Basque Belarusian "
    "Bengali Bulgarian Catalan Chinese_(Simplified) "
    "Chinese_(Traditional) Croatian Czech Danish Dutch English Esperanto",
    "Estonian Filipino Finnish French Galician Georgian German Greek "
    "Haitian_Creole Hebrew Hindi Hmong Hungarian Icelandic Indonesian "
    "Irish Italian Japanese",
    "Kannada Kazakh Khmer Korean Lao Latin Latvian Lithuanian Macedonian "
    "Malay Maltese Marathi Mongolian Norwegian Persian Polish Portuguese "
    "Romanian",
    "Russian Serbian Sinhala Slovak Slovenian Spanish Swahili Swedish "
    "Tajik Tamil Tatar Telugu Thai Turkish Ukrainian Urdu Uzbek Vietnamese",
]


def _display_name(raw):
    return raw.replace("_", " ")


def _all_names():
    return [_display_name(n) for col in LANGUAGES for n in col.split(" ")]


def _persist(shell):
    from qtranslate import config as _C
    try:
        cfg = _C.load() or {}
        cfg["DisabledLanguages"] = sorted(shell._lang_disabled)
        _C.save(cfg)
    except Exception:
        pass


def _repaint(shell):
    for name, lab in (getattr(shell, "_lang_labels", {}) or {}).items():
        try:
            lab.setStyleSheet(
                "QLabel{background:transparent;color:%s;}"
                % (TEXT if name not in shell._lang_disabled else DIM))
        except Exception:
            pass


def _toggle(shell, name):
    if name in shell._lang_disabled:
        shell._lang_disabled.discard(name)
    else:
        shell._lang_disabled.add(name)
    _persist(shell)
    _repaint(shell)


def _toggle_all(shell):
    if len(shell._lang_disabled) >= len(_all_names()) // 2:
        shell._lang_disabled = set()
    else:
        shell._lang_disabled = set(_all_names())
    _persist(shell)
    _repaint(shell)


class _LangCell(QWidget):
    """One language row: click toggles enabled/disabled."""

    def __init__(self, shell, name):
        super().__init__(shell)
        self.shell = shell
        self.name = name

    def mousePressEvent(self, _e):
        _toggle(self.shell, self.name)


class LanguagesPage(OptionsBase):
    SEL = 4

    # MEASURED off capture 2137: the first box's top-left is at screen
    # (156, 33), the columns are 127px apart, the rows 14px, and each
    # word starts 18px after its box.
    BOX_X, BOX_Y = 156, 33
    COL_STEP, ROW_STEP = 127, 14
    TEXT_DX, TEXT_DY = 18, 6

    def build(self):
        cfg = cfg_load() or {}
        self._lang_disabled = set(cfg.get("DisabledLanguages", []) or [])
        self._lang_labels = {}
        lst = panel(self, 155, 31, 481, 272)
        for ci, col in enumerate(LANGUAGES):
            x = self.BOX_X + self.COL_STEP * ci
            for i, n in enumerate(col.split(" ")):
                name = _display_name(n)
                icon(lst, x, self.BOX_Y + self.ROW_STEP * i,
                     "ui_icons", "check_blue")
                lab = label(lst, x + self.TEXT_DX,
                            self.BOX_Y + self.TEXT_DY + self.ROW_STEP * i,
                            name,
                            color=TEXT
                            if name not in self._lang_disabled else DIM)
                # A click target over the box+word, in the panel's own
                # coordinates (the panel's _abs is its screenshot pos).
                cell = _LangCell(self, name)
                cell.setParent(lst)
                cell.setGeometry(x - lst._abs[0] - 4,
                                 self.BOX_Y + self.ROW_STEP * i
                                 - lst._abs[1] - 4, 110, 18)
                cell.show()
                self._lang_labels[name] = lab
        # The list's horizontal scrollbar: the thumb is 267px long.
        rect(lst, 173, 293, 267, 2, THUMB)
        b = button(self, 155, 308, 481, "Check / Uncheck all")
        b.clicked.connect(lambda: _toggle_all(self))
