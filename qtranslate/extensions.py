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
        sys.modules.pop(full_name, None)
        raise

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


class ExtensionManager:
    """Manager over ``registry``: built-ins plus loaded extensions."""

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

    # -- directory loading (Slice 7) ------------------------------------
    def load_dir(self, extensions_dir, api=None, importer=None):
        """Discover, validate and load every extension under a directory.

        Fail-open (``EXTENSION_SDK.md`` §7): one bad extension is disabled
        with a reason and the rest still load. Returns one outcome dict
        per discovered folder, sorted by folder name:
        ``{"path", "id", "status": "loaded"|"disabled", "reason"}``.

        ``api``/``importer`` are injectable so the loader is testable
        without touching the import machinery or a real folder.
        """
        api = api if api is not None else ExtensionAPI(self)
        importer = importer or import_entrypoint
        return [self._load_one(folder, api, importer)
                for folder in discover(extensions_dir)]

    def _load_one(self, folder, api, importer):
        try:
            manifest = read_manifest(folder)
        except ManifestError as exc:
            return {"path": folder, "id": None, "status": "disabled",
                    "reason": str(exc)}

        providers, replaces = dict(self._providers), dict(self._replaces)
        try:
            register = importer(folder, manifest)
            register(api)
        except Exception as exc:
            # Fail-open + rollback: a half-applied extension never wins,
            # so the built-in stays active (rules 3 and 4).
            self._providers, self._replaces = providers, replaces
            return {"path": folder, "id": manifest["id"],
                    "status": "disabled",
                    "reason": "%s: %s" % (type(exc).__name__, exc)}
        return {"path": folder, "id": manifest["id"], "status": "loaded",
                "reason": None}
