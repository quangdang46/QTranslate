"""Core secrets store — credentials that must never ride in Options.json.

Upstream (.tmp ``NetworkConfig`` + ``NetworkConfigMappingTest``) keeps the
proxy password in a SecretStore, deliberately OUTSIDE the persisted
configuration: ``NetworkConfig`` has no password field at all, and the
secret-store key is ``"network.proxy.password"``. The port used to write
``Proxy.Password`` straight into Options.json — a plain, exportable,
screenshottable JSON file.

This module is the core-side equivalent of the per-extension
``secrets.json`` in ``extensions.py``: one flat JSON map next to
Options.json (``<app data>/secrets.json``), written atomically
(tmp+rename, same discipline as ``config.save``) and chmod 0600
best-effort. Reads fail open to ``{}`` — a broken store must not take
the app down.

Only strings are stored, like upstream's ``SecretStore.put``.
"""
import json
import os

from qtranslate.platforms import app_data_dir

# Same directory as Options.json (config.DEFAULT_PATH), different file.
DEFAULT_PATH = os.path.join(app_data_dir(), "secrets.json")


def path_for(options_path):
    """The secrets file that sits NEXT TO a given Options.json.

    ``config.load`` resolves ``DEFAULT_PATH`` at call time, so a test (or
    tool) that points Options.json elsewhere must get the secrets file
    beside THAT file, not the real one -- same rule the Kotlin
    SecretStore follows (one store per settings location).
    """
    return os.path.join(os.path.dirname(os.path.abspath(options_path)),
                        "secrets.json")

# Upstream's secret-store key for the manual-proxy password
# (core/settings/data/NetworkConfig.kt: ``proxyPasswordKey``).
PROXY_PASSWORD_KEY = "network.proxy.password"


def _chmod_private(path):
    """Best-effort owner-only permissions.

    POSIX: chmod 0600. Windows: os.chmod cannot express per-user ACLs,
    so strip inheritance and grant only the current user via icacls
    (the secrets file holds the proxy password -- it must not be
    readable by other accounts on a shared machine).
    """
    try:
        if os.name == "nt":
            import getpass
            import subprocess
            user = getpass.getuser()
            subprocess.run(
                ["icacls", path, "/inheritance:r", "/grant:r",
                 "%s:F" % user],
                capture_output=True, timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return
        os.chmod(path, 0o600)
    except Exception:
        pass


def _load(path=None):
    """The whole secret map; {} on any read problem."""
    if path is None:
        path = DEFAULT_PATH
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    _chmod_private(path)
    return {str(k): v for k, v in data.items() if isinstance(v, str)}


def _save(data, path=None):
    """Atomically write the secret map, owner-only where supported."""
    if path is None:
        path = DEFAULT_PATH
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    _chmod_private(tmp)
    os.replace(tmp, path)
    _chmod_private(path)


def get(key, default=None, path=None):
    """One stored secret, or ``default``."""
    return _load(path).get(key, default)


def set(key, value, path=None):
    """Persist one secret; returns ``value``.

    String-only, like upstream's ``SecretStore.put``: a non-string value
    raises ``TypeError`` at the call site instead of being silently
    coerced into the file.
    """
    if not isinstance(key, str) or not key:
        raise ValueError("secret key must be a non-empty string")
    if not isinstance(value, str):
        raise TypeError("secret value must be a string")
    data = _load(path)
    data[key] = value
    _save(data, path)
    return value


def delete(key, path=None):
    """Remove one secret; no-op when absent."""
    if not isinstance(key, str) or not key:
        raise ValueError("secret key must be a non-empty string")
    data = _load(path)
    if key in data:
        del data[key]
        _save(data, path)


def migrate_options(cfg, path=None):
    """Move a plaintext ``Proxy.Password`` out of a loaded Options dict.

    Returns True when the dict was changed (the caller should persist it
    so the plaintext leaves the file). The value lands under upstream's
    own secret key, ``network.proxy.password``. An absent or empty
    password changes nothing -- empty strings carry no secret and the
    key itself is dropped by ``config.DEFAULT_PROXY`` going forward.
    """
    try:
        px = (cfg or {}).get("Proxy")
        if not isinstance(px, dict) or "Password" not in px:
            return False
        pw = px["Password"]
        # Store BEFORE popping: if the secrets write fails, the config
        # keeps its plaintext so nothing is silently lost -- the next
        # load simply retries the migration.
        if pw:
            set(PROXY_PASSWORD_KEY, str(pw), path=path)
        del px["Password"]
        return True
    except Exception:
        return False
