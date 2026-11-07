"""Clipboard helpers — port of the native clipboard primitives.

- `FUN_0043BE56` = clipboard WRITE: `OpenClipboard` → `EmptyClipboard` →
  `SetClipboardData(CF_UNICODETEXT=0xD)`.
- `FUN_0043BF30` = clipboard SEQUENCE poll: `GetClipboardSequenceNumber`
  (the Ctrl+C+C engine uses it to prove the copy landed).

The port uses `pyperclip` for read/write (equivalent to CF_UNICODETEXT)
and `ctypes` for the sequence number. Both are wrapped so the contract is
testable and so callers get an honest False / -1 on a missing backend
instead of an exception.
"""
from __future__ import annotations

CF_UNICODETEXT = 0xD  # 13, the format FUN_0043BE56 writes


class ClipboardBusyError(RuntimeError):
    """The clipboard stayed busy (another process holds it open) past the
    bounded open retries. The ONLY retryable restore failure -- every
    other restore failure is permanent. Selection capture retries this
    up to its attempt bound, exactly like .tmp's IllegalStateException
    branch in ``SelectionCapture.restoreWithRetry``."""


def write_text(text) -> bool:
    """Write text to the clipboard; True on success (native FUN_0043BE56)."""
    try:
        import pyperclip
        pyperclip.copy("" if text is None else str(text))
        return True
    except Exception:
        return False


def read_text() -> str:
    """Read the clipboard as text; "" when unavailable/empty."""
    try:
        import pyperclip
        return pyperclip.paste() or ""
    except Exception:
        return ""


def sequence() -> int:
    """Monotonic clipboard change counter (native FUN_0043BF30); -1 if
    the platform counter is unavailable.

    Windows: ``GetClipboardSequenceNumber``. macOS: NSPasteboard's
    ``changeCount`` — the same "did the pasteboard change" signal,
    reached through libobjc so no PyObjC dependency is added.
    """
    try:
        import sys
        if sys.platform == "darwin":
            return _darwin_change_count()
        import ctypes
        fn = ctypes.windll.user32.GetClipboardSequenceNumber
        # The API returns a DWORD -- UNSIGNED 32-bit. ctypes' default
        # c_int restype reads values above 2^31 as NEGATIVE, which the
        # capture poll would mistake for a counter blink (``now < 0``)
        # and never see the wrap as a change. c_uint32 keeps the whole
        # range positive so mark/check compare as plain unsigned
        # integers, matching .tmp WindowsClipboardChangeMonitor whose
        # tokens only ever compare for inequality.
        fn.restype = ctypes.c_uint32
        fn.argtypes = []
        seq = int(fn())
        # The API returns 0 on failure; upstream mark() maps 0 to
        # "unavailable" -- a zero token would compare unequal to almost
        # anything and fabricate changes.
        return seq if seq else -1
    except Exception:
        return -1


def snapshot():
    """Capture the clipboard's full contents for later restore.

    .tmp's ``SelectionCapture`` snapshots before synthesizing Copy and
    restores afterwards, so a translation trigger never clobbers what
    the user had copied (an image, a file, rich text -- not just a
    string). This returns an opaque token for ``restore()``, or None
    where a faithful snapshot is not possible; callers treat None as
    "do not restore" rather than risk destroying content they cannot
    put back.

    macOS: every pasteboard item, every declared type, the raw data --
    restored item-for-item through NSPasteboard. Windows: every
    registered clipboard format, the raw bytes behind each HGLOBAL --
    restored format-for-format through ``SetClipboardData`` (a text-only
    restore would silently destroy images/files/rich text, so this
    copies every format ``EnumClipboardFormats`` reports). Returns None
    only when the platform has no faithful snapshot or the clipboard
    could not be opened; callers treat None as "do not restore" rather
    than risk destroying content they cannot put back.
    """
    try:
        import sys
        if sys.platform == "darwin":
            return _darwin_snapshot()
        if sys.platform == "win32":
            return _win_snapshot()
    except Exception:
        return None
    return None


def restore(token) -> bool:
    """Put a ``snapshot()`` token back.

    True on success, False on a PERMANENT failure, and raises
    :class:`ClipboardBusyError` when the clipboard stayed busy past the
    bounded open retries -- the one failure a caller may retry
    (.tmp ``SelectionCapture.restoreWithRetry`` retries busy up to 3
    attempts and fails fast on anything else).
    """
    if token is None:
        return False
    try:
        import sys
        if sys.platform == "darwin":
            return _darwin_restore(token)
        if sys.platform == "win32":
            return _win_restore(token)
    except ClipboardBusyError:
        raise
    except Exception:
        return False
    return False


def _darwin_snapshot():
    """``[(pasteboardItem entries)]`` via PyObjC, or None on failure."""
    import AppKit  # noqa: F401  -- registers NSPasteboard with objc
    pb = AppKit.NSPasteboard.generalPasteboard()
    items = pb.pasteboardItems()
    snap = []
    for item in items or []:
        entries = []
        for pbtype in item.types() or []:
            data = item.dataForType_(pbtype)
            if data is not None:
                entries.append((pbtype, data))
        snap.append(entries)
    return snap


def _darwin_restore(snap) -> bool:
    import AppKit  # noqa: F401
    pb = AppKit.NSPasteboard.generalPasteboard()
    pb.clearContents()
    objects = []
    for entries in snap:
        item = AppKit.NSPasteboardItem.alloc().init()
        for pbtype, data in entries:
            item.setData_forType_(data, pbtype)
        objects.append(item)
    if not objects:
        return True
    return bool(pb.writeObjects_(objects))


