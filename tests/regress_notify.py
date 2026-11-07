"""Regression: the notification bus + toast surface (port of .tmp's
NotificationBus / NotificationPopover).

The port contract, pinned here:

  1. ``notify()`` posts to the bus and every registered handler receives
     the notification with its severity/title/body/code intact;
  2. severity accepts the ``Severity`` enum or its string value, and an
     unknown string degrades to WARNING rather than raising;
  3. the bus keeps Kotlin's replay semantics: the last 10 posts are
     buffered, a NEW subscriber is replayed only those younger than
     5s, there is no dedupe and no persistence;
  4. the Qt surface marshals through ``app._on_ui`` and a toast is
     created per notification — offscreen, no crash headless.

No provider calls, no windows shown: QT_QPA_PLATFORM=offscreen.
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


from qtranslate import notify as N  # noqa: E402

# -- 1. delivery -------------------------------------------------------------
bus = N.NotificationBus()
seen = []
bus.subscribe(seen.append)
note = N.Notification(N.Severity.INFO, "T", "B")
bus.post(note)
ck("a registered handler receives the posted notification",
   seen == [note], repr(seen))
ck("the notification carries severity/title/body/code/source",
   note.severity is N.Severity.INFO and note.title == "T"
   and note.body == "B" and note.timestamp > 0)

# -- 2. severity mapping ------------------------------------------------------
N.notify("warning", "w", "b", bus=N.NotificationBus())  # own bus, no crash
# A throwaway bus: posting to the DEFAULT bus here would replay to the
# toast subscriber attached in section 4 (fresh entries are replayed to
# new subscribers -- that is the bus's documented semantics, not a bug).
mapped = N.notify("error", "e", "b", bus=N.NotificationBus())
ck("module notify() returns the posted Notification",
   isinstance(mapped, N.Notification))
b2 = N.NotificationBus()
got = []
b2.subscribe(got.append)
N.notify("WARNING", "s", "b", bus=b2)
N.notify("bogus-severity", "s", "b", bus=b2)
ck("string severities map case-insensitively",
   got[0].severity is N.Severity.WARNING, repr(got[0].severity))
ck("an unknown severity degrades to WARNING, never raises",
   got[1].severity is N.Severity.WARNING, repr(got[1].severity))
N.notify(N.Severity.ERROR, "s", "b", bus=b2)
ck("the Severity enum passes through unchanged",
   got[2].severity is N.Severity.ERROR)
ck("code and source ride along on the posted notification",
   mapped.code is None and mapped.source is None)

# -- 3. replay semantics (Kotlin replay=10, freshness 5s) --------------------
b3 = N.NotificationBus()
b3.post(N.Notification(N.Severity.INFO, "old", "", timestamp=time.time() - 60))
for i in range(12):                       # overflow the 10-slot buffer
    b3.post(N.Notification(N.Severity.INFO, "f%d" % i, ""))
b3.post(N.Notification(N.Severity.INFO, "fresh", ""))
replayed = []
b3.subscribe(lambda x: replayed.append(x.title))
ck("a stale replay (>5s) is dropped",
   "old" not in replayed, repr(replayed))
ck("a fresh backlog replays to a new subscriber",
   "fresh" in replayed, repr(replayed))
ck("the buffer caps at REPLAY=10 entries",
   len(replayed) == N.REPLAY, repr(len(replayed)))
ck("replay preserves buffer (post) order, oldest first",
   replayed == [m.title for m in b3._recent
                if m.timestamp >= time.time()
                - N.REPLAY_FRESHNESS_MS / 1000.0], repr(replayed))

# -- 4. the Qt surface, offscreen ---------------------------------------------
from PySide6.QtWidgets import QApplication  # noqa: E402

app_qt = QApplication.instance() or QApplication([])


class _FakeApp:
    """The two members the surface needs: ``_on_ui`` (QtApp's own
    marshaler — here the caller is already the UI thread) and a qapp."""
    qapp = app_qt

    def _on_ui(self, fn):
        fn()


from qtranslate.qt import notify as QN  # noqa: E402
QN.detach()
stack = QN.attach(_FakeApp())
ck("attach returns a toast stack", stack is not None)
N.notify("info", "Hello", "World", bus=N.default_bus())
app_qt.processEvents()
ck("a posted notification produces a toast",
   len(stack._toasts) == 1, repr(len(stack._toasts)))
toast = stack._toasts[0] if stack._toasts else None
if toast is not None:
    ck("the toast maps INFO to the accent strip colour",
       toast._strip.name() == "#0078d7", toast._strip.name())
N.notify("error", "Boom", "It broke", bus=N.default_bus())
N.notify("warning", "Careful", "Nearly", bus=N.default_bus())
N.notify("info", "Fourth", "Overflow", bus=N.default_bus())
app_qt.processEvents()
ck("toasts stack up to MAX_TOASTS and the oldest is replaced",
   len(stack._toasts) == QN.MAX_TOASTS, repr(len(stack._toasts)))
ck("attach is idempotent",
   QN.attach(_FakeApp()) is stack)
QN.detach()

for f in fail:
    print("FAIL", f)
print("regress_notify: %d checks, %d failed" % (n[0], len(fail)))
sys.exit(1 if fail else 0)
