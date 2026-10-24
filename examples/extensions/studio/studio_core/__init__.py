"""Studio's shared state: one context object every module receives.

The context owns what a real extension owns somewhere: its settings
(through the host API's per-extension persistence), its data files, and
the counters its UI reports. Modules never reach into the app's
internals -- they talk to the context, and the context talks to the
host API.
"""
import json
import os


class StudioContext:
    """Everything the Studio modules share."""

    def __init__(self, api):
        self.api = api
        # A data file shipped INSIDE the extension: loaded relative to
        # this module's own path, not the working directory.
        data = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "data", "glossary.json")
        try:
            with open(data, encoding="utf-8") as fh:
                self.glossary = json.load(fh)
        except Exception:                   # noqa: BLE001 -- fail open
            self.glossary = {}
        self.misses = 0

    # -- settings (the host persists them under this extension's id) ----
    def setting(self, key, default):
        try:
            return self.api.get_setting(key, default)
        except Exception:                   # noqa: BLE001
            return default

    @property
    def greeting(self):
        return self.setting("Studio.Greeting", "〔studio〕")

    @property
    def title(self):
        return self.setting("Studio.Title", "Studio")

    @property
    def max_words(self):
        try:
            return max(1, int(self.setting("Studio.MaxWords", 40)))
        except Exception:                   # noqa: BLE001
            return 40

    # -- the glossary ----------------------------------------------------
    def lookup(self, text, src, tgt):
        """The exact entry, or None."""
        return (self.glossary.get((src or "").lower(), {})
                .get((tgt or "").lower(), {})
                .get((text or "").strip().lower()))

    def record_miss(self):
        self.misses += 1
