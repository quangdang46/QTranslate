"""Extension Manager — built-ins (Slice 3) + directory loading (Slice 7).

Built on ``EXTENSION_SDK.md`` §3/§4/§6/§7 (folder layout, manifest schema,
override rules, fail-open loading) as the design source of truth:

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

Two slices land here:

- **Slice 3 (built-in only):** ``register``/``providers``/``enabled``/
  ``strip``/``active``/``conflicts`` over the registry.
- **Slice 7 (directory discovery + fail-open loading):** ``validate``/
  ``read_manifest``/``discover`` plus ``load_dir``, which scans the
  per-user extensions folder, validates each manifest, imports the
  entrypoint, and applies registrations — disabling (not crashing on)
  any extension that fails, per ``EXTENSION_SDK.md`` §7.

Override consistency (rule (b) / D18): ``commit`` applies a declared
override to **every** name sharing the replaced callable, because
``microsoft`` and ``bing`` are one provider — so ``TRANSLATORS``,
``router_order()`` and :meth:`ExtensionManager.active` never disagree. An
alias conflict (two extensions claiming such aliases) applies **no**
override and keeps the built-in: with no winner-selection UI yet, discovery
order must not choose one.

Scope still out: the override *UI* (who picks the D18 winner is a UI
slice), vendored-dependency *isolation* (D17 is solved here only for the
import path, not for cross-extension collisions), packaging, and startup
wiring in ``app.py`` (a UI-host slice).

tkinter-free (pinned by ``tests/regress_extensions.py`` and
``tests/regress_extension_loading.py``).
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys

# SDK contract version this runtime implements. ``EXTENSION_SDK.md`` §4:
# ``sdk_version`` is a compatibility gate, so only the major must match.
SDK_VERSION = "1.0"
SDK_MAJOR = SDK_VERSION.split(".", 1)[0]

# Options.json section holding the user's saved override winners (D18):
# ``{base_id: extension_id}``. Written by the override UI, applied at
# startup. Empty until the user picks a winner.
OVERRIDES_SECTION = "ExtensionOverrides"

# Options.json section holding the user's saved override winners (D18):
# ``{base_id: extension_id}``. Written by the override UI, applied at
# startup. Empty until the user picks a winner.
OVERRIDES_SECTION = "ExtensionOverrides"

# Options.json section holding the user's saved override winners (D18):
# ``{base_id: extension_id}``. Written by the override UI, applied at
# startup. Empty until the user picks a winner.
OVERRIDES_SECTION = "ExtensionOverrides"

# Options.json section holding the user's saved override winners (D18):
# ``{base_id: extension_id}``. Written by the override UI, applied at
# startup. Empty until the user picks a winner.
OVERRIDES_SECTION = "ExtensionOverrides"

# Capability kinds an extension may declare (§2). Unknown kinds are
# rejected: the manifest is a compatibility gate, and silently accepting
# a kind the runtime cannot host would make ``capabilities`` a lie.
KNOWN_CAPABILITIES = frozenset((
    "provider", "workflow", "theme", "ui",
    "dictionary", "tts", "ocr", "spell",
))

_REQUIRED_FIELDS = ("id", "name", "version", "sdk_version", "entrypoint",
                    "capabilities")


class ManifestError(Exception):
    """A manifest failed validation; the extension is disabled (§7)."""


def _sdk_major(value):
    if not isinstance(value, str):
        raise ManifestError("sdk_version must be a string")
    head = value.split(".", 1)[0].strip()
    if not head.isdigit():
        raise ManifestError("sdk_version %r has no numeric major" % (value,))
    return head


def validate(data):
    """Validate a parsed manifest and return it unchanged.

    Raises ``ManifestError`` on the first problem. The rules are the
    minimum schema in ``EXTENSION_SDK.md`` §4 plus the Phase-3 test
    matrix (``TEST_STRATEGY.md`` §3): missing/short/bad ``sdk_version``,
    broken ``entrypoint``, and malformed capability/override lists.
    """
    if not isinstance(data, dict):
        raise ManifestError("manifest must be a JSON object")
    for key in _REQUIRED_FIELDS:
        if key not in data:
            raise ManifestError("missing required field %r" % (key,))
    for key in ("id", "name", "version"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise ManifestError("%s must be a non-empty string" % key)
    if _sdk_major(data["sdk_version"]) != SDK_MAJOR:
        raise ManifestError(
            "sdk_version %r is incompatible with SDK %s"
            % (data["sdk_version"], SDK_VERSION))

    entrypoint = data["entrypoint"]
    if not isinstance(entrypoint, str) or entrypoint.count(":") != 1:
        raise ManifestError("entrypoint must be 'module:callable'")
    module, callable_name = entrypoint.split(":")
    if not module.strip() or not callable_name.strip():
        raise ManifestError("entrypoint must be 'module:callable'")

    capabilities = data["capabilities"]
    if not isinstance(capabilities, list) or not capabilities:
        raise ManifestError("capabilities must be a non-empty list")
    for capability in capabilities:
        if capability not in KNOWN_CAPABILITIES:
            raise ManifestError("unknown capability %r" % (capability,))

    replaces = data.get("replaces", [])
    if not isinstance(replaces, list) or any(
            not isinstance(r, str) or not r.strip() for r in replaces):
        raise ManifestError("replaces must be a list of ids")
    return data


def read_manifest(folder):
    """Read + validate ``folder/manifest.json``; raises ``ManifestError``."""
    path = os.path.join(folder, "manifest.json")
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except OSError as exc:
        raise ManifestError("cannot read manifest.json: %s" % (exc,))
    except ValueError as exc:
        raise ManifestError("manifest.json is not valid JSON: %s" % (exc,))
    return validate(raw)


def discover(extensions_dir):
    """Folders directly under ``extensions_dir`` that carry a manifest.

    Sorted for deterministic load order; hidden folders and loose files
    are skipped. A missing directory is not an error — the user simply
    has no extensions yet (D16: never auto-load from the install dir).
    """
    if not extensions_dir or not os.path.isdir(extensions_dir):
        return []
    found = []
    for name in sorted(os.listdir(extensions_dir)):
        if name.startswith("."):
            continue
        folder = os.path.join(extensions_dir, name)
        if os.path.isfile(os.path.join(folder, "manifest.json")):
            found.append(folder)
    return found


def _module_path(folder, module):
    """Resolve ``module`` inside an extension folder to (path, subdirs).

    ``__init__`` is the package root; any other name may be a module or a
    subpackage (``EXTENSION_SDK.md`` §3 shows ``provider.py``/``ui.py`` as
    siblings of ``__init__.py``).
    """
    if module == "__init__":
        return os.path.join(folder, "__init__.py"), [folder]
    flat = os.path.join(folder, module + ".py")
    if os.path.isfile(flat):
        return flat, None
    package = os.path.join(folder, module, "__init__.py")
    if os.path.isfile(package):
        return package, [os.path.join(folder, module)]
    return None, None


# D17 bookkeeping: which plain module names each extension's vendored
# deps shadowed, so the loader can report them (never auto-resolve).
# Entry format: (extension_id, [module_name, ...]).
_LAST_VENDOR_SHADOWS = []
_VENDOR_SHADOW_LIMIT = 64

# Original objects for names a vendored dep overwrote, so the extension
# keeps its bound copy while everyone else sees Core's again.
_MODULE_ORIGIN = {}


def _is_under(folder, mod):
    """True when ``mod``'s file lives inside ``folder``."""
    f = getattr(mod, "__file__", None)
    if not f:
        return False
    try:
        return os.path.abspath(f).startswith(os.path.abspath(folder)
                                             + os.sep)
    except Exception:
        return False


