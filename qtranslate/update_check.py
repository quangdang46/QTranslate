"""GitHub Releases update check — the live feed the native app's
retired manifest endpoint was replaced by.

The Kotlin reference (``core/.../updater/Updater.kt`` in the upstream
QTranslate tree) checks
``GET https://api.github.com/repos/ahatem/qtranslate/releases/latest``
and compares the latest tag against the running version with semantic
ordering. This module is the Python port of that check: same endpoint,
same compare, typed result instead of exceptions. No credentials are
sent; the request carries only a descriptive User-Agent, which the
GitHub API requires.

``APP_VERSION`` is the version this port replicates: the clean-room
re-implementation of native QTranslate 6.10.0 (see
``qtranslate/screens.py``, ``qtranslate/qt/main_window.py``). Releases
are published on THIS repository (``quangdang46/QTranslate``) — checking
the Kotlin rewrite's repo (``ahatem/qtranslate``, versioned 1.x) could
never report an update: 6.10.0 already compares newer than every tag
there.
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.request

APP_VERSION = "6.10.0"

RELEASES_URL = ("https://api.github.com/repos/quangdang46/QTranslate/"
                "releases/latest")
TIMEOUT_SECONDS = 10
_USER_AGENT = "qtranslate-re update-check"

# Release notes shown in the dialog are capped so a huge changelog
# cannot blow up the message box.
MAX_NOTES_CHARS = 4000


def _version_tuple(text: str) -> tuple:
    """Numeric version tuple from a tag like ``v1.2.3`` or ``6.10.0``.

    Non-numeric parts (``v`` prefix, ``-rc1`` suffixes) are ignored;
    missing components compare as 0, mirroring the reference's
    ``VersionInfo.isNewerThan`` leniency.
    """
    m = re.search(r"(\d+(?:\.\d+)*)", text or "")
    if not m:
        return ()
    return tuple(int(p) for p in m.group(1).split("."))


def is_newer(tag: str, current: str = APP_VERSION) -> bool:
    """True when ``tag`` names a newer release than ``current``."""
    new, old = _version_tuple(tag), _version_tuple(current)
    if not new or not old:
        return False
    n = max(len(new), len(old))
    new += (0,) * (n - len(new))
    old += (0,) * (n - len(old))
    return new > old


def _error(message: str) -> dict:
    return {"status": "error", "error": message,
            "version": "", "notes": "", "url": ""}


def check_for_update(timeout: int = TIMEOUT_SECONDS) -> dict:
    """Query the latest GitHub release.

    Returns a dict::

        {"status": "update" | "current" | "error",
         "version": latest tag (e.g. "v1.5.0"),
         "notes":   release notes body (may be ""),
         "url":     release page URL,
         "error":   safe human-readable message on "error"}

    Never raises for network/parse failures — the caller is a UI
    thread-adjacent worker and must always get a result to display.
    """
    req = urllib.request.Request(
        RELEASES_URL,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        return _error("the update server answered HTTP %d" % exc.code)
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        return _error("could not reach the update server (%s)" % reason)
    except (TimeoutError, OSError) as exc:
        return _error("the update check timed out or failed (%s)" % exc)

    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except (ValueError, UnicodeDecodeError):
        return _error("the update server sent an unreadable reply")
    if not isinstance(data, dict):
        return _error("the update server sent an unreadable reply")

    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        return _error("the update server reply had no version tag")

    notes = str(data.get("body") or "").strip()
    if len(notes) > MAX_NOTES_CHARS:
        notes = notes[:MAX_NOTES_CHARS].rstrip() + "\n…"
    url = str(data.get("html_url") or "").strip()

    if is_newer(tag):
        return {"status": "update", "version": tag, "notes": notes,
                "url": url, "error": ""}
    return {"status": "current", "version": tag, "notes": notes,
            "url": url, "error": ""}


# ---------------------------------------------------------------------------
# Startup auto-check, the shared result dialog, and the tray's manual check.
#
# The Kotlin reference checks on EVERY start (``MainStore.init`` calls
# ``checkForUpdates()``, gated only by the auto-check setting); this port
# adds the once-per-interval throttle the feature calls for. The last
# attempt time lives in the ``Update`` config section under
# ``LAST_CHECK_KEY`` (epoch seconds) so a fresh install or a toggled
# setting still checks promptly while a checked-recently install stays
# quiet.
# ---------------------------------------------------------------------------

AUTO_CHECK_INTERVAL_DAYS = 7
LAST_CHECK_KEY = "LastCheckAt"

_auto_started = False
_bridge = None
_active_app = None


def _update_section() -> dict:
    try:
        from qtranslate import config as _C
        return (_C.load() or {}).get("Update", {}) or {}
    except Exception:
        return {}


def auto_check_due(now: float | None = None,
                   section: dict | None = None) -> bool:
    """True when the startup auto-check should run now.

    Respects the same ``Update.CheckForUpdates`` switch the Options page
    checkbox writes (absent means enabled, matching the page's own
    ``upd.get("CheckForUpdates", True)`` default) and the interval since
    ``LAST_CHECK_KEY`` was stamped.
    """
    upd = _update_section() if section is None else section
    if not bool(upd.get("CheckForUpdates", True)):
        return False
    try:
        last = float(upd.get(LAST_CHECK_KEY) or 0.0)
    except (TypeError, ValueError):
        last = 0.0
    now = time.time() if now is None else now
    return (now - last) >= AUTO_CHECK_INTERVAL_DAYS * 86400


def _mark_checked(now: float | None = None) -> None:
    try:
        from qtranslate import config as _C
        cfg = _C.load() or {}
        cfg.setdefault("Update", {})[LAST_CHECK_KEY] = (
            time.time() if now is None else now)
        _C.save(cfg)
    except Exception:
        pass


def _parent_widget(app):
    """The dialog's parent: a QWidget is used as-is (the Options page
    passes itself), otherwise the app's main window, else None (a
    parentless modal still blocks correctly)."""
    try:
        from PySide6.QtWidgets import QWidget
        if isinstance(app, QWidget):
            return app
    except Exception:
        pass
    win = getattr(app, "win", None)
    if win is None:
        return None
    try:
        from PySide6.QtWidgets import QWidget as _W
        return win if isinstance(win, _W) else None
    except Exception:
        return None


def show_update_result(app, res: dict) -> None:
    """The result dialog, shared by the Options page, the tray's manual
    check, and the startup auto-check. ``app`` is the QtApp (or anything
    with a ``win`` widget / nothing at all)."""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QMessageBox

    parent = _parent_widget(app)
    status = res.get("status")
    if status == "update":
        notes = res.get("notes") or "(no release notes)"
        box = QMessageBox(parent)
        box.setWindowTitle("Updates")
        box.setText(
            "A new version %s is available "
            "(you have %s).\n\n%s"
            % (res.get("version", "?"), APP_VERSION, notes))
        open_btn = None
        if res.get("url"):
            open_btn = box.addButton(
                "Open release page", QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Close)
        box.exec()
        if open_btn is not None and box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl(res["url"]))
    elif status == "current":
        QMessageBox.information(
            parent, "Updates",
            "QTranslate %s is up to date." % APP_VERSION)
    else:
        QMessageBox.warning(
            parent, "Updates",
            "Update check failed: %s"
            % res.get("error") or "unknown error")


def _ensure_bridge():
    """The QObject that carries the worker's result onto the UI thread.

    Must be called on the UI thread (``maybe_auto_check`` /
    ``check_now`` are): emitting ``result`` from the daemon thread then
    lands in ``_on_result`` as a queued call, the same pattern
    ``QtApp.invoke`` and the Options page's ``_UpdateBridge`` use.
    """
    global _bridge
    if _bridge is not None:
        return _bridge
    from PySide6.QtCore import QObject, Signal

    class _Bridge(QObject):
        result = Signal(object)   # (result dict, auto: bool)

    _bridge = _Bridge()
    _bridge.result.connect(_on_result)
    return _bridge


def _on_result(payload) -> None:
    res, auto = payload
    # The auto-check is silent unless an update is actually available;
    # the manual checks (Options page, tray) always show the outcome.
    if auto and res.get("status") != "update":
        return
    show_update_result(_active_app, res)


def _spawn_check(auto: bool) -> None:
    def work():
        try:
            res = check_for_update()
        except Exception as exc:            # noqa: BLE001 -- belt+braces
            res = _error("the update check failed (%s)" % exc)
        try:
            _ensure_bridge().result.emit((res, auto))
        except Exception:                   # noqa: BLE001
            pass

    threading.Thread(target=work, daemon=True,
                     name="qtranslate-update-check").start()


def maybe_auto_check(app) -> bool:
    """The startup hook: run the throttled auto-check once per interval.

    Call on the UI thread once the app is up (``Tray.show`` does this —
    ``app.py``'s ``main`` calls ``app.tray.show()`` right after building
    the tray). Returns True when a check was started. Silent unless an
    update is found; the timestamp is stamped BEFORE the network call so
    a failed check does not retry on every launch.
    """
    global _auto_started, _active_app
    if _auto_started:
        return False
    if not auto_check_due():
        return False
    _auto_started = True
    _active_app = app
    _mark_checked()
    _ensure_bridge()
    _spawn_check(auto=True)
    return True


def check_now(app) -> None:
    """The tray's "Check for updates..." entry: an unconditional check
    whose result (up-to-date, new version, or error) is always shown."""
    global _active_app
    _active_app = app
    _ensure_bridge()
    _spawn_check(auto=False)