def _darwin_change_count() -> int:
    """``NSPasteboard.generalPasteboard.changeCount`` via raw libobjc.

    objc_msgSend is variadic, so each call site pins its own restype:
    ``generalPasteboard`` returns an object pointer, ``changeCount``
    returns NSInteger (a long). -1 on any failure — the caller treats
    that as "counter unavailable" and takes the bounded single-read
    path, exactly like the Windows fallback.
    """
    import ctypes
    # NSPasteboard lives in AppKit; without loading the framework
    # objc_getClass cannot resolve the class name.
    ctypes.CDLL("/System/Library/Frameworks/AppKit.framework/AppKit")
    lib = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
    lib.objc_getClass.restype = ctypes.c_void_p
    lib.objc_getClass.argtypes = [ctypes.c_char_p]
    lib.sel_registerName.restype = ctypes.c_void_p
    lib.sel_registerName.argtypes = [ctypes.c_char_p]
    msg = lib.objc_msgSend
    cls = lib.objc_getClass(b"NSPasteboard")
    if not cls:
        return -1
    msg.restype = ctypes.c_void_p
    msg.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    pb = msg(cls, lib.sel_registerName(b"generalPasteboard"))
    if not pb:
        return -1
    msg.restype = ctypes.c_long
    msg.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    return int(msg(pb, lib.sel_registerName(b"changeCount")))


# --- Windows snapshot/restore (pure ctypes, no pywin32 dependency) ------
#
# pywin32 is only an OPTIONAL extra in this project (``win32app.py`` is a
# standalone RE view); ``requirements.txt`` does not carry it, so the
# snapshot uses the Win32 clipboard API directly. A token is a list of
# ``(format, bytes)`` pairs -- the raw contents behind every HGLOBAL the
# clipboard currently offers. Byte copies are taken while the clipboard
# is open, so the handles never outlive ``CloseClipboard``; restore
# re-allocs a movable HGLOBAL per format and hands ownership to
# ``SetClipboardData`` (which frees it on success, so failures must
# ``GlobalFree`` explicitly).

_GMEM_MOVEABLE = 0x0002
_WIN_OPEN_RETRIES = 10
_WIN_OPEN_RETRY_S = 0.01


def _win32_apis():
    """``(user32, kernel32)`` with clipboard prototypes pinned, or raise."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EnumClipboardFormats.argtypes = [wintypes.UINT]
    user32.EnumClipboardFormats.restype = wintypes.UINT
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalSize.argtypes = [ctypes.c_void_p]
    kernel32.GlobalSize.restype = ctypes.c_size_t
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.restype = ctypes.c_void_p
    return user32, kernel32


def _win_open(user32, retries=_WIN_OPEN_RETRIES):
    """``OpenClipboard`` with a bounded retry -- another app holding the
    clipboard is transient, so a single-shot open would spuriously fail
    the whole capture."""
    import time
    for _ in range(max(1, retries)):
        if user32.OpenClipboard(None):
            return True
        time.sleep(_WIN_OPEN_RETRY_S)
    return False


def _win_format_bytes(kernel32, user32, fmt):
    """The bytes behind one clipboard format's HGLOBAL, or None when the
    format cannot be read right now (e.g. a delayed-render owner that
    declines to render)."""
    import ctypes
    handle = user32.GetClipboardData(fmt)
    if not handle:
        return None
    size = int(kernel32.GlobalSize(handle) or 0)
    ptr = kernel32.GlobalLock(handle)
    if not ptr:
        return None
    try:
        return ctypes.string_at(ptr, size) if size else b""
    finally:
        kernel32.GlobalUnlock(handle)


def _win_snapshot():
    """``[(format, bytes)]`` for every clipboard format, or None."""
    user32, kernel32 = _win32_apis()
    if not _win_open(user32):
        return None
    try:
        entries = []
        fmt = 0
        while True:
            fmt = int(user32.EnumClipboardFormats(fmt) or 0)
            if not fmt:
                break
            try:
                data = _win_format_bytes(kernel32, user32, fmt)
            except Exception:
                data = None
            if data is not None:
                entries.append((fmt, data))
        return entries
    finally:
        user32.CloseClipboard()


def _win_restore(token) -> bool:
    """Rebuild the clipboard from a ``_win_snapshot`` token.

    Empty token (the clipboard was empty at snapshot time) still clears
    the current contents -- that IS the faithful restore. Returns False
    when the clipboard could not be opened or a format could not be
    set; a partial restore is reported honestly rather than retried
    blindly (Kotlin retries on busy; the open retry above covers the
    common busy case).
    """
    import ctypes
    user32, kernel32 = _win32_apis()
    if not _win_open(user32):
        # OpenClipboard already retried its bounded busy window; still
        # locked means another process holds the clipboard -- the one
        # restore failure worth retrying (.tmp IllegalStateException).
        raise ClipboardBusyError("clipboard still busy after open retries")
    ok = True
    try:
        if not user32.EmptyClipboard():
            return False
        for fmt, data in token or []:
            # GlobalAlloc(0) is invalid; a zero-length payload still
            # needs a real (1-byte) movable block to hand over.
            handle = kernel32.GlobalAlloc(_GMEM_MOVEABLE,
                                          max(1, len(data)))
            if not handle:
                ok = False
                continue
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                kernel32.GlobalFree(handle)
                ok = False
                continue
            try:
                if data:
                    ctypes.memmove(ptr, data, len(data))
            finally:
                kernel32.GlobalUnlock(handle)
            if not user32.SetClipboardData(int(fmt), handle):
                # SetClipboardData owns the handle on success only.
                kernel32.GlobalFree(handle)
                ok = False
        return ok
    finally:
        user32.CloseClipboard()