def _restore_modules(before, folder=None, keep=()):
    """Undo the ``sys.modules`` side effects of an extension import.

    Two kinds, both undone:
      * names that were NOT imported before (the extension's vendored
        deps and their submodules) -- dropped, so they cannot shadow Core
        or a later extension -- except those in ``keep`` (the entrypoint
        module, which the loader owns);
      * names that WERE imported before but now resolve to a file inside
        ``folder`` -- a vendored dep that overwrote them: Core's original
        object is restored, so Core keeps the module it actually imported.

    Returns the set of names in the second category (the shadows).
    """
    shadowed = set()
    if folder is None:
        for name in list(sys.modules):
            if name not in before and name not in keep:
                sys.modules.pop(name, None)
        return shadowed
    for name in list(sys.modules):
        mod = sys.modules.get(name)
        if name in before:
            if name in keep:
                continue
            if mod is not None and _is_under(folder, mod):
                # the vendored copy is installed under a name Core owns
                shadowed.add(name)
            continue
        if name not in keep:
            sys.modules.pop(name, None)
    for name in shadowed:
        orig = _MODULE_ORIGIN.get(name)
        if orig is not None:
            sys.modules[name] = orig
    return shadowed


def _snapshot_owners(names):
    """Remember which object each currently-shadowable name holds."""
    saved = {}
    for name in names:
        mod = sys.modules.get(name)
        if mod is not None:
            saved[name] = mod
    return saved


