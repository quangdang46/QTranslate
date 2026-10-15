"""Command-line argument parsing — port of `FUN_0043CD68` (row A9).

Native parses `GetCommandLineW` via `CommandLineToArgvW`, then applies
the positional overrides (service, target, theme) over the restored
session — an explicit launch wins over remembered state. The port's
`app.py` reads the same three positionals at module load; this module
factors the parse out so it is testable without importing the UI.
"""
from __future__ import annotations

DEFAULT_SERVICE = "google"
DEFAULT_TARGET = "vi"
DEFAULT_THEME = "Blue"


def parse_args(argv):
    """``argv`` is the argument list WITHOUT the program name.

    Returns ``(service, target, theme, cli_service, cli_target)`` where
    the two flags record whether the user gave an explicit positional
    (an explicit value overrides the restored session).
    """
    args = list(argv or [])
    service = args[0] if len(args) > 0 else DEFAULT_SERVICE
    target = args[1] if len(args) > 1 else DEFAULT_TARGET
    theme = args[2] if len(args) > 2 else DEFAULT_THEME
    return (service, target, theme,
            len(args) > 0, len(args) > 1)
