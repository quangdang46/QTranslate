"""The ``Result`` shape an extension's provider returns.

A standalone copy of the host's ``qtranslate.core.Result``. It has to be
a copy: this package must not import the desktop app, and the app must
not depend on the SDK being installed. The two definitions are kept in
step by ``tests/regress_sdk_package.py``, which compares their field
lists and defaults -- a drift makes that test fail rather than an
extension break at runtime.

APPEND-ONLY, like the host's: a new field goes at the END with a
default, because providers construct a Result positionally.
"""
from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class Result:
    provider_used: str
    text: str
    requested: str = ""
    failures: tuple = ()
    attempts: int = 0
    note: str = ""
    phonetics: str = ""
    source_language: int | None = None

    @property
    def ok(self) -> bool:
        """True when some provider answered."""
        return bool(self.provider_used)

    @property
    def source_language_code(self) -> str:
        """The detected source language's code, when the provider gave one."""
        if self.source_language is None:
            return ""
        try:
            from .languages import lang_code_at
            return lang_code_at(self.source_language)
        except Exception:
            return ""