def import_entrypoint(folder, manifest):
    """Import the manifest's entrypoint callable from ``folder``.

    The extension folder is placed on ``sys.path`` for the duration of the
    import only, so a vendored dependency inside the folder is importable
    (the D17 mechanism). This is **not** isolation: collisions between two
    extensions — or with Core — are still possible, which is why D17's
    full isolation remains designed-for. Any failure raises; the caller
    (``load_dir``) turns it into a disabled extension.
    """
    module_name, callable_name = manifest["entrypoint"].split(":")
    module_name, callable_name = module_name.strip(), callable_name.strip()
    path, subdirs = _module_path(folder, module_name)
    if path is None:
        raise ImportError("entrypoint module %r not found in %s"
                          % (module_name, folder))

    safe_id = re.sub(r"[^0-9A-Za-z_]", "_", manifest["id"])
    full_name = "qtranslate_ext_%s_%s" % (safe_id, module_name)
    spec = importlib.util.spec_from_file_location(
        full_name, path, submodule_search_locations=subdirs)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % (path,))
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module

    # D17 hygiene: the extension's own ``sys.path`` entry makes its
    # *vendored* packages importable, but any plain-named module it
    # imports lands in ``sys.modules`` under that plain name and stays
    # there after the import -- shadowing the same name for Core and for
    # every later extension (a second extension silently gets the first
    # one's version). Snapshot ``sys.modules`` so the call can report and
    # then undo those shadows.
    before = set(sys.modules)
    _MODULE_ORIGIN.update(_snapshot_owners(before))
    try:
        sys.path.insert(0, folder)
        try:
            spec.loader.exec_module(module)
        finally:
            try:
                sys.path.remove(folder)
            except ValueError:
                pass
    except BaseException:
        _restore_modules(before)
        sys.modules.pop(full_name, None)
        raise
    finally:
        # The entrypoint module itself is owned by the loader and survives.
        # Everything else that was not imported before (the vendored deps
        # and their submodules) is dropped; a vendored dep that overwrote
        # a name Core already owns is rolled back to Core's object, while
        # the extension keeps working via the module object it bound at
        # import time.
        owned = {full_name}
        shadowed = _restore_modules(before, folder, keep=owned)
        if shadowed:
            if len(_LAST_VENDOR_SHADOWS) < _VENDOR_SHADOW_LIMIT:
                _LAST_VENDOR_SHADOWS.append(
                    (manifest["id"], sorted(shadowed)))

    register = getattr(module, callable_name, None)
    if register is None:
        raise ImportError("entrypoint %r has no callable %r"
                          % (manifest["entrypoint"], callable_name))
    if not callable(register):
        raise TypeError("entrypoint %r is not callable"
                        % (manifest["entrypoint"],))
    return register


class OverrideConflict(Exception):
    """Two providers claim the same id and the user must pick the winner."""


