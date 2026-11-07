"""GAP_AUDIT_3 rows 5+6: selection-restore gate + clipboard seq wrap.

Row 5 (.tmp SelectionCaptureTest.kt:306-345): a copy that lands but
whose clipboard snapshot cannot be restored must NOT dispatch the
action. Upstream ``restoreWithRetry`` retries a BUSY clipboard up to 3
attempts (50ms apart), fails fast on any other failure, logs, and
reports RESTORE_FAILED. The port's ``copy_selection`` used to restore
in ``finally`` and ignore the result, so a permanent restore failure
still returned the captured text.

Row 6 (.tmp ClipboardMonitorsTest.kt:53-77): ``GetClipboardSequenceNumber``
returns a DWORD. The port read it with ctypes' default c_int restype, so
values above 2^31 came back NEGATIVE and the capture poll treated them
as a counter blink -- a wrap between mark and check never registered as
a change. Upstream maps 0/failure to "unavailable"; the port maps 0 to -1.

Everything is seam-injected or stubbed -- no real clipboard, no real
keystroke, no network. ``sys.platform``/``ctypes.windll`` are faked for
the Windows sequence path, the same trick regress_system_backends_win.py
uses to run win32 branches off Windows.
"""
from __future__ import annotations

import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


from qtranslate import clipboard as CB  # noqa: E402
from qtranslate import selection  # noqa: E402


# --- helpers ---------------------------------------------------------------

def _moving_seq():
    """A sequence seam whose counter moves once -- the copy lands."""
    state = {"n": 0}

    def seq():
        state["n"] += 1
        return 100 if state["n"] == 1 else 200
    return seq


def capture(restore, *, snapshot=lambda: object(), sleeps=None):
    """Run copy_selection with a proven copy and the given restore seam.

    Returns (text, restore_attempts, sleeps, last_reason).
    """
    sleeps = [] if sleeps is None else sleeps
    attempts = {"n": 0}

    def _restore(snap):
        attempts["n"] += 1
        return restore(snap)

    text = selection.copy_selection(
        backend=object(),
        send=lambda combo: True,
        read=lambda: "SELECTED",
        sequence=_moving_seq(),
        sleep=lambda s: sleeps.append(s),
        pressed=lambda key: False,
        snapshot=snapshot,
        restore=_restore)
    return text, attempts["n"], sleeps, selection.last_reason()


# === row 5: restore failure gates dispatch ==================================

# A successful restore lets the captured text through.
text, attempts, _sleeps, reason = capture(lambda snap: True)
ck("successful restore dispatches the captured text",
   text == "SELECTED" and attempts == 1 and reason == "ok",
   repr((text, attempts, reason)))

# Busy clipboard: retried up to RESTORE_MAX_ATTEMPTS, then dispatched
# once the restore finally succeeds (upstream 'restore retries a busy
# clipboard and dispatches only after restoring').
def _busy_twice(snap):
    _busy_twice.n += 1
    if _busy_twice.n <= 2:
        raise CB.ClipboardBusyError("busy")
    return True
_busy_twice.n = 0

sleeps = []
text, attempts, sleeps, reason = capture(_busy_twice, sleeps=sleeps)
ck("busy restore is retried and dispatches after success",
   text == "SELECTED" and attempts == 3 and reason == "ok",
   repr((text, attempts, reason)))
ck("busy retries wait RESTORE_RETRY_DELAY_S between attempts",
   sleeps.count(selection.RESTORE_RETRY_DELAY_S) == 2,
   repr(sleeps))

# Busy forever: bounded at 3 attempts, logged via last_reason, and the
# action is NOT dispatched (upstream 'permanent restore failure is
# bounded, logged, and not dispatched').
def _always_busy(snap):
    _always_busy.n += 1
    raise CB.ClipboardBusyError("still busy")
_always_busy.n = 0

text, attempts, _sleeps, reason = capture(_always_busy)
ck("permanent busy restore is bounded at 3 attempts",
   attempts == selection.RESTORE_MAX_ATTEMPTS == 3, repr(attempts))
ck("permanent restore failure suppresses dispatch and is logged",
   text == "" and reason == "restore-failed",
   repr((text, reason)))

# Non-busy failure: upstream 'non-busy restore failure does not retry' --
# a plain False or any other exception is permanent, ONE attempt.
text, attempts, _sleeps, reason = capture(lambda snap: False)
ck("permanent (False) restore fails after one attempt, no dispatch",
   attempts == 1 and text == "" and reason == "restore-failed",
   repr((attempts, text, reason)))


def _denied(snap):
    raise PermissionError("denied")

text, attempts, _sleeps, reason = capture(_denied)
ck("non-busy exception restore fails after one attempt, no dispatch",
   attempts == 1 and text == "" and reason == "restore-failed",
   repr((attempts, text, reason)))

