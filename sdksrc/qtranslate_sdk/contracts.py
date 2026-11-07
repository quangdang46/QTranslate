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
    the same surface.
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

    # -- PluginContext parity (host: qtranslate.extensions.ExtensionAPI)

    @property
    def data_dir(self):
        """This extension's private data directory (``str`` path)."""
        raise ExtensionError(
            "data_dir needs a host; the real ExtensionAPI is passed to "
            "register() at runtime")

    def notify(self, severity="info", title="", message=""):
        """Post a user notification; True when a surface accepted it."""
        raise ExtensionError(
            "notify needs a host; the real ExtensionAPI is passed to "
            "register() at runtime")

    def http_get(self, url, headers=None, timeout=None):
        """GET ``url`` through the host's shared HTTP path -> body text."""
        raise ExtensionError(
            "http_get needs a host; the real ExtensionAPI is passed to "
            "register() at runtime")

    def http_post(self, url, data=None, headers=None, json=None,
                  timeout=None):
        """POST ``url`` through the host's shared HTTP path -> body text."""
        raise ExtensionError(
            "http_post needs a host; the real ExtensionAPI is passed to "
            "register() at runtime")

    def on_load(self, fn):
        """``fn(api)`` after each successful load/enable."""
        raise ExtensionError(
            "on_load needs a host; the real ExtensionAPI is passed to "
            "register() at runtime")

    def on_unload(self, fn):
        """``fn(api)`` when the extension is disabled."""
        raise ExtensionError(
            "on_unload needs a host; the real ExtensionAPI is passed to "
            "register() at runtime")

    def on_settings_changed(self, fn):
        """``fn(key, value)`` after a successful ``set_setting``."""
        raise ExtensionError(
            "on_settings_changed needs a host; the real ExtensionAPI is "
            "passed to register() at runtime")

    # -- credentials (host: per-extension secrets.json in data_dir) ------

    def secrets_get(self, key, default=None):
        """This extension's stored secret for ``key``, or ``default``."""
        raise ExtensionError(
            "secrets_get needs a host; the real ExtensionAPI is passed "
            "to register() at runtime")

    def secrets_set(self, key, value):
        """Persist ``value`` (a string) as this extension's secret."""
        raise ExtensionError(
            "secrets_set needs a host; the real ExtensionAPI is passed "
            "to register() at runtime")

    def secrets_delete(self, key):
        """Remove this extension's secret for ``key``; no-op when absent."""
        raise ExtensionError(
            "secrets_delete needs a host; the real ExtensionAPI is "
            "passed to register() at runtime")

    def secrets_contains(self, key):
        """Whether a secret is set, without reading its value."""
        raise ExtensionError(
            "secrets_contains needs a host; the real ExtensionAPI is "
            "passed to register() at runtime")

    # -- localization (host: extension-folder localization/*.toml) ------

    def tr(self, key, fallback="", *args):
        """Translate ``key`` via this extension's own bundles.

        Resolution: ``localization/<lang>.toml`` in the extension's
        folder for the active UI language (written tag, base language,
        then ``en``), else ``fallback`` (or ``key`` when both are
        empty); ``*args`` apply printf-style to the winning string.
        """
        raise ExtensionError(
            "tr needs a host; the real ExtensionAPI is passed to "
            "register() at runtime")


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
        # PluginContext-parity recordings: a real temp dir, a notify
        # log, recorded http calls (no network in the fake) and the
        # lifecycle hooks an extension subscribed.
        import tempfile
        self._data_dir = tempfile.mkdtemp(prefix="qt-fake-ext-")
        self.notifications = []
        self.http_calls = []
        self.load_hooks = []
        self.unload_hooks = []
        self.settings_hooks = []
        # Secrets are recorded in memory (a fake has no secrets.json);
        # tr() has no bundles, so it always renders the fallback -- the
        # same contract the real api gives an extension with no
        # localization/ folder.
        self.secrets = {}

    @property
    def data_dir(self):
        return self._data_dir

    def notify(self, severity="info", title="", message=""):
        self.notifications.append({"severity": severity, "title": title,
                                   "message": message})
        return True

    def http_get(self, url, headers=None, timeout=None):
        self.http_calls.append({"method": "GET", "url": url,
                                "headers": headers, "timeout": timeout})
        return ""

    def http_post(self, url, data=None, headers=None, json=None,
                  timeout=None):
        self.http_calls.append({"method": "POST", "url": url,
                                "data": data, "json": json,
                                "headers": headers, "timeout": timeout})
        return ""

    def on_load(self, fn):
        self.load_hooks.append(fn)
        return "load"

    def on_unload(self, fn):
        self.unload_hooks.append(fn)
        return "unload"

    def on_settings_changed(self, fn):
        self.settings_hooks.append(fn)
        return "settings"

    def secrets_get(self, key, default=None):
        return self.secrets.get(key, default)

    def secrets_set(self, key, value):
        if not isinstance(value, str):
            raise TypeError("secret value must be a string")
        self.secrets[key] = value
        return value

    def secrets_delete(self, key):
        self.secrets.pop(key, None)

    def secrets_contains(self, key):
        return key in self.secrets

    def tr(self, key, fallback="", *args):
        text = str(fallback or "") or str(key or "")
        if args:
            try:
                text = text % tuple(args)
            except (TypeError, ValueError):
                pass
        return text

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
