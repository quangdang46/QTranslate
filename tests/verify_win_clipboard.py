"""Manual verification for the Windows clipboard snapshot/restore path.

``qtranslate/clipboard.py`` gained a pure-ctypes Windows implementation
(``_win_snapshot`` / ``_win_restore``, ~lines 165-308) that captures EVERY
registered clipboard format -- not just CF_UNICODETEXT -- so a
translate-and-restore cycle cannot silently destroy an image, file list,
or rich text the user had copied. That code is compile-clean but had
never run on a real Windows clipboard when it was written; this script
is the check. It cannot run on macOS/Linux (``ctypes.windll`` does not
exist there), so it prints SKIP and exits 0 off Windows.

What it exercises, against the REAL system clipboard:

  1. Multi-format snapshot: plant CF_UNICODETEXT + CF_TEXT + a custom
     registered format, snapshot, verify every format's bytes are
     captured verbatim.
  2. Clobber + restore: overwrite the clipboard with unrelated text via
     ``clipboard.write_text``, restore the token, and verify EVERY
     original format is back byte-for-byte.
  3. Empty snapshot: empty the clipboard, snapshot (must be an empty
     list, not None), write text, restore -- clipboard must be empty
     again.
  4. Honest failure shapes: ``restore(None)`` is False, and a second
     restore of the same token still works (tokens are data, not
     handles, so they are reusable).

Manual steps (Windows):

  1. Clone/checkout the repo on a Windows machine.
  2. ``python -m venv .venv && .venv\\Scripts\\pip install -r requirements.txt``
     (only ``pyperclip`` is strictly needed for step 2's clobber write;
     everything else is stdlib ``ctypes``).
  3. Run ``.venv\\Scripts\\python tests\\verify_win_clipboard.py``.
  4. Expected: ``verify_win_clipboard: all checks ok`` and exit code 0.
     Any ``FAIL`` line names the broken assertion; paste the output into
     the bead/issue. To eyeball it too: copy an image in Paint, run the
     script's snapshot path indirectly via the app's translate flow.

Caveats:

  - Other apps holding the clipboard can make ``OpenClipboard`` fail;
    the code retries 10x10ms. If a check fails with "could not open",
    close clipboard-heavy apps and re-run.
  - Delayed-render formats (owners that render on demand, e.g. some
    Explorer "Copy as path" payloads) may return no bytes at snapshot
    time; the snapshot skips those formats rather than failing, which is
    the documented "do not restore what you cannot capture" contract.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fails = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fails.append("%s -- %s" % (name, detail))


def main() -> int:
    if sys.platform != "win32":
        print("SKIP: verify_win_clipboard exercises the Win32 clipboard "
              "API (ctypes.windll); run it on Windows. platform=%r"
              % sys.platform)
        return 0

    import ctypes
    from qtranslate import clipboard as CB

    user32, kernel32 = CB._win32_apis()
    user32.RegisterClipboardFormatW.argtypes = [ctypes.c_wchar_p]
    user32.RegisterClipboardFormatW.restype = ctypes.c_uint

    CF_TEXT = 1
    CF_UNICODETEXT = 13  # == CB.CF_UNICODETEXT

    def set_formats(entries):
        """Replace the clipboard contents with ``[(fmt, bytes), ...]``."""
        assert CB._win_open(user32), "OpenClipboard failed"
        try:
            assert user32.EmptyClipboard(), "EmptyClipboard failed"
            for fmt, data in entries:
                handle = kernel32.GlobalAlloc(CB._GMEM_MOVEABLE,
                                              max(1, len(data)))
                assert handle, "GlobalAlloc failed for fmt %r" % fmt
                ptr = kernel32.GlobalLock(handle)
                assert ptr, "GlobalLock failed for fmt %r" % fmt
                try:
                    if data:
                        ctypes.memmove(ptr, data, len(data))
                finally:
                    kernel32.GlobalUnlock(handle)
                assert user32.SetClipboardData(int(fmt), handle), \
                    "SetClipboardData failed for fmt %r" % fmt
        finally:
            user32.CloseClipboard()

    def read_formats():
        """``{fmt: bytes}`` for every format currently on the clipboard."""
        assert CB._win_open(user32), "OpenClipboard failed"
        try:
            out = {}
            fmt = 0
            while True:
                fmt = int(user32.EnumClipboardFormats(fmt) or 0)
                if not fmt:
                    break
                data = CB._win_format_bytes(kernel32, user32, fmt)
                if data is not None:
                    out[fmt] = data
            return out
        finally:
            user32.CloseClipboard()

    # --- 1. multi-format snapshot -------------------------------------
    custom_fmt = int(user32.RegisterClipboardFormatW(
        "QTranslateVerifyClipboardFormat"))
    ck("custom clipboard format registered", custom_fmt > 0,
       repr(custom_fmt))

    uni = "héllo wörld — verify ✓".encode("utf-16-le") + b"\x00\x00"
    ansi = b"plain ANSI payload \x01\x02"
    custom = bytes(range(256)) * 2  # 512 bytes, all byte values
    planted = [(CF_UNICODETEXT, uni), (CF_TEXT, ansi),
               (custom_fmt, custom)]
    set_formats(planted)

    snap = CB.snapshot()
    ck("snapshot returns a list", isinstance(snap, list), repr(snap))
    snap_map = dict(snap or [])
    for fmt, data in planted:
        ck("snapshot captured fmt %d verbatim" % fmt,
           snap_map.get(fmt) == data,
           "got %d bytes, want %d" % (len(snap_map.get(fmt, b"")),
                                      len(data)))

    # --- 2. clobber, then restore -------------------------------------
    ck("write_text clobbers the clipboard",
       CB.write_text("unrelated clobber text") is True)
    ck("clipboard content changed after clobber",
       read_formats().get(CF_UNICODETEXT) != uni)

    ck("restore returns True", CB.restore(snap) is True)
    restored = read_formats()
    for fmt, data in planted:
        ck("restore put fmt %d back byte-for-byte" % fmt,
           restored.get(fmt) == data,
           "got %r, want %r" % (restored.get(fmt), data))

    # restore(None) is the documented "do not restore" no-op
    ck("restore(None) returns False", CB.restore(None) is False)
    # a token is plain data -- restoring it twice must still succeed
    ck("second restore of same token works", CB.restore(snap) is True)

    # --- 3. empty snapshot restores emptiness -------------------------
    set_formats([])
    empty_snap = CB.snapshot()
    ck("snapshot of empty clipboard is an empty list",
       empty_snap == [], repr(empty_snap))
    CB.write_text("something")
    ck("restore of empty token returns True",
       CB.restore(empty_snap) is True)
    ck("clipboard is empty after restoring empty snapshot",
       read_formats() == {}, repr(read_formats()))

    # leave the user's clipboard with something harmless
    CB.write_text("")

    if fails:
        print("FAIL %d" % len(fails))
        for f in fails:
            print("  -", f)
        return 1
    print("verify_win_clipboard: all checks ok (%d assertions)" % n[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
