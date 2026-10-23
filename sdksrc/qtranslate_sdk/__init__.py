"""The QTranslate extension SDK: the contracts, and nothing else.

An extension author imports THIS, not the desktop app. The package
carries:

* the host API's surface (:class:`ExtensionAPI`, :class:`Manifest`,
  :class:`ExtensionError`), so an extension's ``register(api)`` can be
  written and type-checked without the app installed;
* the data shapes a contribution returns (:class:`Result`);
* the slot names a UI contribution targets (``MENU_SLOTS``,
  ``PANEL_SLOTS``, ``POPUP_SLOTS``, ``PANES``).

It deliberately does NOT carry the engine, the providers, the config
store or the GUI. An extension runs INSIDE the host process, and the
host supplies those through the API object it passes to ``register``.
Importing them here would make the SDK drag the whole desktop app in,
which is exactly what D19's packaging must avoid.

The public surface is what ``__all__`` names; everything else in the
package is an implementation detail.
"""
from __future__ import annotations

from .contracts import (CAPABILITIES, MANIFEST_REQUIRED, PANES, PANEL_SLOTS,
                        POPUP_SLOTS, MENU_SLOTS, UI_KINDS, ExtensionAPI,
                        ExtensionError, FakeAPI, Manifest)
from .result import Result

# The contract version an extension's manifest must declare. The host
# refuses a manifest with a different major version, so this is the
# number an author writes in ``sdk_version``.
SDK_VERSION = "1.0"

__all__ = [
    "Result",
    "ExtensionAPI",
    "ExtensionError",
    "FakeAPI",
    "Manifest",
    "MANIFEST_REQUIRED",
    "CAPABILITIES",
    "MENU_SLOTS",
    "PANEL_SLOTS",
    "POPUP_SLOTS",
    "PANES",
    "UI_KINDS",
    "SDK_VERSION",
]

__version__ = "0.1.0"