class ExtensionAPI:
    """Provisional host API handed to an extension's ``register`` callable.

    Registration forwards to the manager, which reports override conflicts
    (D18) instead of resolving them. This surface is **provisional**:
    ``EXTENSION_SDK.md`` states the SDK signatures freeze before release, so
    an extension registers a provider by calling
    ``api.register_provider(name, fn, replaces=…)``.
    """

    def __init__(self, manager):
        self._manager = manager

    def register_provider(self, name, fn, replaces=None):
        return self._manager.register(name, fn, replaces=replaces)

    def register_theme(self, name, record, replaces=None):
        """Register a theme colour record (Slice 9a).

        ``record`` is the same shape ``theme.load_theme_at`` returns: a
        ``{"Common": ..., "Window": ..., ...}`` dict (any subset of the
        sections/slots -- ``theme.slot()`` reports unset for the rest, so
        a theme may override two colours and inherit the rest).
        ``replaces`` names a built-in theme id; enabling it is the
        caller's decision (D18), never implicit.
        """
        return self._manager.register_theme(name, record, replaces=replaces)

    def register_ui(self, kind, slot, contribution, replaces=None):
        """Register a UI contribution (menu / panel / popup slot).

        The slot names are ``ui_slots``'s, which are derived from the native
        UI surface rather than invented: the menu ids are the ``Menus[].Id``
        values a locale pack declares, and the panel names are the three
        ``Show*Pane`` toggles the Options page reads.

        Contributions land in ``self._manager.ui_slots``; a host reads them
        through ``UISlotRegistry.contributions`` / ``winner``. Same
        last-wins-with-declared-replaces policy as the provider and theme
        slots, so an outcome never depends on discovery order.
        """
        return self._manager.register_ui(kind, slot, contribution,
                                         replaces=replaces)


