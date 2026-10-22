"""The Options dialog (native DLG 154 and the nine page templates) on PySide6.

Every number here was MEASURED off the native captures in
``docs/review/native_screens``: 2135 (Internet), 2136 (Services), 2137
(Languages), 2138 (Appearance), 2139 (Exceptions), 2140 (Advanced), 2141
(Updates) and 2126 (Hotkeys, which is a 663x388 shot and so a different
size). The geometry is in ``qtranslate-pyside6-spec.md`` §5.

The behaviour is the port's: the same settings the tkinter front end
writes (``qtranslate.config``) are the ones this dialog shows, so the two
front ends agree on what the app is configured to do.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel

from qtranslate_style import ACCENT, DIM, TEXT, THUMB

from .widgets import (Base, LINK, button, check, combo, field, group, hline,
                      label, panel, put, rect, vline)

# The nine pages, in native's order. The Hotkeys page is the SECOND one
# (measured off the captures 2140/2141, not the order a reader would
# guess).
SIDEBAR = ["Basics", "Hotkeys", "Internet", "Services", "Languages",
           "Appearance", "Exceptions", "Advanced", "Updates"]

# The four columns of the Languages checklist, transcribed from the
# native capture 2137.
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
    "Russian Serbian Sinhala Slovak Slovenian Spanish Swedish Tajik Tamil "
    "Tatar Telugu Thai Turkish Ukrainian Urdu Uzbek Vietnamese",
]


class OptionsBase(Base):
    """The Options shell: the page list on the left, the page's body on
    the right, and the three buttons at the bottom."""

    ORIGIN, SIZE = (1, 26), (644, 362)
    SEL = 0

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("Options")
        self._shell()
        self.build()

    # ---------------------------------------------------------------- shell
    def _shell(self):
        # The page list: a bordered panel with one 13px row per page,
        # the current one filled in the accent colour.
        panel(self, 4, 29, 142, 324)
        for i, name in enumerate(SIDEBAR):
            sel = i == self.SEL
            q = QLabel(name)
            q.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            # No left padding: the text has to start one pixel inside the
            # row, the way native's does (MEASURED off the capture).
            q.setStyleSheet("QLabel{background:%s;color:%s;}"
                            % (ACCENT if sel else "transparent",
                               "#ffffff" if sel else TEXT))
            put(self, q, 6, 31 + 13 * i, 139, 13)
        # The rule above the buttons, and the buttons.
        hline(self, 358, 3, 639)
        button(self, 403, 363, 73, "OK")
        button(self, 484, 363, 73, "Cancel")
        button(self, 565, 363, 73, "Apply", enabled=False)

    def build(self):
        """The page's own body. Subclasses fill it in."""


class InternetPage(OptionsBase):
    SEL = 2

    def build(self):
        group(self, 152, 35, 484, 45, "Connection")
        label(self, 157, 59, "Timeout, sec:")
        combo(self, 455, 50, 175, "10")
        group(self, 152, 91, 484, 101, "Proxy")
        combo(self, 157, 105, 470, "Use system proxy settings")
        combo(self, 162, 134, 78, "HTTP", enabled=False)
        field(self, 248, 134, 277, 20, enabled=False)
        field(self, 532, 134, 95, 20, "0", enabled=False)
        field(self, 248, 160, 186, 20, enabled=False)
        field(self, 441, 160, 186, 20, enabled=False)


