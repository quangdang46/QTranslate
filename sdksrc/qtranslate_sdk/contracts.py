"""The manifest contract and the host API an extension registers against.

This is the surface ``EXTENSION_SDK.md`` describes. It is deliberately
data-only here: the host implements the behaviour (loading, conflict
resolution, committing a provider into the dispatch table), and the SDK
publishes the shapes an extension writes against, so an extension can be
developed and checked with nothing but this package installed.
"""
from __future__ import annotations

import dataclasses

# The fields a manifest must declare. Mirrors the host's
# ``extensions._REQUIRED_FIELDS``; the host is the authority and
# ``tests/regress_sdk_package.py`` keeps the two in step.
MANIFEST_REQUIRED = ("id", "name", "version", "sdk_version", "entrypoint",
                     "capabilities")

# The capability names a manifest may declare. Every one of them has a
# register_* method on the host API below, so a manifest can only claim
# something the runtime can host.
CAPABILITIES = ("provider", "dictionary", "theme", "ui", "workflow",
                "tts", "ocr", "spell")

# The published UI slots, by kind. The names are the native UI surface's,
# not invented ones: the menu names are ``Menus[].Id`` in a locale pack,
# and the panes are the three ``Show*Pane`` toggles.
MENU_SLOTS = ("main", "source_context", "result_context", "language",
              "tray", "history_ctx", "dict_header", "history_menu", "ocr")
PANEL_SLOTS = ("top", "middle", "services")
PANES = PANEL_SLOTS
POPUP_SLOTS = ("icons", "body")
UI_KINDS = ("menu", "panel", "popup")


class ExtensionError(Exception):
    """Base for the errors the host reports to an extension."""


@dataclasses.dataclass(frozen=True)
class Manifest:
    """An extension's ``manifest.json``, validated.

    ``capabilities`` is a tuple so a manifest that lists the same
    capability twice still compares equal to the set an author meant.
    """

    id: str
    name: str
    version: str
    sdk_version: str
    entrypoint: str
    capabilities: tuple = ()

    @classmethod
    def from_dict(cls, data: dict) -> "Manifest":
        missing = [k for k in MANIFEST_REQUIRED if not data.get(k)]
        if missing:
            raise ExtensionError("manifest is missing %s"
                                 % ", ".join(sorted(missing)))
        caps = data.get("capabilities") or ()
        return cls(id=data["id"], name=data["name"], version=data["version"],
                   sdk_version=str(data["sdk_version"]),
                   entrypoint=data["entrypoint"],
                   capabilities=tuple(caps))

    @property
    def entry_module(self) -> str:
        """The ``module`` half of ``module:callable``."""
        return self.entrypoint.split(":", 1)[0]

    @property
    def entry_callable(self) -> str:
        """The ``callable`` half of ``module:callable``."""
        parts = self.entrypoint.split(":", 1)
        return parts[1] if len(parts) == 2 else "register"


class ExtensionAPI:
    """The host API handed to ``register(api)``.

    The SDK's copy declares the surface and refuses to be used outside a
    host: it exists so an extension can be written, type-checked and
    unit-tested with the host's behaviour stubbed (``FakeAPI`` in the
    test harness). The REAL object an extension receives at runtime is
    the host's ``qtranslate.extensions.ExtensionAPI``, which implements
    the same three methods.
    """

    def register_provider(self, name, fn, replaces=None):
        raise ExtensionError(
            "register_provider needs a host; the real ExtensionAPI is "
            "passed to register() at runtime")

    def register_theme(self, name, record, replaces=None):
        raise ExtensionError(
            "register_theme needs a host; the real ExtensionAPI is "
            "passed to register() at runtime")

    def register_ui(self, kind, slot, contribution, replaces=None):
        raise ExtensionError(
            "register_ui needs a host; the real ExtensionAPI is "
            "passed to register() at runtime")

    def register_dictionary(self, name, fn, replaces=None):
        raise ExtensionError(
            "register_dictionary needs a host; the real ExtensionAPI is "
            "passed to register() at runtime")

    def register_tts(self, name, fn, replaces=None):
        raise ExtensionError(
            "register_tts needs a host; the real ExtensionAPI is "
            "passed to register() at runtime")

    def register_ocr(self, name, fn, replaces=None):
        raise ExtensionError(
            "register_ocr needs a host; the real ExtensionAPI is "
            "passed to register() at runtime")

    def register_spell(self, name, fn, replaces=None):
        raise ExtensionError(
            "register_spell needs a host; the real ExtensionAPI is "
            "passed to register() at runtime")

    def register_workflow(self, name, fn, replaces=None):
        raise ExtensionError(
            "register_workflow needs a host; the real ExtensionAPI is "
            "passed to register() at runtime")


class FakeAPI(ExtensionAPI):
    """A recording host API, for an extension's own tests.

    It records what was registered instead of committing anything, so an
    extension can assert its own registrations without the app.
    """

    def __init__(self):
        self.providers = {}
        self.themes = {}
        self.ui = []
        self.dictionaries = {}
        self.tts = {}
        self.ocr = {}
        self.spell = {}
        self.workflows = {}

    def register_provider(self, name, fn, replaces=None):
        self.providers[name] = {"fn": fn, "replaces": replaces}
        return name

    def register_theme(self, name, record, replaces=None):
        self.themes[name] = {"record": record, "replaces": replaces}
        return name

    def register_ui(self, kind, slot, contribution, replaces=None):
        if kind not in UI_KINDS:
            raise ExtensionError("unknown UI kind %r" % (kind,))
        self.ui.append({"kind": kind, "slot": slot,
                        "contribution": contribution,
                        "replaces": replaces})
        return slot

    def register_dictionary(self, name, fn, replaces=None):
        self.dictionaries[name] = {"fn": fn, "replaces": replaces}
        return name

    def register_tts(self, name, fn, replaces=None):
        self.tts[name] = {"fn": fn, "replaces": replaces}
        return name

    def register_ocr(self, name, fn, replaces=None):
        self.ocr[name] = {"fn": fn, "replaces": replaces}
        return name

    def register_spell(self, name, fn, replaces=None):
        self.spell[name] = {"fn": fn, "replaces": replaces}
        return name

    def register_workflow(self, name, fn, replaces=None):
        self.workflows[name] = {"fn": fn, "replaces": replaces}
        return name
