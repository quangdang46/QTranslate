"""Extension Manager (built-in only) — Slice 3 (approved 2026-10-15).

Built on ``EXTENSION_SDK.md`` §6/§7 (override rules + fail-open loading)
as the design source of truth, scoped to the locked decisions:

- Built-in providers only. No discovery, no sandbox, no versioning,
  no marketplace — those are explicitly out of scope for this slice.
- ``registered`` ≠ ``enabled``: a provider is registered when it has a
  table entry (even a retired host — dead ≠ deleted); it is enabled
  only when reachable through the configured order minus disabled.
- ``ordered_services()`` (strip, no extras) vs ``router_order()``
  (fallback chain, TRANSLATORS-appended + dedupe by callable identity
  per rule (b)) are two separate contracts and are never merged.
- Override conflicts (D18) are REPORTED (returned to the caller), never
  auto-resolved by scan/load order.
- Broken registrations fail open: the extension is skipped and the
  built-in stays active.

tkinter-free (pinned by ``tests/regress_extensions.py``).
"""
from __future__ import annotations


class OverrideConflict(Exception):
    """Two providers claim the same id and the user must pick the winner."""


class ExtensionManager:
    """Minimal manager over ``registry`` for the built-in providers."""

    def __init__(self, registry=None):
        from qtranslate import registry as _RG
        self._rg = registry if registry is not None else _RG
        self._providers = {}
        self._replaces = {}
        for name in self._rg.TRANSLATORS:
            self._providers[name] = self._rg.TRANSLATORS[name]

    # -- registration ---------------------------------------------------
    def register(self, name, fn, replaces=None):
        """Register a provider callable.

        ``replaces`` declares an explicit override of a built-in id;
        enabling it is the caller's decision (D18), never implicit.
        A broken callable (non-callable) raises and the caller keeps
        the built-in — fail-open at the call site.
        """
        if not callable(fn):
            raise TypeError("provider %r is not callable" % (name,))
        if replaces and replaces in self._replaces:
            raise OverrideConflict(
                "%r and %r both replace %r: the user must pick the winner"
                % (self._replaces[replaces], name, replaces))
        self._providers[name] = fn
        if replaces:
            self._replaces[replaces] = name
        return name

    def providers(self):
        """All registered providers, including retired-host ones."""
        return dict(self._providers)

    # -- enablement -----------------------------------------------------
    def enabled(self):
        """Providers reachable through the configured order minus disabled.

        Mirrors ``registry.router_order`` semantics (ServicesOrder ids →
        names, TRANSLATORS-appended, deduped by callable identity per
        rule (b)) so the manager and the engine agree on what runs.
        """
        order = self._rg.router_order()
        return [n for n in order if n in self._providers]

    def strip(self):
        """Exact native strip order: ServicesOrder-minus-disabled, no extras.

        Delegates to ``App.ordered_services`` semantics via
        ``registry`` + config (stable when called headless: falls back to
        the default order on any read failure).
        """
        try:
            from qtranslate import config as _C
            ids = _C.services_order()
            try:
                dis = set(_C.load().get("DisabledServices", []))
            except Exception:
                dis = set()
            names = [_C.SERVICE_NAMES.get(i) for i in ids if i not in dis]
            return [n for n in names if n in self._providers]
        except Exception:
            return list(self.enabled())

    # -- overrides --------------------------------------------------------
    def active(self, name):
        """The callable that actually serves ``name`` (override or built-in).

        Rule (b): ``bing`` resolves to the ``microsoft`` callable — one
        object, never a second chain entry.
        """
        if name == "bing":
            name = "microsoft"
        winner = self._replaces.get(name, name)
        return self._providers.get(winner)

    def conflicts(self):
        """Declared overrides, for the user to review (D18)."""
        return dict(self._replaces)
