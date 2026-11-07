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
        from ctypes import windll as _wd
        return int(_wd.user32.GetClipboardSequenceNumber())
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
    restored item-for-item through NSPasteboard. Windows returns None
    for now: pyperclip only sees text, and a text-only restore would
    silently destroy rich clipboard content, which is worse than not
    restoring at all.
    """
    try:
        import sys
        if sys.platform == "darwin":
            return _darwin_snapshot()
    except Exception:
        return None
    return None


def restore(token) -> bool:
    """Put a ``snapshot()`` token back; True on success."""
    if token is None:
        return False
    try:
        import sys
        if sys.platform == "darwin":
            return _darwin_restore(token)
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