class ExtensionManager:
    """Manager over ``registry``: built-ins plus loaded extensions."""

    def __init__(self, registry=None):
        from qtranslate import registry as _RG
        self._rg = registry if registry is not None else _RG
        self._providers = {}
        self._replaces = {}
        self._claims = {}
        self._themes = {}
        self._theme_replaces = {}
        self._ui = None      # ui_slots.UISlotRegistry, created on first use
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

    def register_theme(self, name, record, replaces=None):
        """Register a theme record under ``name`` (Slice 9a).

        Mirrors ``register``: a non-dict record raises and the caller keeps
        whatever themes were loaded before it (fail-open at the call site).
        Two extensions claiming the same built-in theme id raises
        ``OverrideConflict`` -- the user must pick the winner (D18).
        """
        if not isinstance(record, dict):
            raise TypeError("theme %r must be a dict of sections" % (name,))
        if replaces and replaces in self._theme_replaces:
            raise OverrideConflict(
                "%r and %r both replace theme %r: the user must pick the "
                "winner" % (self._theme_replaces[replaces], name, replaces))
        self._themes[name] = record
        if replaces:
            self._theme_replaces[replaces] = name
        return name

    def register_ui(self, kind, slot, contribution, replaces=None):
        """Register a UI contribution into the ``ui_slots`` registry.

        Lazily creates the registry so a headless caller that never touches
        UI slots pays nothing for it. Fail-open: a bad ``kind``/``slot``
        raises from ``ui_slots.UISlotRegistry.add`` and the caller keeps the
        built-in surface, which is the same contract the provider and theme
        registrations use.
        """
        if self._ui is None:
            from qtranslate.ui_slots import UISlotRegistry
            self._ui = UISlotRegistry()
        return self._ui.add(kind, slot, contribution, replaces=replaces)

    @property
    def ui_slots(self):
        """The UI slot registry, or None until something registers a slot."""
        return self._ui

    def providers(self):
        """All registered providers, including retired-host ones."""
        return dict(self._providers)

    def themes(self):
        """All registered extension themes, by extension-given name."""
        return dict(self._themes)

    def theme_conflicts(self):
        """Declared theme overrides, for the user to review (D18)."""
        return dict(self._theme_replaces)

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

    def active_theme(self, name=None):
        """Resolve a theme name to a record with native semantics (Slice 9a).

        Resolution order:
          1. an extension theme named ``name`` wins outright;
          2. a declared override of built-in ``name`` wins;
          3. otherwise the built-in ``theme.active_theme(name)`` (which
             itself falls back to ``default_theme()``, never ``None`` --
             ``FUN_0044b44f``).

        Unset slots are never materialised here: callers read colours
        through ``theme.slot()`` / ``state_colors()``, which already
        report ``UNSET`` for missing slots, so a partial extension
        record inherits the rest slot-by-slot exactly like a partial
        native theme file does.
        """
        if name in self._themes:
            return self._themes[name]
        winner = self._theme_replaces.get(name)
        if winner is not None and winner in self._themes:
            return self._themes[winner]
        from qtranslate import theme as _TH
        try:
            return _TH.active_theme(name or "")
        except Exception:
            return _TH.default_theme()

    def override_conflicts(self):
        """Providers claimed by more than one loaded extension (D18).

        Returns ``{base_id: [ext_id, ...]}`` for every provider with multiple
        claimants — the set the override UI presents for the user to pick a
        winner. Alias-equivalent claims (``microsoft``/``bing``) are merged by
        callable identity (rule (b)), so the user sees one row per provider.
        """
        table = self._rg.TRANSLATORS
        groups = {}
        for base, exts in self._claims.items():
            fn = table.get(base)
            key = id(fn) if fn is not None else base
            group = groups.setdefault(key, {"base": base, "exts": []})
            for ext in exts:
                if ext not in group["exts"]:
                    group["exts"].append(ext)
        return {g["base"]: g["exts"] for g in groups.values()
                if len(g["exts"]) > 1}

    def _alias_conflict_bases(self):
        """Override targets that collide because they are aliases (rule b).

        Two names resolving to the SAME callable (``microsoft``/``bing``) are
        one provider, so two ``replaces`` declarations on them are two claims
        on one implementation. Returns every base name involved, empty when
        there is no collision.
        """
        groups = {}
        for base in self._replaces:
            fn = self._providers.get(base)
            if fn is not None:
                groups.setdefault(fn, []).append(base)
        conflicted = set()
        for bases in groups.values():
            if len(bases) > 1:
                conflicted.update(bases)
        return conflicted

    def _alias_conflict_reason(self, conflicted):
        parts = ", ".join("%s (%s)" % (self._replaces[base], base)
                          for base in sorted(conflicted))
        return ("OverrideConflict: %s replace one provider: the user must "
                "pick the winner" % (parts,))

    def _drop_unresolved_alias_conflicts(self):
        """Apply no override to an alias-conflicted provider (rule 3 / D18).

        With no winner-selection UI yet, discovery order must not pick one, so
        every claim on the conflicted alias group is dropped and the built-in
        stays the callable behind each name. Returns the dropped base names.
        """
        conflicted = self._alias_conflict_bases()
        for base in conflicted:
            winner = self._replaces.pop(base, None)
            if winner is not None:
                self._providers.pop(winner, None)
        return conflicted

    def commit(self, registry=None):
        """Apply the loaded set to the registry's live dispatch table.

        Writes every registered provider into ``registry.TRANSLATORS`` **in
        place** — ``app.TRANSLATORS``/``engine``'s ``TRANSLATORS`` are aliases
        of that same dict, so the running app sees it without a re-import — and
        applies each declared override under the built-in id it replaces (so
        selecting that built-in actually calls the extension). The cached
        router is dropped so the next ``build_router()`` re-reads the table and
        appends extension-only names to the fallback chain, exactly as
        ``router_order`` already does for any table-only name.

        Rule (b) makes an override symmetric across aliases: an override of
        ``microsoft`` updates ``bing`` too (and the other way round), because
        every name that shared the replaced callable is the same provider —
        so the table, ``router_order()`` and ``active()`` all agree. An
        unresolved alias conflict (see ``_alias_conflict_bases``) applies no
        override at all, leaving the built-in.

        Returns the registry module used.
        """
        reg = registry if registry is not None else self._rg
        table = reg.TRANSLATORS
        before = dict(table)
        self._drop_unresolved_alias_conflicts()
        for name, fn in self._providers.items():
            table[name] = fn
        for base, winner in self._replaces.items():
            fn = self._providers.get(winner)
            if fn is None:
                continue
            table[base] = fn
            replaced = before.get(base)
            if replaced is not None:
                for key, val in before.items():
                    if val is replaced:
                        table[key] = fn
                        self._providers[key] = fn
        reset = getattr(reg, "reset_router", None)
        if reset is not None:
            reset()
        return reg

    # -- directory loading (Slice 7) ------------------------------------
    def load_dir(self, extensions_dir, api=None, importer=None, saved=None):
        """Discover, validate and load every extension under a directory.

        Fail-open (``EXTENSION_SDK.md`` §7): one bad extension is disabled
        with a reason and the rest still load. Returns one outcome dict
        per discovered folder, sorted by folder name:
        ``{"path", "id", "status": "loaded"|"disabled", "reason"}``.

        ``saved`` is the user's persisted winner selection
        (``{base_id: extension_id}``, D18): an extension claiming a provider
        the user already assigned to a *different* extension is disabled with
        a "saved winner" reason before it can reach auto-resolution.

        Alias-equivalent override conflicts (two extensions claiming
        ``microsoft`` and ``bing``) are resolved **after** every folder is
        read and **before** any commit: no winner is guessed from load order,
        so neither claim is applied and the built-in stays (see
        ``_resolve_alias_conflicts``).

        ``api``/``importer`` are injectable so the loader is testable
        without touching the import machinery or a real folder.
        """
        api = api if api is not None else ExtensionAPI(self)
        importer = importer or import_entrypoint
        outcomes, claimed = [], []
        for folder in discover(extensions_dir):
            known = set(self._replaces)
            outcome = self._load_one(folder, api, importer, saved)
            outcomes.append(outcome)
            claimed.append((outcome, set(self._replaces) - known))
        self._resolve_alias_conflicts(claimed)
        return outcomes

    def _resolve_alias_conflicts(self, claimed):
        """Fail safe on alias-equivalent override conflicts (rule 3 / D18).

        ``claimed`` pairs each loaded extension's outcome with the ``replaces``
        bases it declared. An alias conflict applies **no** override — the
        built-in stays and both extensions are reported disabled — so load
        order never decides a winner.
        """
        conflicted = self._alias_conflict_bases()
        if not conflicted:
            return
        reason = self._alias_conflict_reason(conflicted)
        for base in conflicted:
            winner = self._replaces.pop(base, None)
            if winner is not None:
                self._providers.pop(winner, None)
        for outcome, bases in claimed:
            if bases & conflicted:
                outcome["status"] = "disabled"
                outcome["reason"] = reason

    def _saved_veto(self, ext_id, declared_bases, saved):
        """Veto reason if a saved winner pre-empts this extension (D18).

        ``saved`` is ``{base_id: extension_id}`` from Options.json. A saved
        winner is a user preference that pre-empts discovery-order conflict
        resolution: any *other* extension claiming the same provider — by the
        same id or an alias (rule (b) callable identity) — is disabled with
        this reason instead of reaching the auto-resolution path.
        """
        if not saved or not declared_bases:
            return None
        table = self._rg.TRANSLATORS
        for base in declared_bases:
            fn = table.get(base)
            if fn is None:
                continue
            for saved_base, winner in saved.items():
                if winner == ext_id:
                    continue
                if table.get(saved_base) is fn:
                    return ("saved winner for %r is %r: the user must pick "
                            "the winner" % (saved_base, winner))
        return None


    def _load_one(self, folder, api, importer, saved=None):
        try:
            manifest = read_manifest(folder)
        except ManifestError as exc:
            return {"path": folder, "id": None, "status": "disabled",
                    "reason": str(exc)}

        ext_id = manifest["id"]
        veto = self._saved_veto(ext_id, manifest.get("replaces", []), saved)
        if veto is not None:
            # A saved winner pre-empts this extension (D18); it never reaches
            # auto-resolution, so discovery order stays irrelevant.
            return {"path": folder, "id": ext_id, "status": "disabled",
                    "reason": veto}

        providers, replaces = dict(self._providers), dict(self._replaces)
        try:
            register = importer(folder, manifest)
            register(api)
        except Exception as exc:
            # Fail-open + rollback: a half-applied extension never wins,
            # so the built-in stays active (rules 3 and 4).
            self._providers, self._replaces = providers, replaces
            return {"path": folder, "id": ext_id,
                    "status": "disabled",
                    "reason": "%s: %s" % (type(exc).__name__, exc)}
        for base in manifest.get("replaces", []):
            self._claims.setdefault(base, []).append(ext_id)
        return {"path": folder, "id": ext_id, "status": "loaded",
                "reason": None}