# A failed capture still owes the restore, and a failed restore still
# reports restore-failed over the capture's own empty result: the copy
# landed (sequence moved) but the read produced "".
def _empty_read_capture():
    sleeps = []
    attempts = {"n": 0}

    def _restore(snap):
        attempts["n"] += 1
        return False

    state = {"n": 0}

    def seq():
        state["n"] += 1
        return 100 if state["n"] == 1 else 200

    text = selection.copy_selection(
        backend=object(), send=lambda c: True, read=lambda: "",
        sequence=seq, sleep=lambda s: sleeps.append(s),
        pressed=lambda k: False,
        snapshot=lambda: object(), restore=_restore)
    return text, attempts["n"], selection.last_reason()

text, attempts, reason = _empty_read_capture()
ck("restore is still attempted when the capture read nothing",
   attempts == 1 and text == "" and reason == "restore-failed",
   repr((attempts, text, reason)))

# Snapshot failure: copy is never synthesized and restore is never owed.
text, attempts, _sleeps, reason = capture(
    lambda snap: True, snapshot=lambda: None)
ck("snapshot failure skips copy and never restores",
   text == "" and attempts == 0 and reason == "snapshot-failed",
   repr((text, attempts, reason)))


# === row 6: DWORD wrap + zero/failure -> unavailable ========================

REAL_PLATFORM = sys.platform


class _FakeSeqFn:
    """Stand-in for the ctypes GetClipboardSequenceNumber function object:
    records the restype/argtypes the port pins, then replays a script."""

    def __init__(self, script):
        self.script = list(script)
        self.restype = None
        self.argtypes = None
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if not self.script:
            raise AssertionError("sequence called more than scripted")
        return self.script.pop(0)


import contextlib  # noqa: E402
import ctypes as _ctypes  # noqa: E402


@contextlib.contextmanager
def _fake_user32(fn):
    """Fake sys.platform='win32' + ctypes.windll for one block."""
    saved_platform = sys.platform
    saved_windll = getattr(_ctypes, "windll", None)
    had_windll = hasattr(_ctypes, "windll")
    sys.platform = "win32"
    _ctypes.windll = types.SimpleNamespace(
        user32=types.SimpleNamespace(GetClipboardSequenceNumber=fn))
    try:
        yield
    finally:
        sys.platform = saved_platform
        if had_windll:
            _ctypes.windll = saved_windll
        else:
            try:
                del _ctypes.windll
            except AttributeError:
                pass


# DWORD wrap: values above 2^31 must come back UNSIGNED (positive), not
# negative -- the c_int restype bug read them as a counter blink.
fn = _FakeSeqFn([0x80000000, 0xFFFFFFFE])
with _fake_user32(fn):
    seq = CB.sequence()
    ck("sequence reads DWORD values above 2^31 as unsigned",
       seq == 0x80000000, repr(seq))
    ck("sequence pins c_uint32 restype (not the signed c_int default)",
       fn.restype == _ctypes.c_uint32, repr(fn.restype))
    ck("sequence pins empty argtypes", fn.argtypes == [], repr(fn.argtypes))
    seq2 = CB.sequence()
    ck("sequence near the DWORD top stays positive",
       seq2 == 0xFFFFFFFE, repr(seq2))

# 0 is the API's failure value -> "unavailable" (-1), never a token.
with _fake_user32(_FakeSeqFn([0])):
    got = CB.sequence()
ck("sequence 0 maps to unavailable (-1), not a zero token",
   got == -1, repr(got))

# A raising native call is still honest -1.
class _BoomFn:
    restype = None
    argtypes = None

    def __call__(self):
        raise OSError("user32 gone")

with _fake_user32(_BoomFn()):
    got = CB.sequence()
ck("sequence failure maps to -1", got == -1, repr(got))

# The capture poll itself must register a wrap as a change: mark at the
# top of the DWORD range, check just past it -- upstream tokens only
# compare for inequality, so ANY different unsigned value is a change.
def _wrap_seq(pairs):
    vals = iter(pairs)
    return lambda: next(vals)

# 0x7FFFFFFF -> 0x80000000: the exact boundary the signed restype broke.
sleeps = []
text = selection.copy_selection(
    backend=object(), send=lambda c: True, read=lambda: "NEW",
    sequence=_wrap_seq([0x7FFFFFFF, 0x80000000]),
    sleep=lambda s: sleeps.append(s), pressed=lambda k: False,
    snapshot=lambda: object(), restore=lambda s: True)
ck("DWORD wrap across 2^31 registers as a clipboard change",
   text == "NEW", repr(text))

# Full wrap: 0xFFFFFFFF -> 1 still compares unequal -> change.
sleeps = []
text = selection.copy_selection(
    backend=object(), send=lambda c: True, read=lambda: "NEW",
    sequence=_wrap_seq([0xFFFFFFFF, 1]),
    sleep=lambda s: sleeps.append(s), pressed=lambda k: False,
    snapshot=lambda: object(), restore=lambda s: True)
ck("DWORD wrap at the top of the range registers as a change",
   text == "NEW", repr(text))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_gap3_clipboard: all checks ok (%d assertions)" % n[0])
