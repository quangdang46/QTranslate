"""The Options dialog (native DLG 154 and the nine page templates) on PySide6.

Every number in the pages was MEASURED off the native captures in
``docs/review/native_screens``: 2135 (Internet), 2136 (Services), 2137
(Languages), 2138 (Appearance), 2139 (Exceptions), 2140 (Advanced), 2141
(Updates) and 2126 (Hotkeys, which is a 663x388 shot and so a different
size). The geometry is in ``qtranslate-pyside6-spec.md`` section 5.

Each page is its own module so one page can be measured and fixed
without touching the others.
"""
from .advanced import AdvancedPage
from .appearance import AppearancePage
from .base import PAGES
from .basics import BasicsPage
from .exceptions import ExceptionsPage
from .hotkeys import HotkeysPage
from .internet import InternetPage
from .languages import LanguagesPage
from .services import ServicesPage
from .updates import UpdatesPage

# The sidebar's click-through table: SIDEBAR name -> page class, so
# OptionsBase._goto can open any OTHER page without importing all nine
# of its siblings itself.
PAGES.update({
    "Basics": BasicsPage, "Hotkeys": HotkeysPage, "Internet": InternetPage,
    "Services": ServicesPage, "Languages": LanguagesPage,
    "Appearance": AppearancePage, "Exceptions": ExceptionsPage,
    "Advanced": AdvancedPage, "Updates": UpdatesPage,
})

# `qtranslate.qt.app.open_options` opens the dialog at Basics, the same
# page native's Options opens to from the main window's overflow menu.
OptionsDialog = BasicsPage

__all__ = ["AdvancedPage", "AppearancePage", "BasicsPage", "ExceptionsPage",
           "HotkeysPage", "InternetPage", "LanguagesPage", "ServicesPage",
           "UpdatesPage", "OptionsDialog", "PAGES"]