class ServicesPage(OptionsBase):
    SEL = 3

    def build(self):
        lst = panel(self, 155, 31, 481, 272)
        label(lst, 168, 41, "Translation", color="#005eb8")
        hline(lst, 43, 232, 608, "#b5c9e0")
        services = self.app.ordered_services()
        for i, name in enumerate(services):
            check(lst, 160, 63 + 18 * i, "", True, blue=True)
            label(lst, 193, 63 + 18 * i, self.app.service_display(name))
        label(lst, 168, 229, "Dictionary", color="#005eb8")
        hline(lst, 231, 232, 608, "#b5c9e0")
        for i, name in enumerate(self.app.dictionary_names()):
            check(lst, 160, 249 + 18 * i, "", True, blue=True)
            label(lst, 193, 249 + 18 * i, name)
        rect(lst, 626, 48, 2, 157, THUMB)
        button(self, 157, 309, 24, "▲", enabled=False)
        button(self, 187, 309, 24, "▼", enabled=False)
        button(self, 219, 309, 117, "Add dictionary…")
        b = button(self, 342, 309, 118, "Remove dictionary")
        b.setStyleSheet("color:%s" % DIM)


class LanguagesPage(OptionsBase):
    SEL = 4

    def build(self):
        lst = panel(self, 155, 31, 481, 272)
        for ci, col in enumerate(LANGUAGES):
            x = round(158 + ci * 126.5)
            for i, n in enumerate(col.split(" ")):
                check(lst, x, 39 + 14 * i, n.replace("_", " "), True, blue=True)
        rect(lst, 173, 293, 238, 2, THUMB)
        button(self, 155, 308, 481, "Check / Uncheck all")


class AppearancePage(OptionsBase):
    SEL = 5

    def build(self):
        group(self, 152, 35, 484, 56, "General")
        check(self, 160, 55, "Enable window style")
        label(self, 157, 77, "Theme:")
        combo(self, 397, 68, 233, "--- Default ---")
        group(self, 152, 98, 484, 226, "Popup window")
        for cy, t, on in [(122, "Enable auto size", 1),
                          (144, "Enable auto position", 1),
                          (167, "Activate when opened", 0),
                          (190, "Pin when dragging", 1)]:
            check(self, 160, cy, t, bool(on))
        label(self, 157, 213, "Auto-hide delay:")
        combo(self, 397, 204, 115, "5")
        label(self, 523, 213, "seconds")
        label(self, 157, 237, "Transparency (0 - 90):")
        field(self, 397, 227, 233, 20, "15")
        label(self, 157, 261, "Frame thickness:")
        combo(self, 397, 252, 233, "2")
        label(self, 157, 286, "Icons:")
        for i, g in enumerate(["▤", "∩", "⧉", "tā"]):
            b = button(self, 398 + 23 * i, 275, 22, g, 22)
            b.setStyleSheet("QPushButton{background:#c4c4c4;padding:0;}")
        label(self, 157, 313, "Background color:")
        label(self, 320, 313, "Text color:")
        label(self, 482, 313, "Frame color:")
        rect(self, 378, 305, 87, 17, "#000000")
        rect(self, 549, 305, 78, 17, "#5d6c7a")


class ExceptionsPage(OptionsBase):
    SEL = 6

    def build(self):
        combo(self, 155, 33, 481, "Disabled for these programs:")
        t = panel(self, 153, 60, 483, 221)
        label(t, 160, 72, "Program Name")
        label(t, 399, 72, "Window Class Name")
        rect(t, 393, 62, 1, 18, "#e5e5e5")
        exceptions = [("* All Programs *", c) for c in
                      ["SysListView32", "SysTreeView32", "ListBox", "ScrollBar",
                       "ComboBox", "msctls_hotkey32", "ConsoleWindowClass"]]
        exceptions.append(("mstsc.exe", "* All Windows *"))
        for i, (a, b) in enumerate(exceptions):
            label(t, 160, 92 + 17.6 * i, a)
            label(t, 399, 92 + 17.6 * i, b)
        button(self, 155, 288, 71, "Add")
        button(self, 234, 288, 72, "Modify")
        button(self, 314, 288, 72, "Delete")
        check(self, 154, 321, "Enable smart detection", True)


