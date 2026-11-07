"""Application notifications: the port of .tmp's ``NotificationBus``.

Ported from ``.tmp/QTranslate/core``:
``core/shared/notification/NotificationBus.kt``, ``AppNotification.kt``,
``NotificationCode.kt`` and ``api/plugin/NotificationType.kt``.

Semantics carried over honestly:

- the bus is a fire-and-forget stream: ``post()`` never blocks and a
  notification with no listeners is still recorded;
- the last ``REPLAY`` notifications are buffered, and a NEW subscriber is
  immediately replayed the ones younger than ``REPLAY_FRESHNESS_MS``
  (Kotlin's ``MutableSharedFlow(replay = 10)`` plus the
  ``REPLAY_FRESHNESS_MS = 5_000`` freshness filter) — so a UI that
  subscribes after a rebuild does not see stale messages, but one that
  subscribes promptly does see what was posted just before;
- there is NO deduplication and NO persistence: every post is a distinct
  event, and nothing survives a restart.

The core side of the port knows nothing about Qt: ``qtranslate.qt.notify``
is the surface (toast popups), and features call ``notify(...)`` /
``QtApp.notify(...)`` from any thread — the bus itself is thread-safe.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from enum import Enum


class Severity(Enum):
    """``NotificationType``: INFO / WARNING / ERROR (api/plugin)."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Notification:
    """``AppNotification``: one posted notification.

    ``code`` is the port's stand-in for ``NotificationCode`` — a free-form
    string tag the surface may switch on (the Kotlin sealed class's
    ``Custom`` case is what the plugin system posts; the port keeps the
    user-visible ``title``/``body`` on the notification itself, which is
    what ``ScopedPluginContext.notify`` resolves before posting).
    """

    __slots__ = ("severity", "title", "body", "code", "source", "timestamp")

    def __init__(self, severity, title, body, code=None, source=None,
                 timestamp=None):
        self.severity = severity
        self.title = title
        self.body = body
        self.code = code
        self.source = source
        # Wall-clock post time, like Kotlin's ``System.currentTimeMillis()``:
        # it exists only to age out replayed entries.
        self.timestamp = time.time() if timestamp is None else timestamp

    def __repr__(self):
        return ("Notification(%r, %r, %r)" %
                (self.severity, self.title, self.body))


# Kotlin's replay buffer and freshness window, kept as the same numbers.
REPLAY = 10
REPLAY_FRESHNESS_MS = 5_000


class NotificationBus:
    """The stream. One instance per process; see ``default_bus``."""

    def __init__(self):
        self._lock = threading.Lock()
        self._recent = deque(maxlen=REPLAY)
        self._handlers = []

    def post(self, notification):
        """Append and fan out. Never raises into the caller."""
        with self._lock:
            self._recent.append(notification)
            handlers = list(self._handlers)
        for handler in handlers:
            try:
                handler(notification)
            except Exception:               # noqa: BLE001 -- fail-open
                pass

    def subscribe(self, handler):
        """Register ``handler`` and replay the fresh backlog to it.

        The replay happens synchronously under no lock (handlers run on
        the posting thread, like a SharedFlow collector), and only
        notifications younger than ``REPLAY_FRESHNESS_MS`` are delivered
        — the Kotlin ``filter { now - it.timestamp < 5_000 }``.
        """
        with self._lock:
            self._handlers.append(handler)
            backlog = list(self._recent)
        cutoff = time.time() - REPLAY_FRESHNESS_MS / 1000.0
        for n in backlog:
            if n.timestamp >= cutoff:
                try:
                    handler(n)
                except Exception:           # noqa: BLE001 -- fail-open
                    pass

    def unsubscribe(self, handler):
        with self._lock:
            try:
                self._handlers.remove(handler)
            except ValueError:
                pass


_default = NotificationBus()


def default_bus():
    return _default


def notify(severity, title, body, code=None, source=None, bus=None):
    """Post one notification — the module-level convenience every
    feature uses. ``severity`` is a ``Severity`` (or its string value);
    unknown strings degrade to WARNING rather than raising."""
    if not isinstance(severity, Severity):
        try:
            severity = Severity(str(severity).lower())
        except Exception:
            severity = Severity.WARNING
    n = Notification(severity, str(title), str(body),
                     code=code, source=source)
    (bus or _default).post(n)
    return n
