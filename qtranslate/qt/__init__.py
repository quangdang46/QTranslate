"""The PySide6 front end.

The port's core -- the engine, the registry, the providers, the config,
the history -- is toolkit-agnostic and lives in ``qtranslate/``. This
package is the VIEW: the windows, drawn on the coordinates measured off
the native captures (see ``qtranslate-pyside6-spec.md``).
"""
from __future__ import annotations

__all__ = ["app", "main_window", "widgets"]
