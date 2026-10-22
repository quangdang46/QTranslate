"""The crash fail-fast path — port of `FUN_0040345B` -> `FUN_00403446`.

The coverage checklist's Q3 row described this as
"`__fastfail`/terminate". The image settles which: **`RaiseFailFastException`
is absent from the import table**, while `TerminateProcess` and
`UnhandledExceptionFilter` are both imported. So the mechanism is a
terminate, and the property that matters is that it **does not return** —
no unwinding, no destructors, no crash-report hook.

Python's equivalent is ``os._exit``. ``sys.exit()`` raises ``SystemExit``
and an uncaught exception runs ``finally`` blocks, ``atexit`` handlers and
``sys.excepthook`` — which would include this project's own crash-report
writer. That is exactly what native's fail-fast avoids, so using either
would invert the behaviour being ported.

The exception-code mapping is native's: ``-0x7FF8FFF2`` (the negative
literal `FUN_0040345B` tests) resolves to ``0xC0000017``
(``STATUS_NO_MEMORY``), and anything else to ``0xC000001D``
(``STATUS_ILLEGAL_INSTRUCTION``).
"""
import os
import sys

STATUS_NO_MEMORY = 0xC0000017
STATUS_ILLEGAL_INSTRUCTION = 0xC000001D

# The one negative literal FUN_0040345B recognises.
_NATIVE_NO_MEMORY = -0x7FF8FFF2


def resolve_code(code: int) -> int:
    """Map an incoming code the way `FUN_0040345B` does."""
    return STATUS_NO_MEMORY if code == _NATIVE_NO_MEMORY \
        else STATUS_ILLEGAL_INSTRUCTION


def fail_fast(code: int = 0) -> None:
    """Terminate immediately with the resolved Windows status code.

    Never returns. ``os._exit`` bypasses ``finally``, ``atexit`` and
    ``sys.excepthook`` -- which is the point: native's fail-fast runs
    nothing, and in particular does NOT let the crash-report writer see
    it.

    ``os._exit`` takes a C ``int``, so the 32-bit NTSTATUS
    (``0xC0000017``) has to be narrowed before it is passed. Passing it raw
    raises ``OverflowError`` from inside the fail-fast, which would be a
    Python traceback where native produces silence. Windows itself keeps
    only the low byte of a process exit code, so the value the parent
    observes is ``status & 0xFF`` anyway; the full NTSTATUS is what the
    mapping resolves to, and it is reported through
    :func:`resolve_code` for anyone comparing against native's constant.
    """
    status = resolve_code(code)
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:  # noqa: BLE001 -- the flush is best-effort
        pass
    os._exit(status & 0xFF)


# ---------------------------------------------------------------- reporter
# The once-crash reporter (native's row G). Native `FUN_00462C03`
# (decompiled 2026-10-15): if `Exceptions.json` exists, parse it,
# process the entries (`FUN_00462A82`), then `DeleteFileW` it -- so a
# crash is reported exactly ONCE, on the next launch, and the file is
# gone afterwards. The port mirrors that: the filter appends a type==2
# entry, and the next launch prints it and removes the file.
#
# These two live here, in Core, and not in a view: the crash reporter
# is a property of the APP, not of the toolkit that draws it.

def exceptions_path() -> str:
    """Where the crash entries live: next to the settings file."""
    from qtranslate import config as _C
    return os.path.join(os.path.dirname(_C.DEFAULT_PATH), "Exceptions.json")


def consume_crash_reports() -> None:
    """Read Exceptions.json, report the type==2 entries once, delete it.

    Port of ``FUN_00462C03``. The file is removed even when it holds
    nothing this run understands: native deletes it either way, and a
    file left behind would be reported again on every launch.
    """
    try:
        import json as _j
        path = exceptions_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as fh:
                entries = _j.load(fh)
        except Exception:
            entries = []
        for e in (entries or []):
            try:
                if isinstance(e, dict) and e.get("type") == 2:
                    print("[previous crash] %s" % e.get("path", e))
            except Exception:
                pass
        try:
            os.remove(path)
        except OSError:
            pass
    except Exception:
        pass


def install_crash_hook() -> None:
    """Unhandled-exception filter: append a type==2 entry to
    Exceptions.json so the next launch reports it once (native's
    minidump-writer equivalent; no dump, just the traceback)."""
    import traceback as _tb

    def _hook(typ, val, tb):
        try:
            import json as _j
            path = exceptions_path()
            try:
                with open(path, encoding="utf-8") as fh:
                    entries = _j.load(fh)
            except Exception:
                entries = []
            entries.append({"type": 2,
                            "path": "".join(
                                _tb.format_exception(typ, val, tb))[-2000:]})
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_j.dumps(entries, ensure_ascii=False))
        except Exception:
            pass
        sys.__excepthook__(typ, val, tb)

    sys.excepthook = _hook