def read_saved_overrides(cfg=None):
    """Read the user's saved override winners from Options.json (D18).

    Returns ``{base_id: extension_id}``. Fails open to ``{}`` when the
    config cannot be read (no Options.json yet, or unreadable) — a missing
    selection simply means "no winner picked".
    """
    if cfg is None:
        try:
            from qtranslate import config as _C
            cfg = _C.load()
        except Exception:
            return {}
    if not isinstance(cfg, dict):
        return {}
    ov = cfg.get(OVERRIDES_SECTION, {})
    if not isinstance(ov, dict):
        return {}
    return {k: v for k, v in ov.items()
            if isinstance(k, str) and isinstance(v, str) and k and v}


def write_saved_overrides(overrides, cfg=None):
    """Persist the user's saved override winners to Options.json (D18).

    ``overrides`` is ``{base_id: extension_id}``. When ``cfg`` is a dict the
    section is merged into it and the updated dict is returned (test path);
    when ``cfg`` is ``None`` the live Options.json is loaded, updated, and
    saved. Never raises — a failed write leaves the previous selection.
    """
    overrides = {k: v for k, v in (overrides or {}).items()
                 if isinstance(k, str) and isinstance(v, str) and k and v}
    if cfg is None:
        try:
            from qtranslate import config as _C
            cfg = _C.load()
            if not isinstance(cfg, dict):
                cfg = {}
            cfg[OVERRIDES_SECTION] = dict(overrides)
            _C.save(cfg)
            return cfg
        except Exception:
            return {}
    if not isinstance(cfg, dict):
        return {}
    cfg[OVERRIDES_SECTION] = dict(overrides)
    return cfg


