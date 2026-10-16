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