class AdvancedPage(OptionsBase):
    SEL = 7

    def build(self):
        group(self, 152, 35, 484, 180, "Advanced")
        for cy, t, v in [("56", "Default browser:", "Internet Explorer"),
                         ("80", "Copy action:", "Ctrl + C"),
                         ("104", "Keyboard layout indicator:", "None"),
                         ("128", "Preferred domain:", "com")]:
            label(self, 157, int(cy), t)
            combo(self, 455, int(cy) - 10, 175, v)
        check(self, 160, 154, "Enable GUI translation")
        check(self, 160, 177, "Enable listening to the same text at a slower speed", True)
        check(self, 160, 200, "Remove line breaks")
        group(self, 152, 224, 484, 61, "Mouse mode")
        check(self, 160, 244, "Enable mouse mode only when Ctrl is pressed")
        check(self, 160, 268, "Click on system tray icon switches mouse mode", True)
        group(self, 152, 295, 484, 55, "API keys")
        label(self, 157, 315, "OCR API key:")
        field(self, 387, 304, 243, 22)
        label(self, 157, 338, "Register here for free OCR API key",
              color=LINK, underline=True)


class UpdatesPage(OptionsBase):
    SEL = 8

    def build(self):
        check(self, 161, 44, "Automatically check for updates")
        panel(self, 153, 63, 481, 230)
        button(self, 524, 300, 110, "Check now")


class BasicsPage(OptionsBase):
    """The first page. The native capture of it was never taken, so this
    page is built from the settings the port supports, not from a
    measured picture."""

    SEL = 0

    def build(self):
        group(self, 152, 35, 484, 130, "General")
        check(self, 160, 55, "Start QTranslate with Windows", True)
        check(self, 160, 77, "Show tray icon", True)
        check(self, 160, 99, "Enable history", True)
        group(self, 152, 176, 484, 90, "Language")
        label(self, 157, 200, "Default source language:")
        combo(self, 455, 190, 175, "English")
        label(self, 157, 224, "Default target language:")
        combo(self, 455, 214, 175, "Vietnamese")


class HotkeysPage(Base):
    """The Hotkeys page. Its capture is 663x388, a different size from
    the other pages, so it does not use the shared shell."""

    ORIGIN, SIZE = (1, 24), (661, 363)
    SEL = 1

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("Options")
        panel(self, 10, 28, 142, 323)
        for i, name in enumerate(SIDEBAR):
            sel = i == self.SEL
            q = QLabel(name)
            q.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            # No left padding: the text has to start one pixel inside the
            # row, the way native's does (MEASURED off the capture).
            q.setStyleSheet("QLabel{background:%s;color:%s;}"
                            % (ACCENT if sel else "transparent",
                               "#ffffff" if sel else TEXT))
            put(self, q, 11, 28 + 13 * i, 140, 13)
        check(self, 159, 41, "Enable hotkeys", True)
        t = panel(self, 159, 60, 465, 251)
        label(t, 166, 71, "Action")
        label(t, 483, 71, "Hotkey")
        rect(t, 477, 62, 1, 247, "#e5e5e5")
        rows = [("Show main window", ""),
                ("Show popup window", "Ctrl + Q"),
                ("Show dictionary window", ""),
                ("Show history window", ""),
                ("Show keyboard window", ""),
                ("Listen to selected text", ""),
                ("Copy translation to clipboard", ""),
                ("Replace selected text", "Alt + W"),
                ("Switch mouse mode", ""),
                ("Translate clipboard content", ""),
                ("Translate clipboard in main window", ""),
                ("Translate clipboard in popup window", ""),
                ("Dictionary from clipboard", "")]
        for i, (a, k) in enumerate(rows):
            label(t, 166, 92 + 17 * i, a)
            if k:
                label(t, 483, 92 + 17 * i, k)
        rect(t, 629, 75, 2, 164, THUMB)
        button(self, 408, 361, 75, "OK")
        button(self, 489, 361, 75, "Cancel")
        button(self, 570, 361, 75, "Apply", enabled=False)