def load_user_extensions(manager=None, extensions_dir=None, registry=None,
                        saved=None):
    """Load the per-user extensions into Core's live dispatch table (D16).

    Resolves the folder through the ``Paths`` adapter when not given, loads
    it fail-open (``ExtensionManager.load_dir``), and **commits** the winners
    so an extension provider actually serves translations instead of only
    living in the manager's private dict. Returns the ``load_dir`` report
    (empty when the folder cannot be resolved); never raises for a bad
    folder or a bad extension.

    ``saved`` is the user's persisted winner selection
    (``{base_id: extension_id}``, D18). When ``None`` it is read from
    Options.json. A saved winner pre-empts discovery-order conflict
    resolution; a saved winner whose extension is no longer installed is
    cleared (the built-in stays).

    Wiring point for ``app.main``; kept here, not in ``app``, so it stays
    tkinter-free and testable headless.

    The manager the extensions were loaded into is available afterwards
    through ``last_manager()`` -- a host that renders UI contributions
    needs the registry the contributions live in, and the manager is
    created here. It is a module-level "last one loaded" handle, which
    is enough for a single front end per process.
    """
    manager = manager if manager is not None else ExtensionManager(registry)
    global _LAST_MANAGER
    _LAST_MANAGER = manager
    if extensions_dir is None:
        try:
            from qtranslate import platforms as _P
            extensions_dir = _P.current().extensions_dir()
        except Exception:
            return []
    if saved is None:
        saved = read_saved_overrides()
    report = manager.load_dir(extensions_dir, saved=saved)
    if any(item.get("status") == "loaded" for item in report):
        manager.commit(registry)
    # Clear stale saved winners: a winner that is no longer installed must
    # not pin a provider to a missing extension (fall back to the built-in).
    loaded_ids = {item["id"] for item in report
                  if item.get("status") == "loaded"}
    valid = {b: w for b, w in saved.items() if w in loaded_ids}
    if valid != saved:
        write_saved_overrides(valid)
    return report


# The manager the last ``load_user_extensions`` call loaded into. A host
# that renders UI contributions reads ``manager.ui_slots`` from it.
_LAST_MANAGER = None


def last_manager():
    """The ExtensionManager the last load used, or None.

    A host needs it for the UI and theme slots: the contributions live
    in the manager's own registry, so without a handle to the manager
    the host cannot show what an extension registered.
    """
    return _LAST_MANAGER
